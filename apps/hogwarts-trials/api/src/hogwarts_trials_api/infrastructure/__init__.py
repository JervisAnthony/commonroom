"""Infrastructure layer package for Hogwarts Trials API."""

from hogwarts_trials_api.infrastructure.in_memory_quiz_attempt_repository import (
    InMemoryQuizAttemptRepository,
)
from hogwarts_trials_api.infrastructure.in_memory_quiz_repository import (
    InMemoryQuizRepository,
)
from hogwarts_trials_api.infrastructure.postgres_quiz_attempt_repository import (
    PostgresQuizAttemptRepository,
)
from hogwarts_trials_api.infrastructure.postgres_quiz_repository import (
    PostgresQuizRepository,
)

__all__ = [
    "InMemoryQuizAttemptRepository",
    "InMemoryQuizRepository",
    "PostgresQuizAttemptRepository",
    "PostgresQuizRepository",
]
