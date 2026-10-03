"""In-memory quiz attempt repository for Hogwarts Trials API.

Provides a thread-safe in-memory implementation of the QuizAttemptRepository protocol
for local development, testing, and memory backend operation.
"""

from threading import Lock
from uuid import UUID

from hogwarts_trials_api.application.quiz_attempt_repository import (
    QuizAttemptRepository,
)
from hogwarts_trials_api.domain.attempt import (
    AttemptStatus,
    QuizAttempt,
    QuizAttemptAlreadyCompletedError,
    QuizAttemptError,
    QuizAttemptNotFoundError,
)


class InMemoryQuizAttemptRepository:
    """Thread-safe in-memory store for server-owned quiz attempts."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._attempts: dict[UUID, QuizAttempt] = {}

    def create_attempt(self, attempt: QuizAttempt) -> QuizAttempt:
        """Persist a new in-progress attempt.

        Raises:
            QuizAttemptError: If an attempt with this ID already exists.
        """
        with self._lock:
            if attempt.attempt_id in self._attempts:
                raise QuizAttemptError(
                    f"Attempt with ID {attempt.attempt_id} already exists"
                )
            self._attempts[attempt.attempt_id] = attempt
            return attempt

    def get_attempt(self, attempt_id: UUID) -> QuizAttempt | None:
        """Retrieve an attempt by its ID, or None if not found."""
        with self._lock:
            return self._attempts.get(attempt_id)

    def complete_attempt(self, attempt: QuizAttempt) -> QuizAttempt:
        """Record the completion of an in-progress attempt.

        Raises:
            QuizAttemptNotFoundError: If the attempt does not exist.
            QuizAttemptAlreadyCompletedError: If the attempt is already completed.
            QuizAttemptError: If the attempt payload is not in completed state or lacks a result.
        """
        if attempt.status != AttemptStatus.completed or attempt.result is None:
            raise QuizAttemptError(
                "Cannot complete attempt without completed status and an evaluated result"
            )

        with self._lock:
            existing = self._attempts.get(attempt.attempt_id)
            if existing is None:
                raise QuizAttemptNotFoundError(
                    f"Attempt with ID {attempt.attempt_id} not found"
                )
            if existing.status == AttemptStatus.completed:
                raise QuizAttemptAlreadyCompletedError(
                    f"Attempt with ID {attempt.attempt_id} is already completed"
                )

            self._attempts[attempt.attempt_id] = attempt
            return attempt

    def clear(self) -> None:
        """Remove all stored attempts (utility for testing isolation)."""
        with self._lock:
            self._attempts.clear()


# Compile-time protocol conformance check
_: QuizAttemptRepository = InMemoryQuizAttemptRepository()
