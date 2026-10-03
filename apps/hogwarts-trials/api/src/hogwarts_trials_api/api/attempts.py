"""API router for Hogwarts Trials quiz attempt endpoints.

Exposes endpoints to inspect server-owned quiz attempts and submit final answers
to complete an attempt, without exposing server-owned answer keys or provenance.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from hogwarts_trials_api.api.dependencies import (
    get_quiz_attempt_repository,
    get_quiz_repository,
)
from hogwarts_trials_api.api.schemas import (
    QuizAttemptResponse,
    QuizGradeRequest,
    quiz_attempt_to_response,
)
from hogwarts_trials_api.application.quiz_attempt_repository import (
    QuizAttemptRepository,
)
from hogwarts_trials_api.application.quiz_repository import QuizRepository
from hogwarts_trials_api.domain.attempt import (
    AttemptStatus,
    QuizAttemptAlreadyCompletedError,
    QuizAttemptError,
    QuizAttemptNotFoundError,
    complete_attempt,
)
from hogwarts_trials_api.domain.grading import QuizGradingError

router = APIRouter(
    prefix="/api/v1/attempts",
    tags=["attempts"],
)

QuizRepoDep = Annotated[QuizRepository, Depends(get_quiz_repository)]
QuizAttemptRepoDep = Annotated[
    QuizAttemptRepository, Depends(get_quiz_attempt_repository)
]


@router.get("/{attempt_id}", response_model=QuizAttemptResponse)
def get_quiz_attempt(
    attempt_id: UUID,
    attempt_repo: QuizAttemptRepoDep,
) -> QuizAttemptResponse:
    """Retrieve an authoritative quiz attempt by its server-owned UUID.

    Returns 404 if the attempt does not exist. For in-progress attempts,
    result is null. For completed attempts, returns the safe evaluated result snapshot.
    """
    attempt = attempt_repo.get_attempt(attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found",
        )

    return quiz_attempt_to_response(attempt)


@router.post("/{attempt_id}/submit", response_model=QuizAttemptResponse)
def submit_quiz_attempt(
    attempt_id: UUID,
    request: QuizGradeRequest,
    quiz_repo: QuizRepoDep,
    attempt_repo: QuizAttemptRepoDep,
) -> QuizAttemptResponse:
    """Submit final answers for an in-progress quiz attempt.

    Delegates evaluation to the domain complete_attempt() lifecycle function and
    persists the completed attempt snapshot.

    Returns:
        404 Not Found: If the attempt or referenced quiz does not exist.
        409 Conflict: If the attempt has already been completed.
        422 Unprocessable Content: If answer submissions violate validation constraints.
    """
    attempt = attempt_repo.get_attempt(attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found",
        )

    if attempt.status == AttemptStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attempt is already completed",
        )

    quiz = quiz_repo.get_quiz(attempt.quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )

    try:
        completed = complete_attempt(
            attempt=attempt,
            quiz=quiz,
            submissions=request.submissions,
        )
    except QuizGradingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except QuizAttemptAlreadyCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except QuizAttemptError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    try:
        persisted = attempt_repo.complete_attempt(completed)
    except QuizAttemptAlreadyCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except QuizAttemptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return quiz_attempt_to_response(persisted)
