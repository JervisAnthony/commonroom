"""FastAPI dependency providers for Hogwarts Trials API.

Provides dependency injection seams for application ports, allowing routes to
depend on abstractions (such as QuizRepository) while concrete implementations
are injected at runtime and easily overridden during testing.
"""

from hogwarts_trials_api.application.quiz_repository import QuizRepository
from hogwarts_trials_api.infrastructure.in_memory_quiz_repository import (
    InMemoryQuizRepository,
)

_quiz_repository: QuizRepository = InMemoryQuizRepository()


def get_quiz_repository() -> QuizRepository:
    """Provide the application QuizRepository instance."""
    return _quiz_repository
