"""Domain layer package for Hogwarts Trials API."""

from hogwarts_trials_api.domain.attempt import (
    AttemptStatus,
    QuizAttempt,
    QuizAttemptAlreadyCompletedError,
    QuizAttemptError,
    QuizAttemptMismatchError,
    QuizAttemptNotFoundError,
    complete_attempt,
    create_quiz_attempt,
)
from hogwarts_trials_api.domain.grading import (
    QuestionResult,
    QuestionResultStatus,
    QuizGradingError,
    QuizResult,
    grade_question,
    grade_quiz,
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

__all__ = [
    "AnswerSubmission",
    "AttemptStatus",
    "CurationStatus",
    "Question",
    "QuestionChoice",
    "QuestionDifficulty",
    "QuestionProvenance",
    "QuestionResult",
    "QuestionResultStatus",
    "QuestionType",
    "Quiz",
    "QuizAttempt",
    "QuizAttemptAlreadyCompletedError",
    "QuizAttemptError",
    "QuizAttemptMismatchError",
    "QuizAttemptNotFoundError",
    "QuizGradingError",
    "QuizQuestion",
    "QuizResult",
    "SourceTier",
    "complete_attempt",
    "create_quiz_attempt",
    "grade_question",
    "grade_quiz",
]
