"""Directional permission and pure default-deny friend disclosure policy."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from burrow_clock_api.domain.consent import (
    ConsentGrant,
    SharingScope,
    is_disclosure_allowed,
)
from burrow_clock_api.domain.friendship import Friendship


@dataclass(frozen=True)
class SharingPermission:
    """Explicit consent for one direction within one exact friendship."""

    friendship_id: UUID
    sharer_user_id: UUID
    recipient_user_id: UUID
    grant: ConsentGrant

    def __post_init__(self) -> None:
        for name in ("friendship_id", "sharer_user_id", "recipient_user_id"):
            if not isinstance(getattr(self, name), UUID):
                raise TypeError(f"{name} must be a UUID")
        if self.sharer_user_id == self.recipient_user_id:
            raise ValueError("sharer and recipient must be distinct")
        if not isinstance(self.grant, ConsentGrant):
            raise TypeError("grant must be a ConsentGrant")


def is_friend_disclosure_allowed(
    friendship: Friendship | None,
    permission: SharingPermission | None,
    sharer_user_id: UUID,
    recipient_user_id: UUID,
    requested_scope: SharingScope,
    at: datetime,
) -> bool:
    """Require both trusted facts each time; absent active friendship denies.

    Removal, blocking or unfriending must make trusted storage return no active
    friendship, even if an otherwise active permission remains. Invalid scope
    or evaluation time retains the consent helper's ValueError contract.
    """
    if not isinstance(friendship, Friendship) or not isinstance(permission, SharingPermission):
        return False
    if not isinstance(sharer_user_id, UUID) or not isinstance(recipient_user_id, UUID):
        return False
    if not friendship.connects(sharer_user_id, recipient_user_id):
        return False
    if (
        permission.friendship_id != friendship.friendship_id
        or permission.sharer_user_id != sharer_user_id
        or permission.recipient_user_id != recipient_user_id
    ):
        return False
    return is_disclosure_allowed(permission.grant, requested_scope, at)
