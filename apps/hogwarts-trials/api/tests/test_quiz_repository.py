"""Tests for Hogwarts Trials quiz repository abstraction and in-memory implementation."""

from uuid import UUID, uuid4

from hogwarts_trials_api.application.quiz_repository import QuizRepository
from hogwarts_trials_api.domain.quiz import SourceTier
from hogwarts_trials_api.infrastructure.in_memory_quiz_repository import (
    DEMO_QUIZ_ID,
    InMemoryQuizRepository,
)


def test_repository_conforms_to_protocol():
    repo = InMemoryQuizRepository()
    assert isinstance(repo, QuizRepository)


def test_list_quizzes_returns_expected_synthetic_quiz():
    repo = InMemoryQuizRepository()
    quizzes = repo.list_quizzes()
    assert len(quizzes) == 1
    assert quizzes[0].quiz_id == DEMO_QUIZ_ID
    assert quizzes[0].title == "Synthetic Demonstration Quiz"
    assert len(quizzes[0].questions) == 3


def test_list_quizzes_result_type_and_order_deterministic():
    repo = InMemoryQuizRepository()
    first_call = repo.list_quizzes()
    second_call = repo.list_quizzes()
    assert isinstance(first_call, tuple)
    assert first_call == second_call
    assert [q.quiz_id for q in first_call] == [DEMO_QUIZ_ID]


def test_get_quiz_returns_expected_quiz_for_known_uuid():
    repo = InMemoryQuizRepository()
    quiz = repo.get_quiz(DEMO_QUIZ_ID)
    assert quiz is not None
    assert quiz.quiz_id == DEMO_QUIZ_ID
    assert quiz.title == "Synthetic Demonstration Quiz"


def test_get_quiz_returns_none_for_unknown_uuid():
    repo = InMemoryQuizRepository()
    unknown_id = uuid4()
    assert repo.get_quiz(unknown_id) is None


def test_repeated_list_calls_produce_equivalent_deterministic_results():
    repo = InMemoryQuizRepository()
    results = [repo.list_quizzes() for _ in range(5)]
    for r in results[1:]:
        assert r == results[0]


def test_synthetic_quiz_uses_source_tier_synthetic():
    repo = InMemoryQuizRepository()
    quiz = repo.get_quiz(DEMO_QUIZ_ID)
    assert quiz is not None
    for qq in quiz.questions:
        assert qq.question.provenance.source_tier == SourceTier.synthetic
        assert qq.question.provenance.source_reference == "synthetic-api-fixture"


def test_repository_does_not_mutate_quiz_definitions_during_reads():
    repo = InMemoryQuizRepository()
    quiz_before = repo.get_quiz(DEMO_QUIZ_ID)
    assert quiz_before is not None
    _ = repo.list_quizzes()
    quiz_after = repo.get_quiz(DEMO_QUIZ_ID)
    assert quiz_before == quiz_after
    assert quiz_before.model_dump() == quiz_after.model_dump()
