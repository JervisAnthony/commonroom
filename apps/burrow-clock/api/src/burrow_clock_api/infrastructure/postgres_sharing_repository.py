"""Transactional product-local persistence; no public workflow or actual disclosure.

All relationship-dependent lifecycle writes and active-session reads lock the
friendship first, then permission, then session. PostgreSQL READ COMMITTED reads
after committed termination/revocation deny. A returned value is a snapshot,
not a durable capability: future disclosure must recheck immediately before use.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from burrow_clock_api.domain.consent import ConsentGrant, SharingScope, _require_aware, _require_scope
from burrow_clock_api.domain.friendship import Friendship
from burrow_clock_api.domain.session import SharingSession
from burrow_clock_api.domain.sharing import SharingPermission, is_friend_disclosure_allowed
from burrow_clock_api.infrastructure.models import (
    FriendshipModel, SharingPermissionModel, SharingSessionModel,
)


def _require_uuids(*values: UUID) -> None:
    if any(not isinstance(value, UUID) for value in values):
        raise TypeError("identifiers must be UUIDs")


def _utc(value: datetime) -> datetime:
    _require_aware(value, "timestamp")
    return value.astimezone(timezone.utc)


def _stored_instant(value: datetime, session: Session) -> datetime:
    # SQLite unit tests lose TZ information; production PostgreSQL must never do so.
    if not isinstance(value, datetime):
        raise ValueError("stored timestamp must be a datetime")
    if value.utcoffset() is None and session.get_bind().dialect.name == "sqlite":
        value = value.replace(tzinfo=timezone.utc)
    return _utc(value)


def _friendship(row: FriendshipModel | None) -> Friendship | None:
    if row is None or not row.is_active:
        return None
    try:
        return Friendship(row.friendship_id, row.user_a_id, row.user_b_id)
    except (TypeError, ValueError):
        return None


def _permission(row: SharingPermissionModel | None, session: Session) -> SharingPermission | None:
    if row is None or not row.is_current:
        return None
    try:
        grant = ConsentGrant(
            scope=SharingScope[row.scope],
            granted_at=_stored_instant(row.granted_at, session),
            expires_at=_stored_instant(row.expires_at, session) if row.expires_at is not None else None,
            revoked_at=_stored_instant(row.revoked_at, session) if row.revoked_at is not None else None,
        )
        return SharingPermission(row.friendship_id, row.sharer_user_id, row.recipient_user_id, grant)
    except (KeyError, TypeError, ValueError):
        return None


def _sharing_session(row: SharingSessionModel, session: Session) -> SharingSession | None:
    try:
        return SharingSession(
            row.session_id, row.friendship_id, row.permission_id, SharingScope[row.scope],
            _stored_instant(row.started_at, session), _stored_instant(row.expires_at, session),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _lock_friendship(session: Session, friendship_id: UUID) -> FriendshipModel | None:
    return session.scalars(select(FriendshipModel).where(
        FriendshipModel.friendship_id == friendship_id
    ).with_for_update()).first()


def _current_permission(
    session: Session, friendship_id: UUID, sharer: UUID, recipient: UUID,
) -> SharingPermissionModel | None:
    return session.scalars(select(SharingPermissionModel).where(
        SharingPermissionModel.friendship_id == friendship_id,
        SharingPermissionModel.sharer_user_id == sharer,
        SharingPermissionModel.recipient_user_id == recipient,
        SharingPermissionModel.is_current.is_(True),
    ).with_for_update()).first()


class PostgresSharingRepository:
    """Implements relationship, directional permission, session and lifecycle ports."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_friendship(self, friendship: Friendship) -> Friendship:
        if not isinstance(friendship, Friendship):
            raise TypeError("friendship must be a Friendship")
        # Revalidate even if a caller circumvented frozen dataclass construction.
        validated = Friendship(friendship.friendship_id, friendship.user_a_id, friendship.user_b_id)
        low, high = sorted((validated.user_a_id, validated.user_b_id))
        canonical = Friendship(validated.friendship_id, low, high)
        with self._session_factory.begin() as session:
            # PK and partial unique index also protect concurrent creates.
            session.add(FriendshipModel(
                friendship_id=canonical.friendship_id, user_a_id=low, user_b_id=high, is_active=True,
            ))
        return canonical

    def get_active_friendship_between(self, user_a_id: UUID, user_b_id: UUID) -> Friendship | None:
        _require_uuids(user_a_id, user_b_id)
        low, high = sorted((user_a_id, user_b_id))
        with self._session_factory() as session:
            row = session.scalars(select(FriendshipModel).where(
                FriendshipModel.user_a_id == low, FriendshipModel.user_b_id == high,
                FriendshipModel.is_active.is_(True),
            )).first()
            return _friendship(row)

    def terminate_friendship(self, friendship_id: UUID) -> bool:
        _require_uuids(friendship_id)
        with self._session_factory.begin() as session:
            row = _lock_friendship(session, friendship_id)
            if row is None or not row.is_active:
                return False
            row.is_active = False
            # Minimize activity retention; retain relationship and consent facts only.
            session.execute(delete(SharingSessionModel).where(
                SharingSessionModel.friendship_id == friendship_id
            ))
            return True

    def grant_permission(self, permission: SharingPermission) -> UUID:
        if not isinstance(permission, SharingPermission):
            raise TypeError("permission must be a SharingPermission")
        validated = SharingPermission(
            permission.friendship_id, permission.sharer_user_id,
            permission.recipient_user_id, permission.grant,
        )
        grant = validated.grant
        # Reconstruct to enforce original scope/time invariants at the storage boundary.
        grant = ConsentGrant(grant.scope, grant.granted_at, grant.expires_at, grant.revoked_at)
        if grant.revoked_at is not None:
            raise ValueError("new explicit consent must not already be revoked")
        permission_id = uuid4()
        with self._session_factory.begin() as session:
            friendship = _friendship(_lock_friendship(session, validated.friendship_id))
            if friendship is None or not friendship.connects(
                validated.sharer_user_id, validated.recipient_user_id
            ):
                raise ValueError("permission requires an active matching friendship")
            previous = _current_permission(
                session, validated.friendship_id, validated.sharer_user_id, validated.recipient_user_id,
            )
            if previous is not None:
                previous.is_current = False
                # Release the unique current-direction slot before inserting the new grant.
                session.flush()
                session.execute(delete(SharingSessionModel).where(
                    SharingSessionModel.permission_id == previous.permission_id
                ))
            session.add(SharingPermissionModel(
                permission_id=permission_id, friendship_id=validated.friendship_id,
                sharer_user_id=validated.sharer_user_id, recipient_user_id=validated.recipient_user_id,
                scope=grant.scope.name, granted_at=_utc(grant.granted_at),
                expires_at=_utc(grant.expires_at) if grant.expires_at is not None else None,
                revoked_at=None, is_current=True,
            ))
        return permission_id

    def get_permission(
        self, friendship_id: UUID, sharer_user_id: UUID, recipient_user_id: UUID,
    ) -> SharingPermission | None:
        _require_uuids(friendship_id, sharer_user_id, recipient_user_id)
        with self._session_factory.begin() as session:
            friendship = _friendship(_lock_friendship(session, friendship_id))
            if friendship is None or not friendship.connects(sharer_user_id, recipient_user_id):
                return None
            return _permission(_current_permission(
                session, friendship_id, sharer_user_id, recipient_user_id
            ), session)

    def revoke_permission(self, permission_id: UUID, at: datetime) -> None:
        _require_uuids(permission_id)
        at = _utc(at)
        with self._session_factory.begin() as session:
            # This first read finds the parent only, never constitutes authorization.
            friendship_id = session.scalar(select(SharingPermissionModel.friendship_id).where(
                SharingPermissionModel.permission_id == permission_id
            ))
            if friendship_id is None:
                raise ValueError("permission not found")
            _lock_friendship(session, friendship_id)
            row = session.scalars(select(SharingPermissionModel).where(
                SharingPermissionModel.permission_id == permission_id
            ).with_for_update()).first()
            if row is None:
                raise ValueError("permission not found")
            if row.revoked_at is not None:
                raise ValueError("consent grant is already revoked")
            if at < _stored_instant(row.granted_at, session):
                raise ValueError("revocation cannot precede grant activation")
            row.revoked_at = at
            # Leave rows bound to this revoked fact; evaluation honors the exact boundary.
            # No method clears revoked_at or reactivates an old grant.

    def start_session(
        self, friendship_id: UUID, sharer_user_id: UUID, recipient_user_id: UUID,
        requested_scope: SharingScope, started_at: datetime, expires_at: datetime,
    ) -> SharingSession:
        _require_uuids(friendship_id, sharer_user_id, recipient_user_id)
        _require_scope(requested_scope)
        started_at, expires_at = _utc(started_at), _utc(expires_at)
        with self._session_factory.begin() as session:
            friendship = _friendship(_lock_friendship(session, friendship_id))
            row = _current_permission(session, friendship_id, sharer_user_id, recipient_user_id)
            permission = _permission(row, session)
            if not is_friend_disclosure_allowed(
                friendship, permission, sharer_user_id, recipient_user_id, requested_scope, started_at,
            ):
                raise ValueError("session requires active friendship and valid directional consent")
            if permission.grant.expires_at is not None and expires_at > permission.grant.expires_at:
                raise ValueError("session cannot outlive consent expiry")
            value = SharingSession(uuid4(), friendship_id, row.permission_id,
                                   requested_scope, started_at, expires_at)
            session.add(SharingSessionModel(
                session_id=value.session_id, friendship_id=friendship_id,
                permission_id=value.permission_id, scope=requested_scope.name,
                started_at=started_at, expires_at=expires_at,
            ))
        return value

    def get_active_session(
        self, session_id: UUID, sharer_user_id: UUID, recipient_user_id: UUID,
        requested_scope: SharingScope, at: datetime,
    ) -> SharingSession | None:
        _require_uuids(session_id, sharer_user_id, recipient_user_id)
        _require_scope(requested_scope)
        at = _utc(at)
        with self._session_factory.begin() as session:
            friendship_id = session.scalar(select(SharingSessionModel.friendship_id).where(
                SharingSessionModel.session_id == session_id
            ))
            if friendship_id is None:
                return None
            friendship = _friendship(_lock_friendship(session, friendship_id))
            permission_row = _current_permission(session, friendship_id, sharer_user_id, recipient_user_id)
            row = session.scalars(select(SharingSessionModel).where(
                SharingSessionModel.session_id == session_id
            ).with_for_update()).first()
            if row is None or permission_row is None or row.permission_id != permission_row.permission_id:
                return None
            value = _sharing_session(row, session)
            permission = _permission(permission_row, session)
            if value is None or not value.is_active(at):
                return None
            if requested_scope.value > value.requested_scope.value:
                return None
            if permission is None or (
                permission.grant.expires_at is not None and value.expires_at > permission.grant.expires_at
            ):
                return None
            if not is_friend_disclosure_allowed(
                friendship, permission, sharer_user_id, recipient_user_id,
                value.requested_scope, value.started_at,
            ):
                return None
            if not is_friend_disclosure_allowed(
                friendship, permission, sharer_user_id, recipient_user_id, value.requested_scope, at,
            ):
                return None
            return value

    def end_session(self, session_id: UUID) -> bool:
        _require_uuids(session_id)
        with self._session_factory.begin() as session:
            friendship_id = session.scalar(select(SharingSessionModel.friendship_id).where(
                SharingSessionModel.session_id == session_id
            ))
            if friendship_id is None:
                return False
            _lock_friendship(session, friendship_id)
            return session.execute(delete(SharingSessionModel).where(
                SharingSessionModel.session_id == session_id
            )).rowcount == 1

    def cleanup_expired_sessions(self, at: datetime) -> int:
        at = _utc(at)
        with self._session_factory.begin() as session:
            return session.execute(delete(SharingSessionModel).where(
                SharingSessionModel.expires_at <= at
            )).rowcount
