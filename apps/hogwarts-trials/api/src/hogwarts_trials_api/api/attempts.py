"""API router for Hogwarts Trials quiz attempt endpoints.

Exposes endpoints to inspect server-owned quiz attempts and submit final answers
to complete an attempt, without exposing server-owned answer keys or provenance.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from hogwarts_trials_api.api.dependencies import (
    get_current_principal,
    get_quiz_attempt_repository,
    get_quiz_repository,
)
from hogwarts_trials_api.api.schemas import (
    QuizAttemptResponse,
    QuizGradeRequest,
    quiz_attempt_to_response,
)
from hogwarts_trials_api.application.attempt_authorization import (
    AttemptAccessDeniedError,
    AttemptOwnership,
    require_attempt_owner,
)
from hogwarts_trials_api.application.identity import AuthenticatedPrincipal
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

PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]

QuizRepoDep = Annotated[QuizRepository, Depends(get_quiz_repository)]
QuizAttemptRepoDep = Annotated[
    QuizAttemptRepository, Depends(get_quiz_attempt_repository)
]


def _require_requested_attempt_owner(
    attempt_id: UUID, principal: AuthenticatedPrincipal, repo: QuizAttemptRepository
) -> None:
    """Authorize the exact ownership fact before crossing the attempt-data boundary."""
    ownership = repo.get_attempt_ownership(attempt_id)
    try:
        if (
            not isinstance(ownership, AttemptOwnership)
            or not isinstance(ownership.attempt_id, UUID)
            or not isinstance(ownership.owner_user_id, UUID)
            or ownership.attempt_id != attempt_id
        ):
            raise AttemptAccessDeniedError("Attempt access denied")
        require_attempt_owner(ownership, principal)
    except AttemptAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
        ) from exc


@router.get("/{attempt_id}", response_model=QuizAttemptResponse)
def get_quiz_attempt(
    attempt_id: UUID,
    principal: PrincipalDep,
    attempt_repo: QuizAttemptRepoDep,
) -> QuizAttemptResponse:
    """Retrieve a trusted principal's attempt after exact-attempt ownership authorization.

    Returns the same 404 for missing ownership, non-owners, and unknown attempts. For in-progress attempts,
    result is null. For completed attempts, returns the safe evaluated result snapshot.
    """
    _require_requested_attempt_owner(attempt_id, principal, attempt_repo)
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
    principal: PrincipalDep,
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
    _require_requested_attempt_owner(attempt_id, principal, attempt_repo)
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
