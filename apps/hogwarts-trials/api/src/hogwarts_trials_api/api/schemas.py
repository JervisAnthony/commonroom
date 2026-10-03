"""Public wire response and request models for Hogwarts Trials quiz API.

All response models are safe for public consumption and explicitly omit
server-owned answer keys, correct choices, and internal editorial provenance.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from hogwarts_trials_api.domain.attempt import AttemptStatus, QuizAttempt
from hogwarts_trials_api.domain.grading import QuestionResultStatus, QuizResult
from hogwarts_trials_api.domain.quiz import (
    AnswerSubmission,
    QuestionDifficulty,
    QuestionType,
)


class QuizSummaryResponse(BaseModel):
    """Safe public summary of an available quiz for discovery."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    quiz_id: UUID
    title: str
    description: str | None
    question_count: int


class QuizChoiceResponse(BaseModel):
    """Safe public representation of a question choice without correctness data."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    choice_id: UUID
    text: str


class QuizQuestionResponse(BaseModel):
    """Safe public representation of a playable quiz question without answer keys."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    position: int
    question_id: UUID
    prompt: str
    question_type: QuestionType
    difficulty: QuestionDifficulty
    choices: tuple[QuizChoiceResponse, ...]


class QuizDetailResponse(BaseModel):
    """Safe public playable representation of a complete quiz."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    quiz_id: UUID
    title: str
    description: str | None
    questions: tuple[QuizQuestionResponse, ...]


class QuizGradeRequest(BaseModel):
    """Request payload for stateless grading of submitted quiz answers."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    submissions: tuple[AnswerSubmission, ...] = ()


class QuestionGradeResponse(BaseModel):
    """Safe public evaluation outcome for an individual question.

    Indicates whether the response was correct/incorrect/unanswered and points
    awarded, but strictly omits correct answer keys or explanations.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    question_id: UUID
    status: QuestionResultStatus
    selected_choice_ids: tuple[UUID, ...]
    awarded_points: int = Field(ge=0, le=1)
    max_points: int = Field(default=1)


class QuizGradeResponse(BaseModel):
    """Safe public aggregated evaluation outcome for a graded quiz."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    quiz_id: UUID
    question_results: tuple[QuestionGradeResponse, ...]
    total_points: int = Field(ge=0)
    max_points: int = Field(ge=1)
    correct_count: int = Field(ge=0)
    incorrect_count: int = Field(ge=0)
    unanswered_count: int = Field(ge=0)


class QuizAttemptResponse(BaseModel):
    """Safe public representation of a server-owned quiz attempt."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    attempt_id: UUID
    quiz_id: UUID
    status: AttemptStatus
    result: QuizGradeResponse | None = None


def quiz_result_to_response(result: QuizResult) -> QuizGradeResponse:
    """Convert an evaluated domain QuizResult to a safe public QuizGradeResponse."""
    return QuizGradeResponse(
        quiz_id=result.quiz_id,
        question_results=tuple(
            QuestionGradeResponse(
                question_id=qr.question_id,
                status=qr.status,
                selected_choice_ids=qr.selected_choice_ids,
                awarded_points=qr.awarded_points,
                max_points=qr.max_points,
            )
            for qr in result.question_results
        ),
        total_points=result.total_points,
        max_points=result.max_points,
        correct_count=result.correct_count,
        incorrect_count=result.incorrect_count,
        unanswered_count=result.unanswered_count,
    )


def quiz_attempt_to_response(attempt: QuizAttempt) -> QuizAttemptResponse:
    """Convert a domain QuizAttempt to a safe public QuizAttemptResponse."""
    grade_response = (
        quiz_result_to_response(attempt.result)
        if attempt.result is not None
        else None
    )
    return QuizAttemptResponse(
        attempt_id=attempt.attempt_id,
        quiz_id=attempt.quiz_id,
        status=attempt.status,
        result=grade_response,
    )
