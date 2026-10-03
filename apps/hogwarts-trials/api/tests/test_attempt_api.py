"""Tests for Hogwarts Trials server-owned quiz attempt REST API endpoints.

Covers:
1. START ATTEMPT (POST /api/v1/quizzes/{quiz_id}/attempts)
   - Valid start returns 201 with server-owned UUID v4, in_progress status, null result
   - Unknown quiz ID returns 404
   - Malformed quiz UUID returns 422
2. GET ATTEMPT (GET /api/v1/attempts/{attempt_id})
   - In-progress attempt returns 200 with attempt_id, quiz_id, status="in_progress", result=null
   - Completed attempt returns 200 with attempt_id, quiz_id, status="completed", safe evaluated result
   - Unknown attempt UUID returns 404
   - Malformed attempt UUID returns 422
3. SUBMIT ATTEMPT (POST /api/v1/attempts/{attempt_id}/submit)
   - Valid fully correct submission returns 200 with awarded points and correct counts
   - Valid incorrect submission returns 200 with 0 awarded points
   - Unanswered questions in submission evaluate correctly
   - Multiple-choice exact match semantics
   - Resubmitting an already completed attempt returns 409 Conflict
   - Unknown attempt returns 404
   - Unknown question ID in submission returns 422
   - Invalid choice ID in submission returns 422
   - Duplicate question submission returns 422
4. SECURITY & ANSWER-KEY BOUNDARY
   - Recursive verification that answer keys, correct_choice_ids, explanations, and
     provenance metadata never appear in any response payload
5. DEPENDENCY INJECTION PORT OVERRIDE
   - Overriding get_quiz_attempt_repository() proves routes depend on the port abstraction
"""

from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from hogwarts_trials_api.api.dependencies import (
    get_quiz_attempt_repository,
    get_quiz_repository,
    reset_quiz_attempt_repository,
    reset_quiz_repository,
)
from hogwarts_trials_api.application.quiz_attempt_repository import (
    QuizAttemptRepository,
)
from hogwarts_trials_api.domain.attempt import (
    AttemptStatus,
    QuizAttempt,
    create_quiz_attempt,
)
from hogwarts_trials_api.infrastructure.in_memory_quiz_attempt_repository import (
    InMemoryQuizAttemptRepository,
)
from hogwarts_trials_api.infrastructure.in_memory_quiz_repository import (
    DEMO_QUIZ_ID,
    Q1_C1_ID,
    Q1_C2_ID,
    Q1_ID,
    Q2_C1_ID,
    Q2_C2_ID,
    Q2_C3_ID,
    Q2_ID,
    Q3_C3_ID,
    Q3_ID,
    InMemoryQuizRepository,
    _DEMO_QUIZ,
)
from hogwarts_trials_api.main import app

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


@pytest.fixture(autouse=True)
def clean_repositories():
    """Ensure clean repository state before and after each test."""
    reset_quiz_repository()
    reset_quiz_attempt_repository()
    yield
    reset_quiz_repository()
    reset_quiz_attempt_repository()


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# 1. START ATTEMPT (POST /api/v1/quizzes/{quiz_id}/attempts)
# ==============================================================================


def test_start_attempt_success(client):
    res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    assert res.status_code == 201

    data = res.json()
    assert "attempt_id" in data
    attempt_id = UUID(data["attempt_id"])
    assert attempt_id.version == 4
    assert data["quiz_id"] == str(DEMO_QUIZ_ID)
    assert data["status"] == "in_progress"
    assert data["result"] is None

    assert_no_sensitive_fields(data)


def test_start_attempt_unknown_quiz(client):
    unknown_id = uuid4()
    res = client.post(f"/api/v1/quizzes/{unknown_id}/attempts")
    assert res.status_code == 404
    assert res.json()["detail"] == "Quiz not found"


def test_start_attempt_malformed_quiz_uuid(client):
    res = client.post("/api/v1/quizzes/not-a-valid-uuid/attempts")
    assert res.status_code == 422


# ==============================================================================
# 2. GET ATTEMPT (GET /api/v1/attempts/{attempt_id})
# ==============================================================================


def test_get_in_progress_attempt(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    assert start_res.status_code == 201
    attempt_id = start_res.json()["attempt_id"]

    get_res = client.get(f"/api/v1/attempts/{attempt_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["attempt_id"] == attempt_id
    assert data["quiz_id"] == str(DEMO_QUIZ_ID)
    assert data["status"] == "in_progress"
    assert data["result"] is None

    assert_no_sensitive_fields(data)


def test_get_unknown_attempt(client):
    unknown_id = uuid4()
    res = client.get(f"/api/v1/attempts/{unknown_id}")
    assert res.status_code == 404
    assert res.json()["detail"] == "Attempt not found"


def test_get_malformed_attempt_uuid(client):
    res = client.get("/api/v1/attempts/invalid-uuid-string")
    assert res.status_code == 422


def test_get_completed_attempt(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    attempt_id = start_res.json()["attempt_id"]

    submit_payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
        ]
    }
    submit_res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=submit_payload)
    assert submit_res.status_code == 200

    get_res = client.get(f"/api/v1/attempts/{attempt_id}")
    assert get_res.status_code == 200
    data = get_res.json()

    assert data["attempt_id"] == attempt_id
    assert data["quiz_id"] == str(DEMO_QUIZ_ID)
    assert data["status"] == "completed"
    assert data["result"] is not None
    assert data["result"]["total_points"] == 1
    assert data["result"]["max_points"] == 3
    assert data["result"]["correct_count"] == 1
    assert data["result"]["unanswered_count"] == 2

    assert_no_sensitive_fields(data)


# ==============================================================================
# 3. SUBMIT ATTEMPT (POST /api/v1/attempts/{attempt_id}/submit)
# ==============================================================================


def test_submit_attempt_fully_correct(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    attempt_id = start_res.json()["attempt_id"]

    submit_payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
            {
                "question_id": str(Q2_ID),
                "selected_choice_ids": [str(Q2_C1_ID), str(Q2_C3_ID)],
            },
            {"question_id": str(Q3_ID), "selected_choice_ids": [str(Q3_C3_ID)]},
        ]
    }
    res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=submit_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["result"]["total_points"] == 3
    assert data["result"]["max_points"] == 3
    assert data["result"]["correct_count"] == 3
    assert data["result"]["incorrect_count"] == 0
    assert data["result"]["unanswered_count"] == 0

    assert_no_sensitive_fields(data)


def test_submit_attempt_incorrect_and_unanswered(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    attempt_id = start_res.json()["attempt_id"]

    submit_payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C1_ID)]},  # incorrect
            # Q2 and Q3 omitted -> unanswered
        ]
    }
    res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=submit_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["result"]["total_points"] == 0
    assert data["result"]["max_points"] == 3
    assert data["result"]["correct_count"] == 0
    assert data["result"]["incorrect_count"] == 1
    assert data["result"]["unanswered_count"] == 2

    assert_no_sensitive_fields(data)


def test_submit_attempt_multiple_choice_exact_match(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    attempt_id = start_res.json()["attempt_id"]

    # Q2: Square (C1) and Rectangle (C3) are correct. Selecting only C1 is incorrect.
    partial_payload = {
        "submissions": [
            {"question_id": str(Q2_ID), "selected_choice_ids": [str(Q2_C1_ID)]},
        ]
    }
    res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=partial_payload)
    assert res.status_code == 200
    data = res.json()

    q2_result = next(
        r for r in data["result"]["question_results"] if r["question_id"] == str(Q2_ID)
    )
    assert q2_result["status"] == "incorrect"
    assert q2_result["awarded_points"] == 0


def test_submit_attempt_resubmission_returns_409_conflict(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    attempt_id = start_res.json()["attempt_id"]

    submit_payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
        ]
    }
    first_res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=submit_payload)
    assert first_res.status_code == 200

    second_res = client.post(f"/api/v1/attempts/{attempt_id}/submit", json=submit_payload)
    assert second_res.status_code == 409
    assert "already completed" in second_res.json()["detail"].lower()


def test_submit_unknown_attempt(client):
    unknown_id = uuid4()
    res = client.post(
        f"/api/v1/attempts/{unknown_id}/submit",
        json={"submissions": []},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Attempt not found"


def test_submit_unknown_question_returns_422(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    attempt_id = start_res.json()["attempt_id"]

    unknown_qid = uuid4()
    res = client.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        json={
            "submissions": [
                {"question_id": str(unknown_qid), "selected_choice_ids": [str(Q1_C2_ID)]},
            ]
        },
    )
    assert res.status_code == 422
    assert "does not belong to quiz" in res.json()["detail"]


def test_submit_unknown_choice_returns_422(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    attempt_id = start_res.json()["attempt_id"]

    unknown_cid = uuid4()
    res = client.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        json={
            "submissions": [
                {"question_id": str(Q1_ID), "selected_choice_ids": [str(unknown_cid)]},
            ]
        },
    )
    assert res.status_code == 422
    assert "not a valid choice" in res.json()["detail"]


def test_submit_duplicate_question_submission_returns_422(client):
    start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
    attempt_id = start_res.json()["attempt_id"]

    res = client.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        json={
            "submissions": [
                {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C1_ID)]},
                {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
            ]
        },
    )
    assert res.status_code == 422
    assert "duplicate submission" in res.json()["detail"].lower()


# ==============================================================================
# 4. DEPENDENCY INJECTION SEAM TEST
# ==============================================================================


def test_dependency_provider_override(client):
    """Confirm the API uses the QuizAttemptRepository dependency provider seam."""

    class MockAttemptRepo:
        def __init__(self):
            self.calls = []

        def create_attempt(self, attempt: QuizAttempt) -> QuizAttempt:
            self.calls.append(("create_attempt", attempt.attempt_id))
            return attempt

        def get_attempt(self, attempt_id: UUID) -> QuizAttempt | None:
            self.calls.append(("get_attempt", attempt_id))
            return None

        def complete_attempt(self, attempt: QuizAttempt) -> QuizAttempt:
            self.calls.append(("complete_attempt", attempt.attempt_id))
            return attempt

    mock_repo = MockAttemptRepo()
    app.dependency_overrides[get_quiz_attempt_repository] = lambda: mock_repo

    try:
        # 1. Start attempt invokes mock_repo.create_attempt
        start_res = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/attempts")
        assert start_res.status_code == 201
        assert len(mock_repo.calls) == 1
        assert mock_repo.calls[0][0] == "create_attempt"

        # 2. Get attempt invokes mock_repo.get_attempt
        get_res = client.get(f"/api/v1/attempts/{uuid4()}")
        assert get_res.status_code == 404
        assert len(mock_repo.calls) == 2
        assert mock_repo.calls[1][0] == "get_attempt"
    finally:
        app.dependency_overrides.clear()
