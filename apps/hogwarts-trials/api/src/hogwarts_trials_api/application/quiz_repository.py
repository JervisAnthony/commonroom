"""Application-layer repository abstraction for quiz retrieval.

Defines the read-only QuizRepository protocol connecting the API and application
layers to infrastructure persistence implementations without coupling domain or
application logic to concrete storage engines.
"""

from typing import Protocol, runtime_checkable
from uuid import UUID

from hogwarts_trials_api.domain.quiz import Quiz


@runtime_checkable
class QuizRepository(Protocol):
    """Read-only repository interface for quiz retrieval."""

    def list_quizzes(self) -> tuple[Quiz, ...]:
        """Retrieve all available quizzes in deterministic order."""
        ...

    def get_quiz(self, quiz_id: UUID) -> Quiz | None:
        """Retrieve a specific quiz by its unique identifier, or None if not found."""
        ...
