"""Tests for Hogwarts Trials quiz REST API endpoints and application catalog."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from hogwarts_trials_api.infrastructure.in_memory_quiz_repository import (
    DEMO_QUIZ_ID,
    InMemoryQuizRepository,
    Q1_C1_ID,
    Q1_C2_ID,
    Q1_ID,
    Q2_C1_ID,
    Q2_C2_ID,
    Q2_C3_ID,
    Q2_C4_ID,
    Q2_ID,
    Q3_C1_ID,
    Q3_C3_ID,
    Q3_ID,
)
from hogwarts_trials_api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def assert_key_not_in_json(data: Any, forbidden_keys: set[str]) -> None:
    """Recursively verify forbidden keys do not appear anywhere in JSON data."""
    if isinstance(data, dict):
        for k, v in data.items():
            assert k not in forbidden_keys, f"Forbidden key '{k}' found in response!"
            assert_key_not_in_json(v, forbidden_keys)
    elif isinstance(data, list):
        for item in data:
            assert_key_not_in_json(item, forbidden_keys)


# ==============================================================================
# Catalog Direct Tests (Step 31)
# ==============================================================================


def test_catalog_fixed_ids_and_retrieval():
    repo = InMemoryQuizRepository()
    quizzes = repo.list_quizzes()
    assert len(quizzes) >= 1
    demo = quizzes[0]
    assert demo.quiz_id == DEMO_QUIZ_ID

    fetched = repo.get_quiz(DEMO_QUIZ_ID)
    assert fetched is not None
    assert fetched.quiz_id == DEMO_QUIZ_ID


def test_catalog_unknown_uuid_returns_none():
    repo = InMemoryQuizRepository()
    unknown_id = uuid4()
    assert repo.get_quiz(unknown_id) is None


def test_catalog_ordering_deterministic():
    repo = InMemoryQuizRepository()
    first_list = [q.quiz_id for q in repo.list_quizzes()]
    second_list = [q.quiz_id for q in repo.list_quizzes()]
    assert first_list == second_list


# ==============================================================================
# Step 27: List Endpoint Tests (1 - 7)
# ==============================================================================


def test_list_quizzes_returns_200(client: TestClient):
    response = client.get("/api/v1/quizzes")
    assert response.status_code == 200


def test_list_quizzes_response_is_deterministic(client: TestClient):
    res1 = client.get("/api/v1/quizzes").json()
    res2 = client.get("/api/v1/quizzes").json()
    assert res1 == res2


def test_list_quizzes_known_synthetic_quiz_appears(client: TestClient):
    response = client.get("/api/v1/quizzes")
    quizzes = response.json()
    demo_matches = [q for q in quizzes if q["quiz_id"] == str(DEMO_QUIZ_ID)]
    assert len(demo_matches) == 1
    demo = demo_matches[0]
    assert demo["title"] == "Synthetic Demonstration Quiz"
    assert demo["description"] is not None


def test_list_quizzes_question_count_is_correct(client: TestClient):
    response = client.get("/api/v1/quizzes")
    quizzes = response.json()
    demo = next(q for q in quizzes if q["quiz_id"] == str(DEMO_QUIZ_ID))
    assert demo["question_count"] == 3


def test_list_quizzes_does_not_contain_correct_choice_ids(client: TestClient):
    response = client.get("/api/v1/quizzes")
    assert_key_not_in_json(response.json(), {"correct_choice_ids"})


def test_list_quizzes_does_not_contain_explanation(client: TestClient):
    response = client.get("/api/v1/quizzes")
    assert_key_not_in_json(response.json(), {"explanation"})


def test_list_quizzes_does_not_contain_provenance(client: TestClient):
    response = client.get("/api/v1/quizzes")
    assert_key_not_in_json(
        response.json(),
        {"provenance", "source_tier", "source_reference", "chapter_reference", "curation_status"},
    )


# ==============================================================================
# Step 28: Detail Endpoint Tests (8 - 24)
# ==============================================================================


def test_detail_known_quiz_returns_200(client: TestClient):
    response = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
    assert response.status_code == 200


def test_detail_expected_quiz_metadata_returned(client: TestClient):
    response = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
    data = response.json()
    assert data["quiz_id"] == str(DEMO_QUIZ_ID)
    assert data["title"] == "Synthetic Demonstration Quiz"
    assert "questions" in data


def test_detail_expected_number_of_questions_returned(client: TestClient):
    response = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
    data = response.json()
    assert len(data["questions"]) == 3


def test_detail_questions_follow_deterministic_position_order(client: TestClient):
    response = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
    data = response.json()
    positions = [q["position"] for q in data["questions"]]
    assert positions == [1, 2, 3]


def test_detail_question_fields_exposed(client: TestClient):
    response = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
    q1 = response.json()["questions"][0]
    assert q1["question_id"] == str(Q1_ID)
    assert q1["prompt"] == "What is the result of 2 + 2?"
    assert q1["question_type"] == "single_choice"
    assert q1["difficulty"] == "easy"
    assert len(q1["choices"]) == 4
    for choice in q1["choices"]:
        assert "choice_id" in choice
        assert "text" in choice


def test_detail_security_exclusions_recursively(client: TestClient):
    response = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
    forbidden = {
        "correct_choice_ids",
        "explanation",
        "provenance",
        "source_tier",
        "source_reference",
        "chapter_reference",
        "curation_status",
    }
    assert_key_not_in_json(response.json(), forbidden)


def test_detail_unknown_quiz_uuid_returns_404(client: TestClient):
    unknown_id = uuid4()
    response = client.get(f"/api/v1/quizzes/{unknown_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Quiz not found"


def test_detail_malformed_uuid_path_returns_422(client: TestClient):
    response = client.get("/api/v1/quizzes/not-a-valid-uuid")
    assert response.status_code == 422


# ==============================================================================
# Step 29: Grading Endpoint Tests (25 - 47)
# ==============================================================================


def test_grade_all_correct_returns_expected_score(client: TestClient):
    payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
            {
                "question_id": str(Q2_ID),
                "selected_choice_ids": [str(Q2_C1_ID), str(Q2_C3_ID)],
            },
            {"question_id": str(Q3_ID), "selected_choice_ids": [str(Q3_C3_ID)]},
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_points"] == 3
    assert data["max_points"] == 3
    assert data["correct_count"] == 3
    assert data["incorrect_count"] == 0
    assert data["unanswered_count"] == 0


def test_grade_mixed_correct_incorrect(client: TestClient):
    payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},  # correct
            {
                "question_id": str(Q2_ID),
                "selected_choice_ids": [str(Q2_C2_ID), str(Q2_C4_ID)],  # incorrect
            },
            {"question_id": str(Q3_ID), "selected_choice_ids": [str(Q3_C1_ID)]},  # incorrect
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_points"] == 1
    assert data["max_points"] == 3
    assert data["correct_count"] == 1
    assert data["incorrect_count"] == 2
    assert data["unanswered_count"] == 0


def test_grade_omitted_question_becomes_unanswered(client: TestClient):
    payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_points"] == 1
    assert data["max_points"] == 3
    assert data["correct_count"] == 1
    assert data["incorrect_count"] == 0
    assert data["unanswered_count"] == 2

    # Verify statuses of individual questions
    q_results = {r["question_id"]: r for r in data["question_results"]}
    assert q_results[str(Q1_ID)]["status"] == "correct"
    assert q_results[str(Q2_ID)]["status"] == "unanswered"
    assert q_results[str(Q3_ID)]["status"] == "unanswered"


def test_grade_empty_submissions_produces_all_unanswered(client: TestClient):
    payload = {"submissions": []}
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_points"] == 0
    assert data["max_points"] == 3
    assert data["correct_count"] == 0
    assert data["incorrect_count"] == 0
    assert data["unanswered_count"] == 3


def test_grade_multiple_choice_exact_set_succeeds(client: TestClient):
    payload = {
        "submissions": [
            {
                "question_id": str(Q2_ID),
                "selected_choice_ids": [str(Q2_C1_ID), str(Q2_C3_ID)],
            }
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    q2_res = next(r for r in data["question_results"] if r["question_id"] == str(Q2_ID))
    assert q2_res["status"] == "correct"
    assert q2_res["awarded_points"] == 1


def test_grade_multiple_choice_selection_order_does_not_affect_correctness(client: TestClient):
    payload = {
        "submissions": [
            {
                "question_id": str(Q2_ID),
                "selected_choice_ids": [str(Q2_C3_ID), str(Q2_C1_ID)],  # Reversed
            }
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    q2_res = next(r for r in data["question_results"] if r["question_id"] == str(Q2_ID))
    assert q2_res["status"] == "correct"


def test_grade_multiple_choice_subset_selection_is_incorrect(client: TestClient):
    payload = {
        "submissions": [
            {
                "question_id": str(Q2_ID),
                "selected_choice_ids": [str(Q2_C1_ID)],  # Only one of two
            }
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    q2_res = next(r for r in data["question_results"] if r["question_id"] == str(Q2_ID))
    assert q2_res["status"] == "incorrect"
    assert q2_res["awarded_points"] == 0


def test_grade_multiple_choice_with_additional_incorrect_choice(client: TestClient):
    payload = {
        "submissions": [
            {
                "question_id": str(Q2_ID),
                "selected_choice_ids": [str(Q2_C1_ID), str(Q2_C3_ID), str(Q2_C2_ID)],
            }
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    q2_res = next(r for r in data["question_results"] if r["question_id"] == str(Q2_ID))
    assert q2_res["status"] == "incorrect"


def test_grade_unknown_selected_choice_id_returns_422(client: TestClient):
    payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(uuid4())]}
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 422
    assert "not a valid choice" in response.json()["detail"]


def test_grade_duplicate_question_submissions_return_422(client: TestClient):
    payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C1_ID)]},
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 422
    assert "Duplicate submission detected" in response.json()["detail"]


def test_grade_submission_for_question_outside_target_quiz_returns_422(client: TestClient):
    payload = {
        "submissions": [
            {"question_id": str(uuid4()), "selected_choice_ids": [str(Q1_C1_ID)]}
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 422
    assert "does not belong to quiz" in response.json()["detail"]


def test_grade_request_extra_fields_rejected(client: TestClient):
    payload = {
        "submissions": [],
        "extra_field": "disallowed",
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 422


def test_grade_nested_answer_submission_extra_fields_rejected(client: TestClient):
    payload = {
        "submissions": [
            {
                "question_id": str(Q1_ID),
                "selected_choice_ids": [str(Q1_C2_ID)],
                "client_reported_score": 100,
            }
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 422


def test_grade_response_excludes_answer_keys_and_explanations(client: TestClient):
    payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]}
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    forbidden = {
        "correct_choice_ids",
        "explanation",
        "provenance",
        "source_tier",
        "source_reference",
        "chapter_reference",
        "curation_status",
    }
    assert_key_not_in_json(response.json(), forbidden)


def test_grade_result_order_follows_quiz_question_position(client: TestClient):
    # Submit questions in reverse order
    payload = {
        "submissions": [
            {"question_id": str(Q3_ID), "selected_choice_ids": [str(Q3_C3_ID)]},
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
        ]
    }
    response = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload)
    assert response.status_code == 200
    data = response.json()
    result_qids = [r["question_id"] for r in data["question_results"]]
    assert result_qids == [str(Q1_ID), str(Q2_ID), str(Q3_ID)]


def test_grade_repeated_identical_requests_produce_identical_json(client: TestClient):
    payload = {
        "submissions": [
            {"question_id": str(Q1_ID), "selected_choice_ids": [str(Q1_C2_ID)]},
            {"question_id": str(Q2_ID), "selected_choice_ids": [str(Q2_C1_ID), str(Q2_C3_ID)]},
        ]
    }
    res1 = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload).json()
    res2 = client.post(f"/api/v1/quizzes/{DEMO_QUIZ_ID}/grade", json=payload).json()
    assert res1 == res2


def test_grade_unknown_quiz_uuid_returns_404(client: TestClient):
    unknown_id = uuid4()
    payload = {"submissions": []}
    response = client.post(f"/api/v1/quizzes/{unknown_id}/grade", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Quiz not found"


# ==============================================================================
# Step 33: OpenAPI Registration
# ==============================================================================


def test_openapi_route_registration(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/quizzes" in paths
    assert "get" in paths["/api/v1/quizzes"]
    assert "/api/v1/quizzes/{quiz_id}" in paths
    assert "get" in paths["/api/v1/quizzes/{quiz_id}"]
    assert "/api/v1/quizzes/{quiz_id}/grade" in paths
    assert "post" in paths["/api/v1/quizzes/{quiz_id}/grade"]
    assert "/api/v1/health" in paths


# ==============================================================================
# Commit 11: Repository Dependency-Injection Boundary Test
# ==============================================================================


def test_api_uses_repository_dependency_override(client: TestClient):
    """Verify that API endpoints consume QuizRepository via FastAPI dependency injection."""
    from hogwarts_trials_api.api.dependencies import get_quiz_repository
    from hogwarts_trials_api.domain.quiz import (
        CurationStatus,
        Question,
        QuestionChoice,
        QuestionDifficulty,
        QuestionProvenance,
        QuestionType,
        Quiz,
        QuizQuestion,
        SourceTier,
    )

    alt_quiz_id = UUID("00000000-0000-4000-8000-000000000099")
    alt_q_id = UUID("00000000-0000-4000-8000-000000000091")
    alt_c1_id = UUID("00000000-0000-4000-8000-000000000092")
    alt_c2_id = UUID("00000000-0000-4000-8000-000000000093")

    alt_quiz = Quiz(
        quiz_id=alt_quiz_id,
        title="Alternate Injected Test Quiz",
        description="A distinct quiz used solely to test dependency injection.",
        questions=(
            QuizQuestion(
                position=1,
                question=Question(
                    question_id=alt_q_id,
                    prompt="What is 10 + 10?",
                    question_type=QuestionType.single_choice,
                    difficulty=QuestionDifficulty.easy,
                    choices=(
                        QuestionChoice(choice_id=alt_c1_id, text="20"),
                        QuestionChoice(choice_id=alt_c2_id, text="30"),
                    ),
                    correct_choice_ids=(alt_c1_id,),
                    provenance=QuestionProvenance(
                        source_tier=SourceTier.synthetic,
                        source_reference="dependency-override-fixture",
                        chapter_reference=None,
                        curation_status=CurationStatus.approved,
                    ),
                    explanation="Ten plus ten is twenty.",
                ),
            ),
        ),
    )

    alt_repo = InMemoryQuizRepository(quizzes=(alt_quiz,))

    app.dependency_overrides[get_quiz_repository] = lambda: alt_repo
    try:
        # 1. Verify list endpoint returns overridden repository's quiz
        list_resp = client.get("/api/v1/quizzes")
        assert list_resp.status_code == 200
        quizzes = list_resp.json()
        assert len(quizzes) == 1
        assert quizzes[0]["quiz_id"] == str(alt_quiz_id)
        assert quizzes[0]["title"] == "Alternate Injected Test Quiz"

        # 2. Verify detail endpoint retrieves from overridden repository
        detail_resp = client.get(f"/api/v1/quizzes/{alt_quiz_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["quiz_id"] == str(alt_quiz_id)
        assert detail_data["title"] == "Alternate Injected Test Quiz"
        assert len(detail_data["questions"]) == 1

        # 3. Verify grading endpoint grades against overridden repository
        grade_resp = client.post(
            f"/api/v1/quizzes/{alt_quiz_id}/grade",
            json={
                "submissions": [
                    {
                        "question_id": str(alt_q_id),
                        "selected_choice_ids": [str(alt_c1_id)],
                    }
                ]
            },
        )
        assert grade_resp.status_code == 200
        assert grade_resp.json()["total_points"] == 1
        assert grade_resp.json()["correct_count"] == 1

        # 4. Verify default DEMO_QUIZ_ID is now 404 under overridden repo
        old_resp = client.get(f"/api/v1/quizzes/{DEMO_QUIZ_ID}")
        assert old_resp.status_code == 404
    finally:
        app.dependency_overrides.clear()

    # Confirm restoration of default repository behavior
    restored_resp = client.get("/api/v1/quizzes")
    assert restored_resp.status_code == 200
    assert any(q["quiz_id"] == str(DEMO_QUIZ_ID) for q in restored_resp.json())
