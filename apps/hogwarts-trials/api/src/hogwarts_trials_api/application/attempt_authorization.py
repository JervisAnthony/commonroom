"""Pure attempt ownership policy, not yet enforced by HTTP or persistence."""

from dataclasses import dataclass
from uuid import UUID

from hogwarts_trials_api.application.identity import AuthenticatedPrincipal


@dataclass(frozen=True)
class AttemptOwnership:
    """One attempt's ownership fact, to be supplied by future trusted storage.

    This value neither attaches ownership to QuizAttempt nor persists it.
    Callers must use the ownership fact for the attempt being accessed.
    """

    attempt_id: UUID
    owner_user_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, UUID):
            raise TypeError("attempt_id must be a UUID")
        if not isinstance(self.owner_user_id, UUID):
            raise TypeError("owner_user_id must be a UUID")


class AttemptAccessDeniedError(PermissionError):
    """The supplied security context does not establish attempt ownership."""


def can_access_attempt(
    ownership: AttemptOwnership | None,
    principal: AuthenticatedPrincipal | None,
) -> bool:
    """Allow only matching trusted identity and ownership; otherwise deny.

    UUID entropy and possession of an attempt ID do not authorize access.
    No default principal, anonymous-owner fallback, or bypass exists.
    """
    return (
        isinstance(ownership, AttemptOwnership)
        and isinstance(principal, AuthenticatedPrincipal)
        and principal.user_id == ownership.owner_user_id
    )


def require_attempt_owner(
    ownership: AttemptOwnership | None,
    principal: AuthenticatedPrincipal | None,
) -> None:
    """Raise an application error on denial, without HTTP semantics."""
    if not can_access_attempt(ownership, principal):
        raise AttemptAccessDeniedError("Attempt access denied")
