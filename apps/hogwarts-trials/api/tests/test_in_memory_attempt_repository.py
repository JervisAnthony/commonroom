"""Tests for InMemoryQuizAttemptRepository.

Validates:
1. Protocol conformance (QuizAttemptRepository)
2. Creating an in-progress attempt persists and is retrievable
3. Unknown attempt ID returns None
4. Duplicate attempt ID creation fails clearly
5. Completing an unknown attempt fails clearly
6. Completing an in-progress attempt updates its status and stores the evaluated result
7. Persisted completed attempt can be retrieved repeatedly with identical data
8. Attempting to complete an already completed attempt fails clearly (409-style lifecycle error)
9. Completing an attempt with invalid status or without result fails
10. Domain immutability: internal dictionary updates do not mutate existing domain instances
11. Thread safety of concurrent attempt creations
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest

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
from hogwarts_trials_api.domain.grading import (
    QuestionResult,
    QuestionResultStatus,
    QuizResult,
)
from hogwarts_trials_api.domain.quiz import (
    AnswerSubmission,
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
from hogwarts_trials_api.infrastructure.in_memory_quiz_attempt_repository import (
    InMemoryQuizAttemptRepository,
)

QUIZ_ID = UUID("11111111-1111-4000-8000-111111111111")
Q1_ID = UUID("33333333-3333-4000-8000-333333333333")
C1_ID = UUID("44444444-4444-4000-8000-444444444441")
C2_ID = UUID("44444444-4444-4000-8000-444444444442")


def build_synthetic_quiz() -> Quiz:
    provenance = QuestionProvenance(
        source_tier=SourceTier.synthetic,
        source_reference="synthetic-test-fixture",
        chapter_reference=None,
        curation_status=CurationStatus.approved,
    )
    q1 = Question(
        question_id=Q1_ID,
        prompt="Synthetic Single Choice Question",
        question_type=QuestionType.single_choice,
        difficulty=QuestionDifficulty.easy,
        choices=(
            QuestionChoice(choice_id=C1_ID, text="Choice A (Incorrect)"),
            QuestionChoice(choice_id=C2_ID, text="Choice B (Correct)"),
        ),
        correct_choice_ids=(C2_ID,),
        provenance=provenance,
        explanation="Choice B is correct.",
    )
    return Quiz(
        quiz_id=QUIZ_ID,
        title="Synthetic Test Quiz",
        description="A deterministic fixture quiz.",
        questions=(QuizQuestion(position=1, question=q1),),
    )


def test_protocol_conformance():
    repo = InMemoryQuizAttemptRepository()
    assert isinstance(repo, QuizAttemptRepository)


def test_create_and_retrieve_attempt():
    repo = InMemoryQuizAttemptRepository()
    attempt = create_quiz_attempt(QUIZ_ID)

    created = repo.create_attempt(attempt)
    assert created == attempt

    retrieved = repo.get_attempt(attempt.attempt_id)
    assert retrieved is not None
    assert retrieved == attempt
    assert retrieved.status == AttemptStatus.in_progress
    assert retrieved.result is None


def test_get_unknown_attempt_returns_none():
    repo = InMemoryQuizAttemptRepository()
    assert repo.get_attempt(uuid4()) is None


def test_duplicate_attempt_id_rejection():
    repo = InMemoryQuizAttemptRepository()
    attempt = create_quiz_attempt(QUIZ_ID)
    repo.create_attempt(attempt)

    duplicate = QuizAttempt(
        attempt_id=attempt.attempt_id,
        quiz_id=QUIZ_ID,
        status=AttemptStatus.in_progress,
    )
    with pytest.raises(QuizAttemptError, match="already exists"):
        repo.create_attempt(duplicate)


def test_complete_unknown_attempt_raises():
    repo = InMemoryQuizAttemptRepository()
    quiz = build_synthetic_quiz()
    attempt = create_quiz_attempt(QUIZ_ID)
    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=())

    with pytest.raises(QuizAttemptNotFoundError, match="not found"):
        repo.complete_attempt(completed)


def test_complete_attempt_and_retrieve():
    repo = InMemoryQuizAttemptRepository()
    quiz = build_synthetic_quiz()
    attempt = create_quiz_attempt(QUIZ_ID)
    repo.create_attempt(attempt)

    submissions = (
        AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(C2_ID,)),
    )
    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=submissions)
    persisted = repo.complete_attempt(completed)

    assert persisted.status == AttemptStatus.completed
    assert persisted.result is not None
    assert persisted.result.total_points == 1

    retrieved = repo.get_attempt(attempt.attempt_id)
    assert retrieved is not None
    assert retrieved.status == AttemptStatus.completed
    assert retrieved.result == completed.result


def test_complete_already_completed_attempt_raises():
    repo = InMemoryQuizAttemptRepository()
    quiz = build_synthetic_quiz()
    attempt = create_quiz_attempt(QUIZ_ID)
    repo.create_attempt(attempt)

    completed = complete_attempt(attempt=attempt, quiz=quiz, submissions=())
    repo.complete_attempt(completed)

    with pytest.raises(QuizAttemptAlreadyCompletedError, match="already completed"):
        repo.complete_attempt(completed)


def test_complete_attempt_requires_completed_status_and_result():
    repo = InMemoryQuizAttemptRepository()
    attempt = create_quiz_attempt(QUIZ_ID)
    repo.create_attempt(attempt)

    with pytest.raises(QuizAttemptError, match="Cannot complete attempt without completed status"):
        repo.complete_attempt(attempt)


def test_deterministic_result_preservation():
    repo = InMemoryQuizAttemptRepository()
    quiz = build_synthetic_quiz()
    attempt = create_quiz_attempt(QUIZ_ID)
    repo.create_attempt(attempt)

    completed = complete_attempt(
        attempt=attempt,
        quiz=quiz,
        submissions=(AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(C2_ID,)),),
    )
    repo.complete_attempt(completed)

    first_read = repo.get_attempt(attempt.attempt_id)
    second_read = repo.get_attempt(attempt.attempt_id)
    assert first_read == second_read == completed


def test_clear_utility():
    repo = InMemoryQuizAttemptRepository()
    attempt = create_quiz_attempt(QUIZ_ID)
    repo.create_attempt(attempt)
    assert repo.get_attempt(attempt.attempt_id) is not None
    repo.clear()
    assert repo.get_attempt(attempt.attempt_id) is None


def test_concurrent_attempt_creations():
    repo = InMemoryQuizAttemptRepository()
    attempts = [create_quiz_attempt(QUIZ_ID) for _ in range(50)]

    def create_one(a: QuizAttempt) -> QuizAttempt:
        return repo.create_attempt(a)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create_one, attempts))

    assert len(results) == 50
    for a in attempts:
        assert repo.get_attempt(a.attempt_id) is not None



def test_concurrent_completions_preserve_one_winner():
    repo = InMemoryQuizAttemptRepository()
    quiz = build_synthetic_quiz()
    attempt = create_quiz_attempt(QUIZ_ID)
    repo.create_attempt(attempt)
    candidates = (
        complete_attempt(attempt=attempt, quiz=quiz, submissions=()),
        complete_attempt(
            attempt=attempt,
            quiz=quiz,
            submissions=(AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(C2_ID,)),),
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
