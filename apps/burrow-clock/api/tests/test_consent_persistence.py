"""Exact directional grants, immutable grant identities, UTC and fail-closed reconstruction."""
from dataclasses import replace
from datetime import timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from burrow_clock_api.domain.consent import ConsentGrant, SharingScope
from burrow_clock_api.domain.sharing import SharingPermission, is_friend_disclosure_allowed
from burrow_clock_api.infrastructure.models import SharingPermissionModel, SharingSessionModel
from burrow_clock_api.infrastructure.postgres_sharing_repository import _permission


def test_no_grant_or_session_defaults(store, friendship):
    repo, factory, _ = store
    assert repo.get_permission(friendship.friendship_id, friendship.user_a_id, friendship.user_b_id) is None
    with factory() as session:
        assert session.scalars(select(SharingPermissionModel)).all() == []
        assert session.scalars(select(SharingSessionModel)).all() == []


def test_exact_roundtrip_and_reverse_grant(store, explicit_permission, grant_id):
    repo = store[0]
    p = explicit_permission
    assert grant_id.version == 4
    assert repo.get_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id) == p
    assert repo.get_permission(p.friendship_id, p.recipient_user_id, p.sharer_user_id) is None
    reverse = replace(p, sharer_user_id=p.recipient_user_id, recipient_user_id=p.sharer_user_id,
                      grant=replace(p.grant, scope=SharingScope.PRESENCE))
    reverse_id = repo.grant_permission(reverse)
    assert reverse_id != grant_id
    assert repo.get_permission(p.friendship_id, p.recipient_user_id, p.sharer_user_id) == reverse
    assert repo.get_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id) == p


@pytest.mark.parametrize("scope", list(SharingScope))
def test_stored_scope_ceiling_and_time_boundaries(store, friendship, explicit_permission, scope, instant):
    repo = store[0]
    p = replace(explicit_permission, grant=replace(explicit_permission.grant, scope=scope))
    repo.grant_permission(p)
    stored = repo.get_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id)
    for requested in SharingScope:
        assert is_friend_disclosure_allowed(friendship, stored, p.sharer_user_id, p.recipient_user_id, requested, instant) == (requested.value <= scope.value)
    for at, allowed in [(instant - timedelta(microseconds=1), False), (instant, True),
                        (p.grant.expires_at - timedelta(microseconds=1), True), (p.grant.expires_at, False)]:
        assert is_friend_disclosure_allowed(friendship, stored, p.sharer_user_id, p.recipient_user_id, SharingScope.PRESENCE, at) == allowed


def test_offsets_normalize_to_aware_utc(store, explicit_permission):
    repo, factory, _ = store
    offset = timezone(timedelta(hours=5, minutes=30))
    p = replace(explicit_permission, grant=ConsentGrant(
        SharingScope.PRESENCE, explicit_permission.grant.granted_at.astimezone(offset),
        explicit_permission.grant.expires_at.astimezone(offset),
    ))
    identity = repo.grant_permission(p)
    stored = repo.get_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id)
    assert stored == p
    assert stored.grant.granted_at.tzinfo == timezone.utc
    if factory.kw["bind"].dialect.name == "postgresql":
        with factory() as session:
            assert session.get(SharingPermissionModel, identity).granted_at.utcoffset() is not None


@pytest.mark.parametrize("case", ["outsider", "wrong_friendship", "terminated"])
def test_invalid_membership_or_inactive_friendship_denies(store, explicit_permission, participants, case):
    repo, factory, _ = store
    p = explicit_permission
    if case == "outsider":
        p = replace(p, recipient_user_id=participants[2])
    if case == "wrong_friendship":
        p = replace(p, friendship_id=uuid4())
    if case == "terminated":
        repo.terminate_friendship(p.friendship_id)
    with pytest.raises(ValueError):
        repo.grant_permission(p)
    with factory() as session:
        assert session.scalars(select(SharingPermissionModel)).all() == []


def test_revocation_exact_boundary_preserved_on_repeat(store, friendship, explicit_permission, grant_id, instant):
    repo, factory, _ = store
    p = explicit_permission
    revoked_at = instant + timedelta(minutes=30)
    repo.revoke_permission(grant_id, revoked_at)
    stored = repo.get_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id)
    assert stored.grant.revoked_at == revoked_at
    assert is_friend_disclosure_allowed(friendship, stored, p.sharer_user_id, p.recipient_user_id, SharingScope.PRESENCE, revoked_at - timedelta(microseconds=1))
    assert not is_friend_disclosure_allowed(friendship, stored, p.sharer_user_id, p.recipient_user_id, SharingScope.PRESENCE, revoked_at)
    with pytest.raises(ValueError, match="already revoked"):
        repo.revoke_permission(grant_id, revoked_at + timedelta(minutes=1))
    with factory() as session:
        assert session.get(SharingPermissionModel, grant_id).revoked_at is not None


def test_invalid_revocation_does_not_mutate(store, grant_id, instant):
    repo, factory, _ = store
    with pytest.raises(ValueError):
        repo.revoke_permission(grant_id, instant - timedelta(seconds=1))
    with pytest.raises(ValueError):
        repo.revoke_permission(grant_id, instant.replace(tzinfo=None))
    with pytest.raises(ValueError):
        repo.revoke_permission(uuid4(), instant)
    with factory() as session:
        assert session.get(SharingPermissionModel, grant_id).revoked_at is None


@pytest.mark.parametrize("previous_state", ["revoked", "expired"])
def test_regrant_identity_current_selection_and_history(store, explicit_permission, grant_id, instant, previous_state):
    repo, factory, _ = store
    if previous_state == "revoked":
        repo.revoke_permission(grant_id, instant)
    new_start = instant + timedelta(minutes=1) if previous_state == "revoked" else explicit_permission.grant.expires_at
    new = replace(explicit_permission, grant=ConsentGrant(SharingScope.PRESENCE, new_start))
    new_id = repo.grant_permission(new)
    assert new_id != grant_id
    assert repo.get_permission(new.friendship_id, new.sharer_user_id, new.recipient_user_id) == new
    with factory() as session:
        assert not session.get(SharingPermissionModel, grant_id).is_current
        assert (session.get(SharingPermissionModel, grant_id).revoked_at is not None) == (previous_state == "revoked")
        assert session.get(SharingPermissionModel, new_id).is_current


def test_failed_regrant_restores_previous_grant_and_session(store, explicit_permission, grant_id, sharing_session):
    repo, factory, _ = store

    def fail(mapper, connection, target):
        raise RuntimeError("synthetic grant insert failure")

    event.listen(SharingPermissionModel, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            repo.grant_permission(explicit_permission)
    finally:
        event.remove(SharingPermissionModel, "before_insert", fail)
    with factory() as session:
        assert session.get(SharingPermissionModel, grant_id).is_current
        assert session.get(SharingSessionModel, sharing_session.session_id) is not None
        assert len(session.scalars(select(SharingPermissionModel)).all()) == 1


def test_database_membership_and_direction_uniqueness(store, explicit_permission, grant_id, participants):
    _, factory, _ = store
    p = explicit_permission
    for recipient in [p.recipient_user_id, participants[2]]:
        with pytest.raises(IntegrityError):
            with factory.begin() as session:
                session.add(SharingPermissionModel(
                    permission_id=uuid4(), friendship_id=p.friendship_id,
                    sharer_user_id=p.sharer_user_id, recipient_user_id=recipient,
                    scope="PRESENCE", granted_at=p.grant.granted_at, is_current=True,
                ))
    with factory() as session:
        assert len(session.scalars(select(SharingPermissionModel)).all()) == 1


@pytest.mark.parametrize("change", ["scope", "expiry", "revocation", "naive", "uuid", "missing_time"])
def test_malformed_stored_grants_fail_closed(store, explicit_permission, change):
    _, factory, _ = store
    p = explicit_permission
    row = SharingPermissionModel(
        permission_id=uuid4(), friendship_id=p.friendship_id,
        sharer_user_id=p.sharer_user_id, recipient_user_id=p.recipient_user_id,
        scope="PRESENCE", granted_at=p.grant.granted_at, is_current=True,
    )
    if change == "scope": row.scope = "INVALID"
    if change == "expiry": row.expires_at = row.granted_at
    if change == "revocation": row.revoked_at = row.granted_at - timedelta(seconds=1)
    if change == "uuid": row.recipient_user_id = "invalid"
    if change == "missing_time": row.granted_at = None
    with factory() as session:
        if change == "naive":
            # PostgreSQL must never silently add timezone to malformed input.
            from unittest.mock import Mock
            session = Mock(get_bind=lambda: Mock(dialect=Mock(name="postgresql")))
            row.granted_at = row.granted_at.replace(tzinfo=None)
        assert _permission(row, session) is None


def test_new_grant_cannot_clear_revocation_or_accept_invalid_scope(store, explicit_permission, instant):
    repo = store[0]
    with pytest.raises(ValueError):
        repo.grant_permission(replace(explicit_permission, grant=explicit_permission.grant.revoke(instant)))
    malformed = replace(explicit_permission.grant)
    object.__setattr__(malformed, "scope", "PRECISE")
    with pytest.raises(ValueError):
        repo.grant_permission(replace(explicit_permission, grant=malformed))
    with pytest.raises(TypeError):
        repo.get_permission(str(explicit_permission.friendship_id), explicit_permission.sharer_user_id, explicit_permission.recipient_user_id)
