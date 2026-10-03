"""Tests for Hogwarts Trials server-owned quiz attempt domain models and lifecycle operations.

Covers:
1. Valid in-progress attempt initialization
2. In-progress attempt rejects a result
3. Completed attempt requires a result
4. Completed attempt result quiz_id must match attempt quiz_id
5. create_quiz_attempt generates UUID v4 server-side and initializes in_progress attempt
6. complete_attempt delegates to deterministic grading semantics
7. complete_attempt produces a new immutable completed QuizAttempt
8. Original in-progress attempt remains unchanged (immutability)
9. Completing an already-completed attempt raises QuizAttemptAlreadyCompletedError
10. Completing with a mismatched quiz raises QuizAttemptMismatchError
11. Preserves exact answer submission evaluations and question scores
12. Forbids extra attributes on models
"""

from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest

from hogwarts_trials_api.domain.attempt import (
    AttemptStatus,
    QuizAttempt,
    QuizAttemptAlreadyCompletedError,
    QuizAttemptError,
    QuizAttemptMismatchError,
    complete_attempt,
    create_quiz_attempt,
)
from hogwarts_trials_api.domain.grading import (
    QuestionResult,
    QuestionResultStatus,
    QuizGradingError,
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

# Deterministic test fixtures
QUIZ_ID = UUID("11111111-1111-4000-8000-111111111111")
OTHER_QUIZ_ID = UUID("99999999-9999-4000-8000-999999999999")
ATTEMPT_ID = UUID("22222222-2222-4000-8000-222222222222")

Q1_ID = UUID("33333333-3333-4000-8000-333333333333")
C1_ID = UUID("44444444-4444-4000-8000-444444444441")
C2_ID = UUID("44444444-4444-4000-8000-444444444442")

Q2_ID = UUID("55555555-5555-4000-8000-555555555555")
C3_ID = UUID("66666666-6666-4000-8000-666666666661")
C4_ID = UUID("66666666-6666-4000-8000-666666666662")


def build_synthetic_quiz(quiz_id: UUID = QUIZ_ID) -> Quiz:
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
    q2 = Question(
        question_id=Q2_ID,
        prompt="Synthetic Second Single Choice Question",
        question_type=QuestionType.single_choice,
        difficulty=QuestionDifficulty.medium,
        choices=(
            QuestionChoice(choice_id=C3_ID, text="Choice C (Correct)"),
            QuestionChoice(choice_id=C4_ID, text="Choice D (Incorrect)"),
        ),
        correct_choice_ids=(C3_ID,),
        provenance=provenance,
        explanation="Choice C is correct.",
    )
    return Quiz(
        quiz_id=quiz_id,
        title="Synthetic Test Quiz",
        description="A deterministic fixture quiz.",
        questions=(
            QuizQuestion(position=1, question=q1),
            QuizQuestion(position=2, question=q2),
        ),
    )


def build_dummy_quiz_result(quiz_id: UUID = QUIZ_ID) -> QuizResult:
    qr1 = QuestionResult(
        question_id=Q1_ID,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(C2_ID,),
        correct_choice_ids=(C2_ID,),
        awarded_points=1,
        max_points=1,
    )
    return QuizResult(
        quiz_id=quiz_id,
        question_results=(qr1,),
        total_points=1,
        max_points=1,
        correct_count=1,
        incorrect_count=0,
        unanswered_count=0,
    )


# ==============================================================================
# 1. ATTEMPT STATUS & DOMAIN INVARIANTS
# ==============================================================================


def test_attempt_status_values():
    assert AttemptStatus.in_progress == "in_progress"
    assert AttemptStatus.completed == "completed"
    assert len(AttemptStatus) == 2


def test_valid_in_progress_attempt():
    attempt = QuizAttempt(
        attempt_id=ATTEMPT_ID,
        quiz_id=QUIZ_ID,
        status=AttemptStatus.in_progress,
        result=None,
    )
    assert attempt.attempt_id == ATTEMPT_ID
    assert attempt.quiz_id == QUIZ_ID
    assert attempt.status == AttemptStatus.in_progress
    assert attempt.result is None


def test_in_progress_attempt_rejects_result():
    dummy_result = build_dummy_quiz_result(QUIZ_ID)
    with pytest.raises((QuizAttemptError, ValidationError), match="cannot contain a result"):
        QuizAttempt(
            attempt_id=ATTEMPT_ID,
            quiz_id=QUIZ_ID,
            status=AttemptStatus.in_progress,
            result=dummy_result,
        )


def test_completed_attempt_requires_result():
    with pytest.raises((QuizAttemptError, ValidationError), match="must contain a result"):
        QuizAttempt(
            attempt_id=ATTEMPT_ID,
            quiz_id=QUIZ_ID,
            status=AttemptStatus.completed,
            result=None,
        )


def test_completed_attempt_result_quiz_id_must_match():
    mismatched_result = build_dummy_quiz_result(OTHER_QUIZ_ID)
    with pytest.raises((QuizAttemptError, ValidationError), match="does not match attempt quiz_id"):
        QuizAttempt(
            attempt_id=ATTEMPT_ID,
            quiz_id=QUIZ_ID,
            status=AttemptStatus.completed,
            result=mismatched_result,
        )


def test_valid_completed_attempt():
    valid_result = build_dummy_quiz_result(QUIZ_ID)
    attempt = QuizAttempt(
        attempt_id=ATTEMPT_ID,
        quiz_id=QUIZ_ID,
        status=AttemptStatus.completed,
        result=valid_result,
    )
    assert attempt.status == AttemptStatus.completed
    assert attempt.result == valid_result


def test_quiz_attempt_is_frozen_and_forbids_extra():
    attempt = QuizAttempt(
        attempt_id=ATTEMPT_ID,
        quiz_id=QUIZ_ID,
        status=AttemptStatus.in_progress,
    )
    with pytest.raises(Exception):
        attempt.status = AttemptStatus.completed  # type: ignore[misc]

    with pytest.raises(Exception):
        QuizAttempt(
            attempt_id=ATTEMPT_ID,
            quiz_id=QUIZ_ID,
            status=AttemptStatus.in_progress,
            extra_field="disallowed",  # type: ignore[call-arg]
        )


# ==============================================================================
# 2. START ATTEMPT (create_quiz_attempt)
# ==============================================================================


def test_create_quiz_attempt_defaults_to_uuid4():
    attempt = create_quiz_attempt(QUIZ_ID)
    assert isinstance(attempt.attempt_id, UUID)
    assert attempt.attempt_id.version == 4
    assert attempt.quiz_id == QUIZ_ID
    assert attempt.status == AttemptStatus.in_progress
    assert attempt.result is None


def test_create_quiz_attempt_accepts_custom_id_factory():
    custom_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    attempt = create_quiz_attempt(QUIZ_ID, attempt_id_factory=lambda: custom_id)
    assert attempt.attempt_id == custom_id
    assert attempt.quiz_id == QUIZ_ID
    assert attempt.status == AttemptStatus.in_progress


# ==============================================================================
# 3. COMPLETE ATTEMPT (complete_attempt)
# ==============================================================================


def test_complete_attempt_delegates_to_deterministic_grading():
    quiz = build_synthetic_quiz()
    in_progress = create_quiz_attempt(quiz.quiz_id)

    submissions = (
        AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(C2_ID,)),  # correct
        AnswerSubmission(question_id=Q2_ID, selected_choice_ids=(C4_ID,)),  # incorrect
    )

    completed = complete_attempt(
        attempt=in_progress,
        quiz=quiz,
        submissions=submissions,
    )

    assert completed.attempt_id == in_progress.attempt_id
    assert completed.quiz_id == in_progress.quiz_id
    assert completed.status == AttemptStatus.completed
    assert completed.result is not None
    assert completed.result.quiz_id == quiz.quiz_id
    assert completed.result.total_points == 1
    assert completed.result.max_points == 2
    assert completed.result.correct_count == 1
    assert completed.result.incorrect_count == 1
    assert completed.result.unanswered_count == 0


def test_complete_attempt_produces_new_immutable_instance():
    quiz = build_synthetic_quiz()
    in_progress = create_quiz_attempt(quiz.quiz_id)

    completed = complete_attempt(
        attempt=in_progress,
        quiz=quiz,
        submissions=(),
    )

    # Original attempt is unchanged
    assert in_progress.status == AttemptStatus.in_progress
    assert in_progress.result is None

    # New completed instance is distinct and completed
    assert completed is not in_progress
    assert completed.status == AttemptStatus.completed
    assert completed.result is not None
    assert completed.result.unanswered_count == 2


def test_complete_attempt_raises_if_already_completed():
    quiz = build_synthetic_quiz()
    in_progress = create_quiz_attempt(quiz.quiz_id)
    completed = complete_attempt(attempt=in_progress, quiz=quiz, submissions=())

    with pytest.raises(QuizAttemptAlreadyCompletedError, match="already completed"):
        complete_attempt(attempt=completed, quiz=quiz, submissions=())


def test_complete_attempt_raises_if_quiz_mismatched():
    quiz1 = build_synthetic_quiz(QUIZ_ID)
    quiz2 = build_synthetic_quiz(OTHER_QUIZ_ID)
    in_progress = create_quiz_attempt(quiz1.quiz_id)

    with pytest.raises(QuizAttemptMismatchError, match="does not match"):
        complete_attempt(attempt=in_progress, quiz=quiz2, submissions=())


def test_complete_attempt_propagates_grading_errors():
    quiz = build_synthetic_quiz()
    in_progress = create_quiz_attempt(quiz.quiz_id)

    unknown_choice = uuid4()
    invalid_submissions = (
        AnswerSubmission(question_id=Q1_ID, selected_choice_ids=(unknown_choice,)),
    )

    with pytest.raises(QuizGradingError, match="is not a valid choice"):
        complete_attempt(
            attempt=in_progress,
            quiz=quiz,
            submissions=invalid_submissions,
        )
