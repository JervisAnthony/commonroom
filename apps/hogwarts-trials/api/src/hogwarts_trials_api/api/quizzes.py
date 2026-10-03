"""API router for Hogwarts Trials quiz endpoints.

Exposes stateless endpoints to list quizzes, fetch playable quiz definitions,
and grade submitted answers without leaking server-owned answer keys.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from hogwarts_trials_api.api.dependencies import (
    get_quiz_attempt_repository,
    get_quiz_repository,
)
from hogwarts_trials_api.api.schemas import (
    QuestionGradeResponse,
    QuizAttemptResponse,
    QuizChoiceResponse,
    QuizDetailResponse,
    QuizGradeRequest,
    QuizGradeResponse,
    QuizQuestionResponse,
    QuizSummaryResponse,
    quiz_attempt_to_response,
    quiz_result_to_response,
)
from hogwarts_trials_api.application.quiz_attempt_repository import (
    QuizAttemptRepository,
)
from hogwarts_trials_api.application.quiz_repository import QuizRepository
from hogwarts_trials_api.domain.attempt import create_quiz_attempt
from hogwarts_trials_api.domain.grading import QuizGradingError, grade_quiz

router = APIRouter(
    prefix="/api/v1/quizzes",
    tags=["quizzes"],
)

QuizRepoDep = Annotated[QuizRepository, Depends(get_quiz_repository)]
QuizAttemptRepoDep = Annotated[
    QuizAttemptRepository, Depends(get_quiz_attempt_repository)
]


@router.get("", response_model=list[QuizSummaryResponse])
def get_quizzes(
    repo: QuizRepoDep,
) -> list[QuizSummaryResponse]:
    """Retrieve all available quizzes as summary items for discovery."""
    quizzes = repo.list_quizzes()
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
def get_quiz_by_id(
    quiz_id: UUID,
    repo: QuizRepoDep,
) -> QuizDetailResponse:
    """Retrieve a playable quiz definition.

    Server-owned answer keys, correct choices, explanations, and editorial
    provenance are omitted.
    """
    quiz = repo.get_quiz(quiz_id)
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
    repo: QuizRepoDep,
) -> QuizGradeResponse:
    """Perform stateless evaluation of submitted answers against a quiz.

    Grading delegates to the deterministic domain engine. Answer keys are strictly
    omitted from the response.
    """
    quiz = repo.get_quiz(quiz_id)
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

    return quiz_result_to_response(domain_result)


@router.post(
    "/{quiz_id}/attempts",
    status_code=status.HTTP_201_CREATED,
    response_model=QuizAttemptResponse,
)
def start_quiz_attempt(
    quiz_id: UUID,
    quiz_repo: QuizRepoDep,
    attempt_repo: QuizAttemptRepoDep,
) -> QuizAttemptResponse:
    """Start a new server-owned quiz attempt.

    Verifies the quiz exists (404 if not found), generates an authoritative
    server-side UUID v4 attempt ID, persists an in_progress attempt, and returns 201 Created.
    """
    quiz = quiz_repo.get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )

    attempt = create_quiz_attempt(quiz_id=quiz.quiz_id)
    persisted = attempt_repo.create_attempt(attempt)
    return quiz_attempt_to_response(persisted)
