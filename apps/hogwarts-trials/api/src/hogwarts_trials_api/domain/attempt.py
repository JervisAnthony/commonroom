"""Hogwarts Trials server-owned quiz attempt domain models and lifecycle rules.

Defines the immutable QuizAttempt aggregate, attempt lifecycle states, and pure
domain operations for starting and completing server-owned quiz attempts.
"""

from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, model_validator

from hogwarts_trials_api.domain.grading import QuizResult, grade_quiz
from hogwarts_trials_api.domain.quiz import AnswerSubmission, Quiz


class AttemptStatus(StrEnum):
    """Authoritative server-side lifecycle state for a quiz attempt."""

    in_progress = "in_progress"
    completed = "completed"


class QuizAttemptError(ValueError):
    """Base domain error for quiz attempt lifecycle and validation errors."""

    pass


class QuizAttemptNotFoundError(QuizAttemptError):
    """Raised when an attempt cannot be found."""

    pass


class QuizAttemptAlreadyCompletedError(QuizAttemptError):
    """Raised when attempting to modify or complete an already-completed attempt."""

    pass


class QuizAttemptMismatchError(QuizAttemptError):
    """Raised when an attempt does not correspond to the targeted quiz."""

    pass


class QuizAttempt(BaseModel):
    """Immutable server-owned quiz attempt aggregate.

    Represents an authoritative session boundary for taking a quiz.
    Timestamps, user identity, and timer deadlines are intentionally deferred.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    attempt_id: UUID
    quiz_id: UUID
    status: AttemptStatus
    result: QuizResult | None = None

    @model_validator(mode="after")
    def validate_attempt_invariants(self) -> Self:
        """Enforce domain invariants across attempt lifecycle states."""
        if self.status == AttemptStatus.in_progress:
            if self.result is not None:
                raise QuizAttemptError(
                    "In-progress quiz attempt cannot contain a result"
                )
        elif self.status == AttemptStatus.completed:
            if self.result is None:
                raise QuizAttemptError(
                    "Completed quiz attempt must contain a result"
                )
            if self.result.quiz_id != self.quiz_id:
                raise QuizAttemptMismatchError(
                    f"Result quiz_id ({self.result.quiz_id}) does not match "
                    f"attempt quiz_id ({self.quiz_id})"
                )
        return self


def create_quiz_attempt(
    quiz_id: UUID,
    attempt_id_factory: Callable[[], UUID] = uuid4,
) -> QuizAttempt:
    """Create a new in-progress server-owned quiz attempt with a generated UUID v4."""
    return QuizAttempt(
        attempt_id=attempt_id_factory(),
        quiz_id=quiz_id,
        status=AttemptStatus.in_progress,
        result=None,
    )


def complete_attempt(
    attempt: QuizAttempt,
    quiz: Quiz,
    submissions: Sequence[AnswerSubmission] = (),
) -> QuizAttempt:
    """Complete an in-progress quiz attempt by delegating to the deterministic grading engine.

    Returns a new immutable completed QuizAttempt containing the evaluated QuizResult.
    The original attempt is not mutated.

    Raises:
        QuizAttemptAlreadyCompletedError: If the attempt is already completed.
        QuizAttemptMismatchError: If the attempt does not match the quiz ID.
        QuizGradingError: If answer submissions violate contextual grading rules.
    """
    if attempt.status != AttemptStatus.in_progress:
        raise QuizAttemptAlreadyCompletedError(
            f"Attempt {attempt.attempt_id} is already completed and cannot be completed again"
        )

    if attempt.quiz_id != quiz.quiz_id:
        raise QuizAttemptMismatchError(
            f"Attempt quiz_id ({attempt.quiz_id}) does not match "
            f"quiz.quiz_id ({quiz.quiz_id})"
        )

    result = grade_quiz(quiz=quiz, submissions=submissions)

    return QuizAttempt(
        attempt_id=attempt.attempt_id,
        quiz_id=attempt.quiz_id,
        status=AttemptStatus.completed,
        result=result,
    )
