"""Product-local storage ports; lifecycle writers require trusted application callers."""

from datetime import datetime
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from burrow_clock_api.domain.consent import SharingScope
from burrow_clock_api.domain.friendship import Friendship
from burrow_clock_api.domain.session import SharingSession
from burrow_clock_api.domain.sharing import SharingPermission


class SharingStateConflict(ValueError):
    """An authorized transition conflicts with existing consent terms/state."""


@dataclass(frozen=True)
class CurrentPermission:
    """Current exact-direction consent plus its generated grant identity."""

    permission_id: UUID
    permission: SharingPermission

    def __post_init__(self) -> None:
        if not isinstance(self.permission_id, UUID):
            raise TypeError("permission_id must be a UUID")
        if not isinstance(self.permission, SharingPermission):
            raise TypeError("permission must be a SharingPermission")


@runtime_checkable
class FriendshipRepository(Protocol):
    def get_active_friendship_between(
        self, user_a_id: UUID, user_b_id: UUID
    ) -> Friendship | None:
        """Return only a currently active relationship, independent of order.

        Removed, blocked or unfriended relationships must return None.
        """
        ...


@runtime_checkable
class SharingPermissionRepository(Protocol):
    def get_permission(
        self, friendship_id: UUID, sharer_user_id: UUID, recipient_user_id: UUID
    ) -> SharingPermission | None:
        """Return the exact direction's permission, or None; never reverse it.

        A returned permission alone does not authorize disclosure.
        """
        ...


@runtime_checkable
class SharingSessionRepository(Protocol):
    def get_active_session(
        self, session_id: UUID, sharer_user_id: UUID, recipient_user_id: UUID,
        requested_scope: SharingScope, at: datetime,
    ) -> SharingSession | None:
        """Re-evaluate current friendship, exact grant, direction and time; otherwise None."""
        ...


class SharingLifecycleRepository(Protocol):
    """Internal writes only. IDs are identifiers, never proof of authentication.

    Future public callers must authenticate and authorize the acting sharer first.
    Invalid transitions raise ValueError; invalid UUID types raise TypeError.
    Database constraint/transaction failures propagate without partial writes.
    """

    def create_friendship(self, friendship: Friendship) -> Friendship: ...

    def terminate_friendship(self, friendship_id: UUID) -> bool: ...

    def grant_permission(self, permission: SharingPermission) -> UUID:
        """Create a new explicit grant identity, replacing the current exact direction."""
        ...

    def revoke_permission(self, permission_id: UUID, at: datetime) -> None: ...

    def start_session(
        self, friendship_id: UUID, sharer_user_id: UUID, recipient_user_id: UUID,
        requested_scope: SharingScope, started_at: datetime, expires_at: datetime,
    ) -> SharingSession: ...

    def end_session(self, session_id: UUID) -> bool: ...

    def cleanup_expired_sessions(self, at: datetime) -> int: ...


class AuthorizedSharingRepository(FriendshipRepository, SharingSessionRepository, Protocol):
    """HTTP-facing port: actor identity comes from trusted authentication only.

    Mutations verify authoritative membership/ownership in the mutation transaction.
    Missing and inaccessible resources have the same None/False result.
    """

    def get_current_permission(
        self, friendship_id: UUID, sharer_user_id: UUID, recipient_user_id: UUID,
    ) -> CurrentPermission | None: ...

    def terminate_friendship_as_member(self, friendship_id: UUID, actor_user_id: UUID) -> bool: ...

    def revoke_permission_as_sharer(
        self, permission_id: UUID, actor_user_id: UUID, at: datetime,
    ) -> bool: ...

    def end_session_as_sharer(self, session_id: UUID, actor_user_id: UUID) -> bool: ...

    def grant_permission(self, permission: SharingPermission) -> UUID: ...

    def start_session(
        self, friendship_id: UUID, sharer_user_id: UUID, recipient_user_id: UUID,
        requested_scope: SharingScope, started_at: datetime, expires_at: datetime,
    ) -> SharingSession: ...
