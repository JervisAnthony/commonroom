"""Hogwarts Trials deterministic quiz grading engine.

Provides pure domain evaluation functions and immutable result models for
grading questions and aggregating quiz outcomes.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hogwarts_trials_api.domain.quiz import AnswerSubmission, Question, Quiz


class QuizGradingError(ValueError):
    """Raised when an answer submission violates contextual grading rules."""

    pass


class QuestionResultStatus(StrEnum):
    """Outcome status for an evaluated question."""

    correct = "correct"
    incorrect = "incorrect"
    unanswered = "unanswered"


class QuestionResult(BaseModel):
    """Immutable outcome of evaluating an individual question."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    question_id: UUID
    status: QuestionResultStatus
    selected_choice_ids: tuple[UUID, ...]
    correct_choice_ids: tuple[UUID, ...]
    awarded_points: int = Field(ge=0, le=1)
    max_points: int = Field(default=1)

    @field_validator("correct_choice_ids")
    @classmethod
    def validate_and_sort_correct_choice_ids(
        cls, v: tuple[UUID, ...]
    ) -> tuple[UUID, ...]:
        if len(v) == 0:
            raise ValueError("correct_choice_ids must not be empty")
        if len(set(v)) != len(v):
            raise ValueError("correct_choice_ids must contain unique IDs")
        return tuple(sorted(v, key=lambda u: u.int))

    @field_validator("selected_choice_ids")
    @classmethod
    def validate_and_sort_selected_choice_ids(
        cls, v: tuple[UUID, ...]
    ) -> tuple[UUID, ...]:
        if len(set(v)) != len(v):
            raise ValueError("selected_choice_ids must contain unique IDs")
        return tuple(sorted(v, key=lambda u: u.int))

    @model_validator(mode="after")
    def validate_result_invariants(self) -> Self:
        if self.max_points != 1:
            raise ValueError("max_points must be exactly 1")
        if self.awarded_points not in (0, 1):
            raise ValueError("awarded_points must be 0 or 1")

        if self.status == QuestionResultStatus.correct:
            if len(self.selected_choice_ids) == 0:
                raise ValueError("correct question result must have selected choices")
            if self.awarded_points != 1:
                raise ValueError("correct question result must award 1 point")
        elif self.status == QuestionResultStatus.incorrect:
            if len(self.selected_choice_ids) == 0:
                raise ValueError("incorrect question result must have selected choices")
            if self.awarded_points != 0:
                raise ValueError("incorrect question result must award 0 points")
        elif self.status == QuestionResultStatus.unanswered:
            if len(self.selected_choice_ids) != 0:
                raise ValueError("unanswered question result cannot have selected choices")
            if self.awarded_points != 0:
                raise ValueError("unanswered question result must award 0 points")

        return self


class QuizResult(BaseModel):
    """Aggregated immutable result for a completed or partially completed quiz."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    quiz_id: UUID
    question_results: tuple[QuestionResult, ...]
    total_points: int = Field(ge=0)
    max_points: int = Field(ge=1)
    correct_count: int = Field(ge=0)
    incorrect_count: int = Field(ge=0)
    unanswered_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_quiz_result_invariants(self) -> Self:
        if len(self.question_results) < 1:
            raise ValueError("A quiz result must contain at least one question result")

        question_ids = [r.question_id for r in self.question_results]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("Question IDs within a quiz result must be unique")

        expected_total_points = sum(r.awarded_points for r in self.question_results)
        if self.total_points != expected_total_points:
            raise ValueError(
                f"total_points ({self.total_points}) does not match sum of awarded points ({expected_total_points})"
            )

        expected_max_points = sum(r.max_points for r in self.question_results)
        if self.max_points != expected_max_points:
            raise ValueError(
                f"max_points ({self.max_points}) does not match sum of question max points ({expected_max_points})"
            )

        expected_correct = sum(
            1 for r in self.question_results if r.status == QuestionResultStatus.correct
        )
        if self.correct_count != expected_correct:
            raise ValueError(
                f"correct_count ({self.correct_count}) does not match number of correct results ({expected_correct})"
            )

        expected_incorrect = sum(
            1 for r in self.question_results if r.status == QuestionResultStatus.incorrect
        )
        if self.incorrect_count != expected_incorrect:
            raise ValueError(
                f"incorrect_count ({self.incorrect_count}) does not match number of incorrect results ({expected_incorrect})"
            )

        expected_unanswered = sum(
            1
            for r in self.question_results
            if r.status == QuestionResultStatus.unanswered
        )
        if self.unanswered_count != expected_unanswered:
            raise ValueError(
                f"unanswered_count ({self.unanswered_count}) does not match number of unanswered results ({expected_unanswered})"
            )

        if (
            self.correct_count + self.incorrect_count + self.unanswered_count
            != len(self.question_results)
        ):
            raise ValueError(
                "Sum of status counts must equal the number of question results"
            )

        return self


def grade_question(
    question: Question,
    submission: AnswerSubmission | None,
) -> QuestionResult:
    """Evaluate an answer submission against a question's server-owned answer key."""
    canonical_correct_choice_ids = tuple(
        sorted(question.correct_choice_ids, key=lambda u: u.int)
    )

    if submission is None:
        return QuestionResult(
            question_id=question.question_id,
            status=QuestionResultStatus.unanswered,
            selected_choice_ids=(),
            correct_choice_ids=canonical_correct_choice_ids,
            awarded_points=0,
            max_points=1,
        )

    if submission.question_id != question.question_id:
        raise QuizGradingError(
            f"Submission question_id ({submission.question_id}) does not match "
            f"question.question_id ({question.question_id})"
        )

    available_choice_ids = {c.choice_id for c in question.choices}
    for selected_id in submission.selected_choice_ids:
        if selected_id not in available_choice_ids:
            raise QuizGradingError(
                f"Selected choice ID {selected_id} is not a valid choice for question {question.question_id}"
            )

    canonical_selected_choice_ids = tuple(
        sorted(submission.selected_choice_ids, key=lambda u: u.int)
    )

    is_correct = set(submission.selected_choice_ids) == set(question.correct_choice_ids)

    if is_correct:
        return QuestionResult(
            question_id=question.question_id,
            status=QuestionResultStatus.correct,
            selected_choice_ids=canonical_selected_choice_ids,
            correct_choice_ids=canonical_correct_choice_ids,
            awarded_points=1,
            max_points=1,
        )
    else:
        return QuestionResult(
            question_id=question.question_id,
            status=QuestionResultStatus.incorrect,
            selected_choice_ids=canonical_selected_choice_ids,
            correct_choice_ids=canonical_correct_choice_ids,
            awarded_points=0,
            max_points=1,
        )


def grade_quiz(
    quiz: Quiz,
    submissions: Sequence[AnswerSubmission] = (),
) -> QuizResult:
    """Grade an entire quiz deterministically by ordering questions by position."""
    quiz_question_map = {qq.question.question_id: qq for qq in quiz.questions}

    seen_submission_qids: set[UUID] = set()
    submission_map: dict[UUID, AnswerSubmission] = {}
    for sub in submissions:
        if sub.question_id in seen_submission_qids:
            raise QuizGradingError(
                f"Duplicate submission detected for question ID {sub.question_id}"
            )
        seen_submission_qids.add(sub.question_id)
        if sub.question_id not in quiz_question_map:
            raise QuizGradingError(
                f"Submission question ID {sub.question_id} does not belong to quiz {quiz.quiz_id}"
            )
        submission_map[sub.question_id] = sub

    sorted_quiz_questions = sorted(quiz.questions, key=lambda qq: qq.position)

    question_results: list[QuestionResult] = []
    for qq in sorted_quiz_questions:
        sub = submission_map.get(qq.question.question_id)
        result = grade_question(qq.question, sub)
        question_results.append(result)

    results_tuple = tuple(question_results)
    total_points = sum(r.awarded_points for r in results_tuple)
    max_points = sum(r.max_points for r in results_tuple)
    correct_count = sum(
        1 for r in results_tuple if r.status == QuestionResultStatus.correct
    )
    incorrect_count = sum(
        1 for r in results_tuple if r.status == QuestionResultStatus.incorrect
    )
    unanswered_count = sum(
        1 for r in results_tuple if r.status == QuestionResultStatus.unanswered
    )

    return QuizResult(
        quiz_id=quiz.quiz_id,
        question_results=results_tuple,
        total_points=total_points,
        max_points=max_points,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        unanswered_count=unanswered_count,
    )

