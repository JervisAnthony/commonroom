"""Tests for PostgresQuizAttemptRepository, relational schema, and PostgreSQL integration.

Covers:
1. Protocol conformance (QuizAttemptRepository)
2. Ephemeral DB unit tests:
   - Attempt creation persists and is retrievable
   - Unknown attempt returns None
   - Duplicate attempt creation raises QuizAttemptError
   - Transactional completion persists question results and selected choices
   - Reconstructed QuizResult equals original completed domain result
   - Deterministic retrieval across repeated calls
   - Single-completion invariant (cannot complete already-completed attempt)
   - Rollback leaves attempt in_progress if an error occurs
   - Answer keys and explanations are not duplicated in attempt snapshot tables
   - Database-backed API endpoints end-to-end verification
3. Live PostgreSQL integration tests (@requires_postgres):
   - Alembic migration 0002 applies successfully
   - Migration downgrade 0001 -> upgrade head roundtrip
   - Live PostgreSQL repository attempt lifecycle
   - Live PostgreSQL end-to-end FastAPI attempt API test
"""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from threading import Barrier
from typing import Any
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from hogwarts_trials_api.api.dependencies import (
    get_quiz_attempt_repository,
    get_quiz_repository,
)
from hogwarts_trials_api.application.quiz_attempt_repository import (
    QuizAttemptRepository,
)
from hogwarts_trials_api.domain.attempt import (
    AttemptStatus,
    QuizAttempt,
    QuizAttemptAlreadyCompletedError,
    QuizAttemptError,
    QuizAttemptNotFoundError,
    complete_attempt,
    create_quiz_attempt,
)
from hogwarts_trials_api.domain.grading import QuestionResultStatus
from hogwarts_trials_api.domain.quiz import AnswerSubmission
from hogwarts_trials_api.infrastructure.database import (
    create_db_engine,
    create_session_factory,
    validate_database_url,
)
from hogwarts_trials_api.infrastructure.in_memory_quiz_repository import (
    DEMO_QUIZ_ID,
    Q1_C1_ID,
    Q1_C2_ID,
    Q1_ID,
    Q2_C1_ID,
    Q2_C3_ID,
    Q2_ID,
    Q3_C3_ID,
    Q3_ID,
    _DEMO_QUIZ,
)
from hogwarts_trials_api.infrastructure.models import (
    Base,
    QuestionChoiceModel,
    QuestionCorrectChoiceModel,
    QuestionModel,
    QuizAttemptModel,
    QuizAttemptQuestionResultModel,
    QuizAttemptSelectedChoiceModel,
    QuizModel,
    QuizQuestionModel,
)
from hogwarts_trials_api.infrastructure.postgres_quiz_attempt_repository import (
    PostgresQuizAttemptRepository,
)
from hogwarts_trials_api.infrastructure.postgres_quiz_repository import (
    PostgresQuizRepository,
)
from hogwarts_trials_api.infrastructure.quiz_mapper import quiz_domain_to_model
from hogwarts_trials_api.main import app

TEST_DB_URL_ENV_VAR = "HOGWARTS_TRIALS_TEST_DATABASE_URL"
TEST_DB_URL = os.environ.get(TEST_DB_URL_ENV_VAR)

SENSITIVE_FIELD_NAMES = (
    "correct_choice_ids",
    "explanation",
    "provenance",
    "source_tier",
    "source_reference",
    "chapter_reference",
    "curation_status",
)


def assert_no_sensitive_fields(payload: Any) -> None:
    """Recursively confirm that no forbidden answer-key or editorial fields appear."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            assert k not in SENSITIVE_FIELD_NAMES, f"Sensitive field '{k}' exposed!"
            assert_no_sensitive_fields(v)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_sensitive_fields(item)


# ==============================================================================
# 1. UNIT TESTS: EPHEMERAL SQLITE IN-MEMORY ENGINE
# ==============================================================================


@pytest.fixture
def sqlite_attempt_repo() -> tuple[
    PostgresQuizAttemptRepository, PostgresQuizRepository, sessionmaker[Session]
]:
    """Create an ephemeral SQLite in-memory database with all models created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Seed demo quiz
    with factory() as session:
        session.add(quiz_domain_to_model(_DEMO_QUIZ))
        session.commit()

    attempt_repo = PostgresQuizAttemptRepository(session_factory=factory)
    quiz_repo = PostgresQuizRepository(session_factory=factory)
    return attempt_repo, quiz_repo, factory


def test_postgres_repo_protocol_conformance(sqlite_attempt_repo):
    attempt_repo, _, _ = sqlite_attempt_repo
    assert isinstance(attempt_repo, QuizAttemptRepository)


def test_postgres_repo_create_and_get_attempt(sqlite_attempt_repo):
    attempt_repo, _, _ = sqlite_attempt_repo
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)

    created = attempt_repo.create_attempt(attempt)
    assert created == attempt

    retrieved = attempt_repo.get_attempt(attempt.attempt_id)
    assert retrieved is not None
    assert retrieved.attempt_id == attempt.attempt_id
    assert retrieved.quiz_id == DEMO_QUIZ_ID
    assert retrieved.status == AttemptStatus.in_progress
    assert retrieved.result is None


def test_postgres_repo_get_unknown_attempt(sqlite_attempt_repo):
    attempt_repo, _, _ = sqlite_attempt_repo
    assert attempt_repo.get_attempt(uuid4()) is None


def test_postgres_repo_duplicate_attempt_rejected(sqlite_attempt_repo):
    attempt_repo, _, _ = sqlite_attempt_repo
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)
    attempt_repo.create_attempt(attempt)

    duplicate = QuizAttempt(
        attempt_id=attempt.attempt_id,
        quiz_id=DEMO_QUIZ_ID,
        status=AttemptStatus.in_progress,
    )
    with pytest.raises(QuizAttemptError, match="already exists"):
        attempt_repo.create_attempt(duplicate)


def test_postgres_repo_completion_transaction(sqlite_attempt_repo):
    attempt_repo, quiz_repo, factory = sqlite_attempt_repo
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)
    attempt_repo.create_attempt(attempt)

    quiz = quiz_repo.get_quiz(DEMO_QUIZ_ID)
    assert quiz is not None

    submissions = (
        AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(Q1_C2_ID,)),  # correct
        AnswerSubmission(question_id=Q2_ID, selected_choice_ids=(Q2_C1_ID, Q2_C3_ID)),  # correct
        # Q3 unanswered
    )
    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=submissions)
    persisted = attempt_repo.complete_attempt(completed)

    assert persisted == completed

    # Verify rows in database
    with factory() as session:
        attempt_row = session.get(QuizAttemptModel, attempt.attempt_id)
        assert attempt_row is not None
        assert attempt_row.status == "completed"

        qr_rows = session.scalars(
            select(QuizAttemptQuestionResultModel).where(
                QuizAttemptQuestionResultModel.attempt_id == attempt.attempt_id
            )
        ).all()
        assert len(qr_rows) == 3

        sc_rows = session.scalars(
            select(QuizAttemptSelectedChoiceModel).where(
                QuizAttemptSelectedChoiceModel.attempt_id == attempt.attempt_id
            )
        ).all()
        # Q1 has 1 choice, Q2 has 2 choices, Q3 has 0 choices -> 3 total
        assert len(sc_rows) == 3

    # Verify reconstructed QuizResult equals original completed result
    retrieved = attempt_repo.get_attempt(attempt.attempt_id)
    assert retrieved is not None
    assert retrieved == completed
    assert retrieved.result == completed.result
    assert retrieved.result.total_points == 2
    assert retrieved.result.correct_count == 2
    assert retrieved.result.unanswered_count == 1


def test_postgres_repo_deterministic_retrieval(sqlite_attempt_repo):
    attempt_repo, quiz_repo, _ = sqlite_attempt_repo
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)
    attempt_repo.create_attempt(attempt)

    quiz = quiz_repo.get_quiz(DEMO_QUIZ_ID)
    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=())
    attempt_repo.complete_attempt(completed)

    r1 = attempt_repo.get_attempt(attempt.attempt_id)
    r2 = attempt_repo.get_attempt(attempt.attempt_id)
    r3 = attempt_repo.get_attempt(attempt.attempt_id)
    assert r1 == r2 == r3 == completed


def test_postgres_repo_cannot_complete_twice(sqlite_attempt_repo):
    attempt_repo, quiz_repo, _ = sqlite_attempt_repo
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)
    attempt_repo.create_attempt(attempt)

    quiz = quiz_repo.get_quiz(DEMO_QUIZ_ID)
    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=())
    attempt_repo.complete_attempt(completed)

    with pytest.raises(QuizAttemptAlreadyCompletedError, match="already completed"):
        attempt_repo.complete_attempt(completed)


def test_postgres_repo_complete_unknown_attempt_raises(sqlite_attempt_repo):
    attempt_repo, quiz_repo, _ = sqlite_attempt_repo
    quiz = quiz_repo.get_quiz(DEMO_QUIZ_ID)
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)
    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=())

    with pytest.raises(QuizAttemptNotFoundError, match="not found"):
        attempt_repo.complete_attempt(completed)


def test_postgres_repo_rollback_on_failure(sqlite_attempt_repo):
    attempt_repo, quiz_repo, factory = sqlite_attempt_repo
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)
    attempt_repo.create_attempt(attempt)

    quiz = quiz_repo.get_quiz(DEMO_QUIZ_ID)
    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=())

    # Simulate an error by corrupting the question_id to an invalid foreign key
    corrupted_qr = completed.result.question_results[0].model_copy(
        update={"question_id": uuid4()}
    )
    corrupted_result = completed.result.model_copy(
        update={"question_results": (corrupted_qr,)}
    )
    corrupted_attempt = completed.model_copy(update={"result": corrupted_result})

    with pytest.raises(Exception):
        attempt_repo.complete_attempt(corrupted_attempt)

    # In-progress status must remain intact
    retrieved = attempt_repo.get_attempt(attempt.attempt_id)
    assert retrieved is not None
    assert retrieved.status == AttemptStatus.in_progress
    assert retrieved.result is None


def test_answer_keys_not_duplicated_in_attempt_tables(sqlite_attempt_repo):
    """Verify that attempt snapshot tables do NOT contain answer-key or explanation columns."""
    _, _, factory = sqlite_attempt_repo
    with factory() as session:
        insp = inspect(session.bind)

        # 1. quiz_attempt_question_results columns
        qr_cols = {c["name"] for c in insp.get_columns("quiz_attempt_question_results")}
        assert qr_cols == {"attempt_id", "question_id", "status", "awarded_points", "max_points"}
        assert "correct_choice_ids" not in qr_cols
        assert "explanation" not in qr_cols
        assert "provenance" not in qr_cols

        # 2. quiz_attempt_selected_choices columns
        sc_cols = {c["name"] for c in insp.get_columns("quiz_attempt_selected_choices")}
        assert sc_cols == {"attempt_id", "question_id", "choice_id"}
        assert "is_correct" not in sc_cols


def test_database_backed_api_endpoints(sqlite_attempt_repo):
    """Verify FastAPI attempt endpoints backed by database repositories."""
    attempt_repo, quiz_repo, _ = sqlite_attempt_repo
    client = TestClient(app)

    app.dependency_overrides[get_quiz_repository] = lambda: quiz_repo
    app.dependency_overrides[get_quiz_attempt_repository] = lambda: attempt_repo

    try:
        # 1. Start attempt
        start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
        assert start_res.status_code == 201
        start_data = start_res.json()
        attempt_id = start_data["attempt_id"]
        assert start_data["status"] == "in_progress"
        assert_no_sensitive_fields(start_data)

        # 2. Get in-progress attempt
        get_res = client.get(f"/api/v1/attempts/{attempt_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["status"] == "in_progress"
        assert get_data["result"] is None
        assert_no_sensitive_fields(get_data)

        # 3. Submit attempt
        submit_payload = {
            "submissions": [
                {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
                {"question_id": str(Q2_ID), "selected_choice_ids": [str(Q2_C1_ID), str(Q2_C3_ID)]},
                {"question_id": str(Q3_ID), "selected_choice_ids": [str(Q3_C3_ID)]},
            ]
        }
        submit_res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=submit_payload)
        assert submit_res.status_code == 200
        submit_data = submit_res.json()
        assert submit_data["status"] == "completed"
        assert submit_data["result"]["total_points"] == 3
        assert_no_sensitive_fields(submit_data)

        # 4. Get completed attempt
        get_completed_res = client.get(f"/api/v1/attempts/{attempt_id}")
        assert get_completed_res.status_code == 200
        completed_data = get_completed_res.json()
        assert completed_data["status"] == "completed"
        assert completed_data["result"]["total_points"] == 3
        assert_no_sensitive_fields(completed_data)

        # 5. Cannot resubmit
        resubmit_res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=submit_payload)
        assert resubmit_res.status_code == 409
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 2. INTEGRATION TESTS: REAL POSTGRESQL INSTANCE (SKIPPED LOCALLY IF NO DB CONFIGURED)
# ==============================================================================

requires_postgres = pytest.mark.skipif(
    not TEST_DB_URL,
    reason=f"Integration test requires {TEST_DB_URL_ENV_VAR} environment variable pointing to PostgreSQL",
)


@pytest.fixture(scope="module")
def postgres_test_engine():
    """Module-scoped PostgreSQL engine connected to the dedicated test database."""
    if not TEST_DB_URL:
        pytest.skip(f"{TEST_DB_URL_ENV_VAR} not set")
    engine = create_db_engine(TEST_DB_URL)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def postgres_migrated_db(postgres_test_engine):
    """Run Alembic upgrade head against the real PostgreSQL test database."""
    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", validate_database_url(TEST_DB_URL))

    # Apply all migrations to head (0001 and 0002)
    command.upgrade(alembic_cfg, "head")

    yield postgres_test_engine


@pytest.fixture
def postgres_session_factory(postgres_migrated_db):
    """Session factory for PostgreSQL integration tests with clean tables per test."""
    factory = create_session_factory(postgres_migrated_db)

    def clean_tables():
        with factory() as session:
            session.query(QuizAttemptSelectedChoiceModel).delete()
            session.query(QuizAttemptQuestionResultModel).delete()
            session.query(QuizAttemptModel).delete()
            session.query(QuestionCorrectChoiceModel).delete()
            session.query(QuestionChoiceModel).delete()
            session.query(QuizQuestionModel).delete()
            session.query(QuestionModel).delete()
            session.query(QuizModel).delete()
            session.commit()

    clean_tables()
    yield factory
    clean_tables()


@requires_postgres
def test_postgres_migration_0002_upgrade_downgrade_cycle():
    """Verify revision 0002 applies cleanly and downgrades cleanly back to 0001."""
    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", validate_database_url(TEST_DB_URL))

    # Downgrade to 0001
    command.downgrade(alembic_cfg, "0001")

    # Verify attempt tables dropped
    engine = create_db_engine(TEST_DB_URL)
    with engine.connect() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        assert "quiz_attempts" not in tables
        assert "quiz_attempt_question_results" not in tables
        assert "quiz_attempt_selected_choices" not in tables
        assert "quizzes" in tables
        assert "questions" in tables

    # Upgrade back to head (0002)
    command.upgrade(alembic_cfg, "head")
    with engine.connect() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        assert "quiz_attempts" in tables
        assert "quiz_attempt_question_results" in tables
        assert "quiz_attempt_selected_choices" in tables
    engine.dispose()


@requires_postgres
def test_postgres_attempt_lifecycle_integration(postgres_session_factory):
    """Integration test verifying full attempt lifecycle backed by real PostgreSQL 17."""
    with postgres_session_factory() as session:
        session.add(quiz_domain_to_model(_DEMO_QUIZ))
        session.commit()

    attempt_repo = PostgresQuizAttemptRepository(session_factory=postgres_session_factory)
    quiz_repo = PostgresQuizRepository(session_factory=postgres_session_factory)

    # 1. Create attempt
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)
    attempt_repo.create_attempt(attempt)

    # 2. Retrieve in-progress attempt
    retrieved = attempt_repo.get_attempt(attempt.attempt_id)
    assert retrieved is not None
    assert retrieved.status == AttemptStatus.in_progress
    assert retrieved.result is None

    # 3. Complete attempt
    quiz = quiz_repo.get_quiz(DEMO_QUIZ_ID)
    assert quiz is not None
    submissions = (
        AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(Q1_C2_ID,)),
        AnswerSubmission(question_id=Q2_ID, selected_choice_ids=(Q2_C1_ID, Q2_C3_ID)),
        AnswerSubmission(question_id=Q3_ID, selected_choice_ids=(Q3_C3_ID,)),
    )
    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=submissions)
    persisted = attempt_repo.complete_attempt(completed)
    assert persisted.status == AttemptStatus.completed
    assert persisted.result.total_points == 3

    # 4. Re-retrieve completed attempt
    final_read = attempt_repo.get_attempt(attempt.attempt_id)
    assert final_read is not None
    assert final_read == completed
    assert final_read.result == completed.result


@requires_postgres
def test_postgres_api_attempt_endpoints_integration(postgres_session_factory):
    """End-to-end API integration test with live PostgreSQL and FastAPI TestClient."""
    with postgres_session_factory() as session:
        session.add(quiz_domain_to_model(_DEMO_QUIZ))
        session.commit()

    attempt_repo = PostgresQuizAttemptRepository(session_factory=postgres_session_factory)
    quiz_repo = PostgresQuizRepository(session_factory=postgres_session_factory)

    client = TestClient(app)
    app.dependency_overrides[get_quiz_repository] = lambda: quiz_repo
    app.dependency_overrides[get_quiz_attempt_repository] = lambda: attempt_repo

    try:
        # POST start attempt
        start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
        assert start_res.status_code == 201
        attempt_id = start_res.json()["attempt_id"]

        # POST submit attempt
        submit_payload = {
            "submissions": [
                {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
                {"question_id": str(Q2_ID), "selected_choice_ids": [str(Q2_C1_ID), str(Q2_C3_ID)]},
            ]
        }
        submit_res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=submit_payload)
        assert submit_res.status_code == 200
        submit_data = submit_res.json()
        assert submit_data["status"] == "completed"
        assert submit_data["result"]["total_points"] == 2
        assert submit_data["result"]["max_points"] == 3
        assert submit_data["result"]["correct_count"] == 2
        assert submit_data["result"]["unanswered_count"] == 1

        # GET completed attempt
        get_res = client.get(f"/api/v1/attempts/{attempt_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["status"] == "completed"
        assert get_data["result"]["total_points"] == 2

        # Check secrecy across responses
        assert_no_sensitive_fields(start_res.json())
        assert_no_sensitive_fields(submit_data)
        assert_no_sensitive_fields(get_data)
    finally:
        app.dependency_overrides.clear()



@requires_postgres
def test_postgres_concurrent_completions_preserve_one_winner(postgres_session_factory):
    """Competing transactions must persist exactly one result and reject the loser."""
    with postgres_session_factory() as session:
        session.add(quiz_domain_to_model(_DEMO_QUIZ))
        session.commit()

    repo = PostgresQuizAttemptRepository(session_factory=postgres_session_factory)
    attempt = create_quiz_attempt(DEMO_QUIZ_ID)
    repo.create_attempt(attempt)
    candidates = (
        complete_attempt(attempt=attempt, quiz=_DEMO_QUIZ, submissions=()),
        complete_attempt(
            attempt=attempt,
            quiz=_DEMO_QUIZ,
            submissions=(AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(Q1_C2_ID,)),),
        ),
    )
    ready = Barrier(2, timeout=10)

    def submit(candidate: QuizAttempt) -> QuizAttempt | None:
        ready.wait()
        try:
            return repo.complete_attempt(candidate)
        except QuizAttemptAlreadyCompletedError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(submit, candidates))

    winners = [outcome for outcome in outcomes if outcome is not None]
    assert len(winners) == 1
    assert outcomes.count(None) == 1
    assert repo.get_attempt(attempt.attempt_id) == winners[0]
    with postgres_session_factory() as session:
        result_rows = session.scalars(
            select(QuizAttemptQuestionResultModel).where(
                QuizAttemptQuestionResultModel.attempt_id == attempt.attempt_id
            )
        ).all()
        selected_rows = session.scalars(
            select(QuizAttemptSelectedChoiceModel).where(
                QuizAttemptSelectedChoiceModel.attempt_id == attempt.attempt_id
            )
        ).all()
        assert len(result_rows) == len(winners[0].result.question_results)
        assert len(selected_rows) == sum(
            len(result.selected_choice_ids) for result in winners[0].result.question_results
        )
