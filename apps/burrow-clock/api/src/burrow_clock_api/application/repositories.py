"""Read-only authorization ports for future trusted storage; no adapters."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from burrow_clock_api.domain.friendship import Friendship
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
