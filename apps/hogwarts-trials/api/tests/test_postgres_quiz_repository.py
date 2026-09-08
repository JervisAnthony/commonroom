"""Tests for PostgreSQL QuizRepository adapter, models, mapper, and configuration.

Includes comprehensive unit tests covering:
- Backend configuration parsing and defaults
- Database URL validation and normalization
- Domain <-> persistence mapping fidelity
- Deterministic ordering of questions and choices
- Strict rejection of invalid persisted enum values
- Repository protocol conformance
- Parity between in-memory and database-loaded quiz grading
- Answer-key secrecy enforcement with PostgresQuizRepository
- PostgreSQL integration tests (executed when HOGWARTS_TRIALS_TEST_DATABASE_URL is provided)
"""

import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from hogwarts_trials_api.api.dependencies import (
    build_quiz_repository,
    get_quiz_repository,
    reset_quiz_repository,
    set_quiz_repository,
)
from hogwarts_trials_api.application.quiz_repository import QuizRepository
from hogwarts_trials_api.domain.grading import grade_quiz
from hogwarts_trials_api.domain.quiz import (
    AnswerSubmission,
    CurationStatus,
    QuestionChoice,
    QuestionDifficulty,
    QuestionProvenance,
    QuestionType,
    Quiz,
    QuizQuestion,
    SourceTier,
)
from hogwarts_trials_api.infrastructure.database import (
    DATABASE_URL_ENV_VAR,
    DEFAULT_REPOSITORY_BACKEND,
    QUIZ_REPOSITORY_ENV_VAR,
    create_db_engine,
    create_session_factory,
    get_database_url,
    get_repository_backend,
    validate_database_url,
)
from hogwarts_trials_api.infrastructure.in_memory_quiz_repository import (
    DEMO_QUIZ_ID,
    Q1_C2_ID,
    Q1_ID,
    Q2_C1_ID,
    Q2_C3_ID,
    Q2_ID,
    Q3_C3_ID,
    Q3_ID,
    InMemoryQuizRepository,
    _DEMO_QUIZ,
)
from hogwarts_trials_api.infrastructure.models import (
    Base,
    QuestionChoiceModel,
    QuestionCorrectChoiceModel,
    QuestionModel,
    QuizModel,
    QuizQuestionModel,
)
from hogwarts_trials_api.infrastructure.postgres_quiz_repository import (
    PostgresQuizRepository,
)
from hogwarts_trials_api.infrastructure.quiz_mapper import (
    question_model_to_domain,
    quiz_domain_to_model,
    quiz_model_to_domain,
)
from hogwarts_trials_api.main import app

TEST_DB_URL_ENV_VAR = "HOGWARTS_TRIALS_TEST_DATABASE_URL"
TEST_DB_URL = os.environ.get(TEST_DB_URL_ENV_VAR)


# ==============================================================================
# UNIT TESTS: CONFIGURATION & DATABASE HELPERS
# ==============================================================================


def test_repository_backend_default_is_memory():
    assert get_repository_backend({}) == DEFAULT_REPOSITORY_BACKEND
    assert get_repository_backend({QUIZ_REPOSITORY_ENV_VAR: ""}) == "memory"
    assert get_repository_backend({QUIZ_REPOSITORY_ENV_VAR: "   "}) == "memory"


def test_repository_backend_explicit_values():
    assert get_repository_backend({QUIZ_REPOSITORY_ENV_VAR: "memory"}) == "memory"
    assert get_repository_backend({QUIZ_REPOSITORY_ENV_VAR: "postgres"}) == "postgres"
    assert get_repository_backend({QUIZ_REPOSITORY_ENV_VAR: "  POSTGRES  "}) == "postgres"
    assert get_repository_backend({QUIZ_REPOSITORY_ENV_VAR: "MEMORY"}) == "memory"


def test_repository_backend_unsupported_value_fails():
    with pytest.raises(ValueError, match="Unsupported quiz repository backend: 'redis'"):
        get_repository_backend({QUIZ_REPOSITORY_ENV_VAR: "redis"})


def test_database_url_validation_valid():
    url = "postgresql+psycopg://user:password@localhost:5432/hogwarts_trials"
    assert validate_database_url(url) == url


def test_database_url_validation_normalizes_postgresql_scheme():
    url = "postgresql://user:password@localhost:5432/hogwarts_trials"
    expected = "postgresql+psycopg://user:password@localhost:5432/hogwarts_trials"
    assert validate_database_url(url) == expected


def test_database_url_validation_rejects_empty():
    with pytest.raises(ValueError, match="Database URL must be a non-empty string"):
        validate_database_url("")
    with pytest.raises(ValueError, match="Database URL must be a non-empty string"):
        validate_database_url("   ")


def test_database_url_validation_rejects_unsupported_schemes():
    with pytest.raises(ValueError, match="Invalid database URL scheme: 'sqlite'"):
        validate_database_url("sqlite:///data.db")
    with pytest.raises(ValueError, match="Invalid database URL scheme: 'mysql'"):
        validate_database_url("mysql://user:pass@localhost/db")


def test_get_database_url_raises_when_missing():
    with pytest.raises(ValueError, match="HOGWARTS_TRIALS_DATABASE_URL environment variable is required"):
        get_database_url({})


def test_get_database_url_returns_normalized():
    env = {DATABASE_URL_ENV_VAR: "postgresql://user:pass@localhost:5432/db"}
    assert get_database_url(env) == "postgresql+psycopg://user:pass@localhost:5432/db"


def test_build_quiz_repository_default_memory():
    repo = build_quiz_repository(env={})
    assert isinstance(repo, InMemoryQuizRepository)
    assert isinstance(repo, QuizRepository)


def test_build_quiz_repository_explicit_memory():
    repo = build_quiz_repository(backend="memory")
    assert isinstance(repo, InMemoryQuizRepository)


def test_build_quiz_repository_postgres_missing_url_raises():
    with pytest.raises(ValueError, match="HOGWARTS_TRIALS_DATABASE_URL environment variable is required"):
        build_quiz_repository(backend="postgres", env={})


def test_build_quiz_repository_postgres_constructs_repo():
    url = "postgresql+psycopg://test_user:test_pass@localhost:5432/test_db"
    repo = build_quiz_repository(backend="postgres", database_url=url)
    assert isinstance(repo, PostgresQuizRepository)
    assert isinstance(repo, QuizRepository)


def test_build_quiz_repository_invalid_backend_raises():
    with pytest.raises(ValueError, match="Unsupported quiz repository backend"):
        build_quiz_repository(backend="mongodb")


def test_memory_mode_does_not_construct_database_engine(monkeypatch):
    """Confirm that memory mode does not call create_db_engine or inspect DATABASE_URL."""
    called = False

    def mock_create_engine(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Engine construction should not be called in memory mode")

    monkeypatch.setattr("hogwarts_trials_api.api.dependencies.create_db_engine", mock_create_engine)
    monkeypatch.delenv(DATABASE_URL_ENV_VAR, raising=False)
    monkeypatch.setenv(QUIZ_REPOSITORY_ENV_VAR, "memory")

    reset_quiz_repository()
    try:
        repo = get_quiz_repository()
        assert isinstance(repo, InMemoryQuizRepository)
        assert not called
    finally:
        reset_quiz_repository()


def test_set_and_reset_quiz_repository():
    custom_repo = InMemoryQuizRepository(quizzes=())
    set_quiz_repository(custom_repo)
    assert get_quiz_repository() is custom_repo
    reset_quiz_repository()
    # After reset, it creates default instance
    default_repo = get_quiz_repository()
    assert default_repo is not custom_repo
    reset_quiz_repository()


# ==============================================================================
# UNIT TESTS: PERSISTENCE MODELS & DOMAIN MAPPER
# ==============================================================================


def test_postgres_quiz_repository_protocol_conformance():
    fake_factory = sessionmaker()
    repo = PostgresQuizRepository(session_factory=fake_factory)
    assert isinstance(repo, QuizRepository)


def test_round_trip_mapper_preserves_demo_quiz():
    """Verify that domain -> model -> domain round trip preserves the demo quiz exactly."""
    model = quiz_domain_to_model(_DEMO_QUIZ)
    assert isinstance(model, QuizModel)
    assert model.quiz_id == _DEMO_QUIZ.quiz_id
    assert model.title == _DEMO_QUIZ.title
    assert model.description == _DEMO_QUIZ.description
    assert len(model.quiz_questions) == 3

    reconstructed = quiz_model_to_domain(model)
    assert reconstructed == _DEMO_QUIZ
    assert reconstructed.model_dump() == _DEMO_QUIZ.model_dump()


def test_mapper_preserves_question_and_choice_ordering():
    """Verify that out-of-order relational models are reconstructed with deterministic ordering."""
    quiz_id = uuid4()
    q1_id = uuid4()
    c1_id = uuid4()
    c2_id = uuid4()

    q_model = QuestionModel(
        question_id=q1_id,
        prompt="Test question?",
        question_type=QuestionType.single_choice.value,
        difficulty=QuestionDifficulty.easy.value,
        explanation="Test explanation.",
        source_tier=SourceTier.synthetic.value,
        source_reference="test-ref",
        chapter_reference=None,
        curation_status=CurationStatus.approved.value,
    )
    # Append choices in reverse position order
    q_model.choices = [
        QuestionChoiceModel(choice_id=c2_id, question_id=q1_id, text="Choice 2", position=2),
        QuestionChoiceModel(choice_id=c1_id, question_id=q1_id, text="Choice 1", position=1),
    ]
    q_model.correct_choices = [
        QuestionCorrectChoiceModel(question_id=q1_id, choice_id=c1_id),
    ]

    domain_question = question_model_to_domain(q_model)
    assert domain_question.choices[0].choice_id == c1_id
    assert domain_question.choices[0].text == "Choice 1"
    assert domain_question.choices[1].choice_id == c2_id
    assert domain_question.choices[1].text == "Choice 2"
    assert domain_question.correct_choice_ids == (c1_id,)


def test_mapper_fails_on_invalid_persisted_enum_values():
    q_id = uuid4()
    base_kwargs: dict[str, Any] = {
        "question_id": q_id,
        "prompt": "Valid prompt?",
        "question_type": QuestionType.single_choice.value,
        "difficulty": QuestionDifficulty.easy.value,
        "explanation": "Explanation",
        "source_tier": SourceTier.synthetic.value,
        "source_reference": "ref",
        "chapter_reference": None,
        "curation_status": CurationStatus.approved.value,
    }

    # Invalid question_type
    bad_type = QuestionModel(**{**base_kwargs, "question_type": "invalid_type"})
    with pytest.raises(ValueError):
        question_model_to_domain(bad_type)

    # Invalid difficulty
    bad_diff = QuestionModel(**{**base_kwargs, "difficulty": "impossible"})
    with pytest.raises(ValueError):
        question_model_to_domain(bad_diff)

    # Invalid source_tier
    bad_tier = QuestionModel(**{**base_kwargs, "source_tier": "fan_fiction"})
    with pytest.raises(ValueError):
        question_model_to_domain(bad_tier)

    # Invalid curation_status
    bad_status = QuestionModel(**{**base_kwargs, "curation_status": "unreviewed"})
    with pytest.raises(ValueError):
        question_model_to_domain(bad_status)


# ==============================================================================
# UNIT TESTS: REPOSITORY QUERIES & GRADING PARITY (IN-MEMORY DB ENGINE)
# ==============================================================================


@pytest.fixture
def sqlite_in_memory_repo() -> tuple[PostgresQuizRepository, sessionmaker[Session]]:
    """Create an ephemeral SQLite in-memory database to test PostgresQuizRepository query logic."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Seed demo quiz
    with factory() as session:
        session.add(quiz_domain_to_model(_DEMO_QUIZ))
        session.commit()

    repo = PostgresQuizRepository(session_factory=factory)
    return repo, factory


def test_repo_list_quizzes_returns_demo_quiz(sqlite_in_memory_repo):
    repo, _ = sqlite_in_memory_repo
    quizzes = repo.list_quizzes()
    assert isinstance(quizzes, tuple)
    assert len(quizzes) == 1
    assert quizzes[0].quiz_id == DEMO_QUIZ_ID
    assert quizzes[0].title == "Synthetic Demonstration Quiz"
    assert len(quizzes[0].questions) == 3


def test_repo_get_quiz_returns_expected_quiz(sqlite_in_memory_repo):
    repo, _ = sqlite_in_memory_repo
    quiz = repo.get_quiz(DEMO_QUIZ_ID)
    assert quiz is not None
    assert quiz.quiz_id == DEMO_QUIZ_ID
    assert quiz == _DEMO_QUIZ


def test_repo_get_quiz_returns_none_for_unknown_id(sqlite_in_memory_repo):
    repo, _ = sqlite_in_memory_repo
    unknown_id = uuid4()
    assert repo.get_quiz(unknown_id) is None


def test_repo_deterministic_reads(sqlite_in_memory_repo):
    repo, _ = sqlite_in_memory_repo
    reads = [repo.list_quizzes() for _ in range(3)]
    assert reads[0] == reads[1] == reads[2]


def test_grading_parity_between_memory_and_persisted_quiz(sqlite_in_memory_repo):
    """Parity regression test: grading a persistence-loaded quiz grades identically to in-memory."""
    repo, _ = sqlite_in_memory_repo
    persisted_quiz = repo.get_quiz(DEMO_QUIZ_ID)
    assert persisted_quiz is not None

    submissions = (
        AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(Q1_C2_ID,)),  # correct (4)
        AnswerSubmission(question_id=Q2_ID, selected_choice_ids=(Q2_C1_ID, Q2_C3_ID)),  # correct (Square, Rect)
        # Q3 omitted -> unanswered
    )

    in_memory_result = grade_quiz(quiz=_DEMO_QUIZ, submissions=submissions)
    persisted_result = grade_quiz(quiz=persisted_quiz, submissions=submissions)

    assert in_memory_result == persisted_result
    assert persisted_result.total_points == 2
    assert persisted_result.max_points == 3
    assert persisted_result.correct_count == 2
    assert persisted_result.unanswered_count == 1
    assert persisted_result.incorrect_count == 0


def test_database_backed_api_responses_preserve_answer_key_secrecy(sqlite_in_memory_repo):
    """Confirm that endpoints backed by PostgresQuizRepository never leak answer keys or provenance."""
    repo, _ = sqlite_in_memory_repo
    client = TestClient(app)
    app.dependency_overrides[get_quiz_repository] = lambda: repo

    try:
        # 1. Detail endpoint
        detail_res = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
        assert detail_res.status_code == 200
        detail_data = detail_res.json()

        def assert_no_sensitive_keys(data: Any) -> None:
            if isinstance(data, dict):
                for key, val in data.items():
                    assert key not in (
                        "correct_choice_ids",
                        "explanation",
                        "provenance",
                        "source_tier",
                        "source_reference",
                        "chapter_reference",
                        "curation_status",
                    )
                    assert_no_sensitive_keys(val)
            elif isinstance(data, list):
                for item in data:
                    assert_no_sensitive_keys(item)

        assert_no_sensitive_keys(detail_data)

        # 2. Grade endpoint
        grade_payload = {
            "submissions": [
                {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
            ]
        }
        grade_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=grade_payload)
        assert grade_res.status_code == 200
        grade_data = grade_res.json()
        assert_no_sensitive_keys(grade_data)

    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# INTEGRATION TESTS: REAL POSTGRESQL INSTANCE (SKIPPED LOCALLY IF NO DB CONFIGURED)
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

    # Apply all migrations to head
    command.upgrade(alembic_cfg, "head")

    yield postgres_test_engine

    # Optional downgrade after module run
    # command.downgrade(alembic_cfg, "base")


@pytest.fixture
def postgres_session_factory(postgres_migrated_db):
    """Session factory for PostgreSQL integration tests with clean tables per test."""
    factory = create_session_factory(postgres_migrated_db)

    # Clean existing data before test
    with factory() as session:
        session.query(QuestionCorrectChoiceModel).delete()
        session.query(QuestionChoiceModel).delete()
        session.query(QuizQuestionModel).delete()
        session.query(QuestionModel).delete()
        session.query(QuizModel).delete()
        session.commit()

    yield factory

    # Clean up after test
    with factory() as session:
        session.query(QuestionCorrectChoiceModel).delete()
        session.query(QuestionChoiceModel).delete()
        session.query(QuizQuestionModel).delete()
        session.query(QuestionModel).delete()
        session.query(QuizModel).delete()
        session.commit()


@requires_postgres
def test_postgres_migration_and_seed_lifecycle(postgres_session_factory):
    """Integration test verifying schema creation, fixture seeding, and retrieval on PostgreSQL."""
    # Seed synthetic demo quiz into PostgreSQL
    with postgres_session_factory() as session:
        session.add(quiz_domain_to_model(_DEMO_QUIZ))
        session.commit()

    repo = PostgresQuizRepository(session_factory=postgres_session_factory)

    # 1. list_quizzes
    quizzes = repo.list_quizzes()
    assert len(quizzes) == 1
    loaded_quiz = quizzes[0]
    assert loaded_quiz.quiz_id == DEMO_QUIZ_ID
    assert loaded_quiz.title == "Synthetic Demonstration Quiz"
    assert len(loaded_quiz.questions) == 3

    # 2. get_quiz
    quiz = repo.get_quiz(DEMO_QUIZ_ID)
    assert quiz is not None
    assert quiz == _DEMO_QUIZ

    # 3. Unknown UUID
    assert repo.get_quiz(uuid4()) is None

    # 4. Invariants
    for qq in quiz.questions:
        assert qq.question.provenance.source_tier == SourceTier.synthetic
        assert qq.question.provenance.source_reference == "synthetic-api-fixture"

    # 5. Grading parity on PostgreSQL
    submissions = (
        AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(Q1_C2_ID,)),
        AnswerSubmission(question_id=Q2_ID, selected_choice_ids=(Q2_C1_ID, Q2_C3_ID)),
        AnswerSubmission(question_id=Q3_ID, selected_choice_ids=(Q3_C3_ID,)),
    )
    result = grade_quiz(quiz=quiz, submissions=submissions)
    assert result.total_points == 3
    assert result.correct_count == 3


@requires_postgres
def test_postgres_api_endpoints_integration(postgres_session_factory):
    """Integration test verifying FastAPI endpoints backed by real PostgreSQL repository."""
    with postgres_session_factory() as session:
        session.add(quiz_domain_to_model(_DEMO_QUIZ))
        session.commit()

    repo = PostgresQuizRepository(session_factory=postgres_session_factory)
    client = TestClient(app)
    app.dependency_overrides[get_quiz_repository] = lambda: repo

    try:
        # GET /api/v1/quizzes
        list_res = client.get("/api/v1/quizzes")
        assert list_res.status_code == 200
        summaries = list_res.json()
        assert len(summaries) == 1
        assert summaries[0]["quiz_id"] == str(DEMO_QUIZ_ID)
        assert summaries[0]["question_count"] == 3

        # GET /api/v1/quizzes/{quiz_id}
        detail_res = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["title"] == "Synthetic Demonstration Quiz"
        assert len(detail["questions"]) == 3

        # POST /api/v1/quizzes/{quiz_id}/grade
        grade_res = client.post(
            f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade",
            json={
                "submissions": [
                    {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
                ]
            },
        )
        assert grade_res.status_code == 200
        grade_data = grade_res.json()
        assert grade_data["total_points"] == 1
        assert grade_data["max_points"] == 3
        assert grade_data["correct_count"] == 1
        assert grade_data["unanswered_count"] == 2

    finally:
        app.dependency_overrides.clear()

