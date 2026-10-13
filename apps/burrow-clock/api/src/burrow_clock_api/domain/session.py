"""Time-bounded sharing metadata; this value alone never authorizes disclosure."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from burrow_clock_api.domain.consent import SharingScope, _require_aware, _require_scope


@dataclass(frozen=True)
class SharingSession:
    session_id: UUID
    friendship_id: UUID
    permission_id: UUID
    requested_scope: SharingScope
    started_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for name in ("session_id", "friendship_id", "permission_id"):
            if not isinstance(getattr(self, name), UUID):
                raise TypeError(f"{name} must be a UUID")
        _require_scope(self.requested_scope)
        _require_aware(self.started_at, "started_at")
        _require_aware(self.expires_at, "expires_at")
        if self.expires_at.astimezone(timezone.utc) <= self.started_at.astimezone(timezone.utc):
            raise ValueError("expires_at must be strictly later than started_at")

    def is_active(self, at: datetime) -> bool:
        """Interval check only; current friendship and consent must also be checked."""
        _require_aware(at, "at")
        instant = at.astimezone(timezone.utc)
        return self.started_at.astimezone(timezone.utc) <= instant < self.expires_at.astimezone(timezone.utc)
