"""API router for Hogwarts Trials quiz endpoints.

Exposes stateless endpoints to list quizzes, fetch playable quiz definitions,
and grade submitted answers without leaking server-owned answer keys.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from hogwarts_trials_api.api.schemas import (
    QuestionGradeResponse,
    QuizChoiceResponse,
    QuizDetailResponse,
    QuizGradeRequest,
    QuizGradeResponse,
    QuizQuestionResponse,
    QuizSummaryResponse,
)
from hogwarts_trials_api.application.quiz_catalog import get_quiz, list_quizzes
from hogwarts_trials_api.domain.grading import QuizGradingError, grade_quiz

router = APIRouter(
    prefix="/api/v1/quizzes",
    tags=["quizzes"],
)


@router.get("", response_model=list[QuizSummaryResponse])
def get_quizzes() -> list[QuizSummaryResponse]:
    """Retrieve all available quizzes as summary items for discovery."""
    quizzes = list_quizzes()
    return [
        QuizSummaryResponse(
            quiz_id=q.quiz_id,
            title=q.title,
            description=q.description,
            question_count=len(q.questions),
        )
        for q in quizzes
    ]


@router.get("/{quiz_id}", response_model=QuizDetailResponse)
def get_quiz_by_id(quiz_id: UUID) -> QuizDetailResponse:
    """Retrieve a playable quiz definition.

    Server-owned answer keys, correct choices, explanations, and editorial
    provenance are omitted.
    """
    quiz = get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )

    return QuizDetailResponse(
        quiz_id=quiz.quiz_id,
        title=quiz.title,
        description=quiz.description,
        questions=tuple(
            QuizQuestionResponse(
                position=qq.position,
                question_id=qq.question.question_id,
                prompt=qq.question.prompt,
                question_type=qq.question.question_type,
                difficulty=qq.question.difficulty,
                choices=tuple(
                    QuizChoiceResponse(
                        choice_id=c.choice_id,
                        text=c.text,
                    )
                    for c in qq.question.choices
                ),
            )
            for qq in sorted(quiz.questions, key=lambda q: q.position)
        ),
    )


@router.post("/{quiz_id}/grade", response_model=QuizGradeResponse)
def grade_quiz_endpoint(
    quiz_id: UUID,
    request: QuizGradeRequest,
) -> QuizGradeResponse:
    """Perform stateless evaluation of submitted answers against a quiz.

    Grading delegates to the deterministic domain engine. Answer keys are strictly
    omitted from the response.
    """
    quiz = get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )

    try:
        domain_result = grade_quiz(quiz=quiz, submissions=request.submissions)
    except QuizGradingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return QuizGradeResponse(
        quiz_id=domain_result.quiz_id,
        question_results=tuple(
            QuestionGradeResponse(
                question_id=qr.question_id,
                status=qr.status,
                selected_choice_ids=qr.selected_choice_ids,
                awarded_points=qr.awarded_points,
                max_points=qr.max_points,
            )
            for qr in domain_result.question_results
        ),
        total_points=domain_result.total_points,
        max_points=domain_result.max_points,
        correct_count=domain_result.correct_count,
        incorrect_count=domain_result.incorrect_count,
        unanswered_count=domain_result.unanswered_count,
    )
