"""Hogwarts Trials quiz domain contracts and models.

Defines the typed, validated domain models representing questions, choices,
provenance metadata, quiz structure, and answer submissions.
"""

from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuestionType(StrEnum):
    """Categorization of quiz question response mechanics."""

    single_choice = "single_choice"
    multiple_choice = "multiple_choice"


class QuestionDifficulty(StrEnum):
    """Editorial classification of question difficulty."""

    easy = "easy"
    medium = "medium"
    hard = "hard"


class SourceTier(StrEnum):
    """Canonical provenance classification for curated questions and synthetic fixtures.

    Values:
        book_canon: Authentic canonical literature content.
        screen_adaptation: Screen/film adaptation material.
        official_expanded: Officially licensed expanded franchise material.
        synthetic: Original synthetic development/test/demo material rather than canonical production content.
    """

    book_canon = "book_canon"
    screen_adaptation = "screen_adaptation"
    official_expanded = "official_expanded"
    synthetic = "synthetic"


class CurationStatus(StrEnum):
    """Editorial lifecycle state for a curated question."""

    draft = "draft"
    reviewed = "reviewed"
    approved = "approved"


class QuestionProvenance(BaseModel):
    """Metadata detailing the origin and editorial status of a question."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    source_tier: SourceTier
    source_reference: str = Field(min_length=1, max_length=255)
    chapter_reference: str | None = Field(default=None, max_length=255)
    curation_status: CurationStatus

    @field_validator("source_reference")
    @classmethod
    def validate_source_reference(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("source_reference must not be blank")
        return v.strip()

    @field_validator("chapter_reference")
    @classmethod
    def validate_chapter_reference(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("chapter_reference cannot be blank if provided")
            return stripped
        return v


class QuestionChoice(BaseModel):
    """An individual response choice available on a question."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    choice_id: UUID
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("choice text must not be blank")
        return v.strip()


class Question(BaseModel):
    """A fully-formed quiz question with choices, answer key, and provenance."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    question_id: UUID
    prompt: str = Field(min_length=1, max_length=1000)
    question_type: QuestionType
    difficulty: QuestionDifficulty
    choices: tuple[QuestionChoice, ...]
    correct_choice_ids: tuple[UUID, ...]
    provenance: QuestionProvenance
    explanation: str | None = Field(default=None, max_length=2000)

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("prompt must not be blank")
        return v.strip()

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("explanation cannot be blank if provided")
            return stripped
        return v

    @model_validator(mode="after")
    def validate_question_invariants(self) -> Self:
        if len(self.choices) < 2:
            raise ValueError("A question must contain at least 2 choices")
        if len(self.choices) > 8:
            raise ValueError("A question cannot contain more than 8 choices")

        choice_ids = [c.choice_id for c in self.choices]
        if len(set(choice_ids)) != len(choice_ids):
            raise ValueError("Choice IDs within a question must be unique")

        if len(set(self.correct_choice_ids)) != len(self.correct_choice_ids):
            raise ValueError("correct_choice_ids must be unique")

        choice_id_set = set(choice_ids)
        for cid in self.correct_choice_ids:
            if cid not in choice_id_set:
                raise ValueError(f"Correct choice ID {cid} does not exist in choices")

        if self.question_type == QuestionType.single_choice:
            if len(self.correct_choice_ids) != 1:
                raise ValueError(
                    "single_choice question must have exactly one correct choice ID"
                )
        elif self.question_type == QuestionType.multiple_choice:
            if len(self.correct_choice_ids) < 2:
                raise ValueError(
                    "multiple_choice question must have at least two correct choice IDs"
                )
            if len(self.correct_choice_ids) >= len(self.choices):
                raise ValueError(
                    "multiple_choice question cannot have all available choices marked correct"
                )

        return self


class QuizQuestion(BaseModel):
    """An ordered placement of a question within a quiz."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    position: int = Field(ge=1)
    question: Question


class Quiz(BaseModel):
    """An ordered collection of questions forming a complete quiz."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    quiz_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    questions: tuple[QuizQuestion, ...]

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("description cannot be blank if provided")
            return stripped
        return v

    @model_validator(mode="after")
    def validate_quiz_invariants(self) -> Self:
        if len(self.questions) < 1:
            raise ValueError("A quiz must contain at least one question")

        question_ids = [q.question.question_id for q in self.questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("Question IDs within a quiz must be unique")

        positions = [q.position for q in self.questions]
        if len(set(positions)) != len(positions):
            raise ValueError("Quiz question positions must be unique")

        sorted_positions = sorted(positions)
        expected_positions = list(range(1, len(self.questions) + 1))
        if sorted_positions != expected_positions:
            raise ValueError(
                f"Quiz question positions must form a contiguous sequence beginning at 1. "
                f"Got {sorted_positions}, expected {expected_positions}"
            )

        return self


class AnswerSubmission(BaseModel):
    """An answer submission payload containing selections for a single question."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    question_id: UUID
    selected_choice_ids: tuple[UUID, ...]

    @model_validator(mode="after")
    def validate_submission_invariants(self) -> Self:
        if len(self.selected_choice_ids) < 1:
            raise ValueError("At least one choice must be selected")
        if len(set(self.selected_choice_ids)) != len(self.selected_choice_ids):
            raise ValueError("selected_choice_ids must be unique")
        return self

