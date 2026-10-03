"""Application-layer repository abstraction for quiz attempt persistence.

Defines the QuizAttemptRepository protocol connecting the API and application layers
to infrastructure persistence implementations without coupling domain or application
logic to concrete storage engines.
"""

from typing import Protocol, runtime_checkable
from uuid import UUID

from hogwarts_trials_api.domain.attempt import QuizAttempt


@runtime_checkable
class QuizAttemptRepository(Protocol):
    """Repository interface for quiz attempt lifecycle persistence."""

    def create_attempt(self, attempt: QuizAttempt) -> QuizAttempt:
        """Persist a newly started in-progress quiz attempt.

        Raises:
            QuizAttemptError: If an attempt with the same attempt_id already exists.
        """
        ...

    def get_attempt(self, attempt_id: UUID) -> QuizAttempt | None:
        """Retrieve a quiz attempt by its unique identifier, or None if not found."""
        ...

    def complete_attempt(self, attempt: QuizAttempt) -> QuizAttempt:
        """Atomically persist a completed attempt and its evaluated result snapshot.

        Raises:
            QuizAttemptNotFoundError: If the attempt does not exist in the repository.
            QuizAttemptAlreadyCompletedError: If the attempt has already been completed.
            QuizAttemptError: If the attempt is invalid or missing completion data.
        """
        ...
