"""Application layer package for Hogwarts Trials API."""

from hogwarts_trials_api.application.quiz_attempt_repository import (
    QuizAttemptRepository,
)
from hogwarts_trials_api.application.quiz_repository import QuizRepository

__all__ = [
    "QuizAttemptRepository",
    "QuizRepository",
]
