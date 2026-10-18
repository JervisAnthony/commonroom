"""Minimal metadata DTOs; write contracts forbid actor identity and lifecycle flags."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from burrow_clock_api.application.repositories import CurrentPermission
from burrow_clock_api.domain.session import SharingSession

ScopeName = Literal["PRESENCE", "APPROXIMATE", "PRECISE"]


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    recipient_user_id: UUID
    scope: ScopeName
    expires_at: AwareDatetime | None = None

    @field_validator("expires_at", mode="before")
    @classmethod
    def require_iso_datetime(cls, value):
        # Do not interpret numeric epoch values as an ISO 8601 client timestamp.
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("expires_at must be an aware ISO 8601 datetime")
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError("expires_at must be an aware ISO 8601 datetime") from None
        return value

    @field_validator("expires_at")
    @classmethod
    def normalize_utc(cls, value):
        return value.astimezone(timezone.utc) if value is not None else None


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    recipient_user_id: UUID
    requested_scope: ScopeName
    duration_seconds: int = Field(strict=True, ge=60, le=86400)


class MetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("granted_at", "revoked_at", "started_at", "expires_at", check_fields=False)
    @classmethod
    def utc_timestamps(cls, value):
        return value.astimezone(timezone.utc) if value is not None else None


class FriendshipResponse(MetadataResponse):
    friendship_id: UUID
    user_a_id: UUID
    user_b_id: UUID


class PermissionResponse(MetadataResponse):
    permission_id: UUID
    friendship_id: UUID
    sharer_user_id: UUID
    recipient_user_id: UUID
    scope: ScopeName
    granted_at: AwareDatetime
    expires_at: AwareDatetime | None
    revoked_at: AwareDatetime | None


class SessionResponse(MetadataResponse):
    session_id: UUID
    friendship_id: UUID
    permission_id: UUID
    requested_scope: ScopeName
    started_at: AwareDatetime
    expires_at: AwareDatetime


def permission_response(value: CurrentPermission) -> PermissionResponse:
    p = value.permission
    return PermissionResponse(
        permission_id=value.permission_id, friendship_id=p.friendship_id,
        sharer_user_id=p.sharer_user_id, recipient_user_id=p.recipient_user_id,
        scope=p.grant.scope.name, granted_at=p.grant.granted_at,
        expires_at=p.grant.expires_at, revoked_at=p.grant.revoked_at,
    )


def session_response(value: SharingSession) -> SessionResponse:
    return SessionResponse(
        session_id=value.session_id, friendship_id=value.friendship_id,
        permission_id=value.permission_id, requested_scope=value.requested_scope.name,
        started_at=value.started_at, expires_at=value.expires_at,
    )
