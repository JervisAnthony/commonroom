"""Product-local storage ports; lifecycle writers require trusted application callers."""

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from burrow_clock_api.domain.consent import SharingScope
from burrow_clock_api.domain.friendship import Friendship
from burrow_clock_api.domain.session import SharingSession
from burrow_clock_api.domain.sharing import SharingPermission


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
