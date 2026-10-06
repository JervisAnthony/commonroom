"""Explicit consent terms; no location data or infrastructure."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum


class SharingScope(Enum):
    """Maximum permitted disclosure, ordered from least to most sensitive."""

    PRESENCE = 1
    APPROXIMATE = 2
    PRECISE = 3


def _require_aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _require_scope(value: SharingScope) -> None:
    if not isinstance(value, SharingScope):
        raise ValueError("scope must be a SharingScope")


@dataclass(frozen=True)
class ConsentGrant:
    """Immutable consent terms with exclusive expiry and revocation boundaries."""

    scope: SharingScope
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_scope(self.scope)
        _require_aware(self.granted_at, "granted_at")
        if self.expires_at is not None:
            _require_aware(self.expires_at, "expires_at")
            if self.expires_at.astimezone(timezone.utc) <= self.granted_at.astimezone(timezone.utc):
                raise ValueError("expires_at must be strictly later than granted_at")
        if self.revoked_at is not None:
            _require_aware(self.revoked_at, "revoked_at")
            if self.revoked_at.astimezone(timezone.utc) < self.granted_at.astimezone(timezone.utc):
                raise ValueError("revoked_at must not be earlier than granted_at")

    def is_active(self, at: datetime) -> bool:
        """Evaluate the supplied time, including historical consent terms."""
        _require_aware(at, "at")
        instant = at.astimezone(timezone.utc)
        return (
            instant >= self.granted_at.astimezone(timezone.utc)
            and (
                self.expires_at is None
                or instant < self.expires_at.astimezone(timezone.utc)
            )
            and (
                self.revoked_at is None
                or instant < self.revoked_at.astimezone(timezone.utc)
            )
        )

    def revoke(self, at: datetime) -> "ConsentGrant":
        """Return a new revoked value; repeat revocation is invalid."""
        _require_aware(at, "revoked_at")
        if self.revoked_at is not None:
            raise ValueError("consent grant is already revoked")
        return replace(self, revoked_at=at)


def is_disclosure_allowed(
    grant: ConsentGrant | None, requested_scope: SharingScope, at: datetime
) -> bool:
    """Deny absent/inactive consent and disclosures above its ceiling."""
    _require_aware(at, "at")
    _require_scope(requested_scope)
    return (
        grant is not None
        and grant.is_active(at)
        and requested_scope.value <= grant.scope.value
    )
