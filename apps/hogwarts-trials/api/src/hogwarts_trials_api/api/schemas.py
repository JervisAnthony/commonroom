"""Public wire response and request models for Hogwarts Trials quiz API.

All response models are safe for public consumption and explicitly omit
server-owned answer keys, correct choices, and internal editorial provenance.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from hogwarts_trials_api.domain.grading import QuestionResultStatus
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
