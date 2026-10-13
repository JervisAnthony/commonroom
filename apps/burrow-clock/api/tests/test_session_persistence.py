"""Sessions never bypass current friendship, exact consent, direction, scope or time."""
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from burrow_clock_api.domain.consent import ConsentGrant, SharingScope
from burrow_clock_api.infrastructure.models import FriendshipModel, SharingPermissionModel, SharingSessionModel


def active(repo, value, p, at, scope=SharingScope.PRESENCE):
    return repo.get_active_session(value.session_id, p.sharer_user_id, p.recipient_user_id, scope, at)


def test_explicit_server_id_exact_grant_and_interval(store, sharing_session, explicit_permission, grant_id, instant):
    repo = store[0]
    assert sharing_session.session_id.version == 4
    assert sharing_session.permission_id == grant_id
    assert active(repo, sharing_session, explicit_permission, instant) == sharing_session
    assert active(repo, sharing_session, explicit_permission, instant - timedelta(microseconds=1)) is None
    assert active(repo, sharing_session, explicit_permission, sharing_session.expires_at - timedelta(microseconds=1)) == sharing_session
    assert active(repo, sharing_session, explicit_permission, sharing_session.expires_at) is None


@pytest.mark.parametrize("case", ["no_friendship", "no_permission", "reverse", "pre_activation", "expired", "revoked", "broader", "outlives", "no_expiry", "zero_duration", "naive"])
def test_invalid_session_creation_leaves_no_rows(store, explicit_permission, instant, case):
    repo, factory, _ = store
    p = explicit_permission
    if case != "no_permission":
        identity = repo.grant_permission(p)
    friendship_id, sharer, recipient = p.friendship_id, p.sharer_user_id, p.recipient_user_id
    scope, start, end = SharingScope.PRESENCE, instant, instant + timedelta(hours=1)
    if case == "no_friendship": friendship_id = uuid4()
    if case == "reverse": sharer, recipient = recipient, sharer
    if case == "pre_activation": start = instant - timedelta(microseconds=1)
    if case == "expired": start, end = p.grant.expires_at, p.grant.expires_at + timedelta(hours=1)
    if case == "revoked": repo.revoke_permission(identity, instant)
    if case == "broader": scope = SharingScope.PRECISE
    if case == "outlives": end = p.grant.expires_at + timedelta(microseconds=1)
    if case == "no_expiry": end = None
    if case == "zero_duration": end = start
    if case == "naive": start = instant.replace(tzinfo=None)
    with pytest.raises(ValueError):
        repo.start_session(friendship_id, sharer, recipient, scope, start, end)
    with factory() as session:
        assert session.scalars(select(SharingSessionModel)).all() == []


def test_direction_and_session_scope_cannot_be_reused(store, sharing_session, explicit_permission, instant):
    repo = store[0]
    p = explicit_permission
    assert repo.get_active_session(sharing_session.session_id, p.recipient_user_id, p.sharer_user_id, SharingScope.PRESENCE, instant) is None
    assert active(repo, sharing_session, p, instant, SharingScope.APPROXIMATE) is None
    assert active(repo, sharing_session, p, instant, SharingScope.PRECISE) is None
    assert repo.get_active_session(uuid4(), p.sharer_user_id, p.recipient_user_id, SharingScope.PRESENCE, instant) is None


def test_finite_session_with_indefinite_consent(store, explicit_permission, instant):
    repo = store[0]
    p = replace(explicit_permission, grant=ConsentGrant(SharingScope.PRECISE, instant))
    repo.grant_permission(p)
    value = repo.start_session(p.friendship_id, p.sharer_user_id, p.recipient_user_id, SharingScope.APPROXIMATE, instant, instant + timedelta(hours=1))
    assert active(repo, value, p, instant) == value
    assert active(repo, value, p, value.expires_at) is None


def test_revocation_denies_exactly_without_cleanup(store, sharing_session, explicit_permission, grant_id, instant):
    repo, factory, _ = store
    at = instant + timedelta(minutes=30)
    repo.revoke_permission(grant_id, at)
    assert active(repo, sharing_session, explicit_permission, at - timedelta(microseconds=1)) == sharing_session
    assert active(repo, sharing_session, explicit_permission, at) is None
    assert active(repo, sharing_session, explicit_permission, at + timedelta(minutes=1)) is None
    with factory() as session:
        assert session.get(SharingSessionModel, sharing_session.session_id) is not None


def test_terminated_friendship_denies_even_with_stored_session(store, sharing_session, explicit_permission, instant):
    repo, factory, _ = store
    # Simulate an inactive relationship whose historical rows have not been cleaned.
    with factory.begin() as session:
        session.get(FriendshipModel, explicit_permission.friendship_id).is_active = False
    assert active(repo, sharing_session, explicit_permission, instant) is None
    with factory() as session:
        assert session.get(SharingSessionModel, sharing_session.session_id) is not None


def test_regrant_does_not_revive_old_session_even_if_reinserted(store, sharing_session, explicit_permission, grant_id, instant):
    repo, factory, _ = store
    new_id = repo.grant_permission(explicit_permission)
    assert new_id != grant_id
    assert active(repo, sharing_session, explicit_permission, instant) is None
    with factory.begin() as session:
        assert session.get(SharingSessionModel, sharing_session.session_id) is None
        # A stale historical session still cannot act as a capability.
        session.add(SharingSessionModel(
            session_id=sharing_session.session_id, friendship_id=sharing_session.friendship_id,
            permission_id=grant_id, scope=sharing_session.requested_scope.name,
            started_at=sharing_session.started_at, expires_at=sharing_session.expires_at,
        ))
    assert active(repo, sharing_session, explicit_permission, instant) is None
    new = repo.start_session(explicit_permission.friendship_id, explicit_permission.sharer_user_id,
                             explicit_permission.recipient_user_id, SharingScope.PRESENCE,
                             instant, instant + timedelta(hours=1))
    assert new.permission_id == new_id
    assert active(repo, new, explicit_permission, instant) == new


def test_ended_session_deleted_and_expiry_cleanup_explicit(store, sharing_session, explicit_permission, instant):
    repo, factory, _ = store
    p = explicit_permission
    second = repo.start_session(p.friendship_id, p.sharer_user_id, p.recipient_user_id, SharingScope.PRESENCE, instant, instant + timedelta(hours=2))
    assert repo.end_session(sharing_session.session_id)
    assert not repo.end_session(sharing_session.session_id)
    assert active(repo, sharing_session, p, instant) is None
    assert repo.cleanup_expired_sessions(second.expires_at - timedelta(microseconds=1)) == 0
    assert active(repo, second, p, second.expires_at) is None
    with factory() as session:
        assert session.get(SharingSessionModel, second.session_id) is not None
    assert repo.cleanup_expired_sessions(second.expires_at) == 1
    with factory() as session:
        assert session.get(SharingSessionModel, second.session_id) is None


def test_session_insert_failure_rolls_back(store, explicit_permission, grant_id, instant):
    repo, factory, _ = store
    p = explicit_permission

    def fail(mapper, connection, target):
        raise RuntimeError("synthetic session insert failure")

    event.listen(SharingSessionModel, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            repo.start_session(p.friendship_id, p.sharer_user_id, p.recipient_user_id, SharingScope.PRESENCE, instant, instant + timedelta(hours=1))
    finally:
        event.remove(SharingSessionModel, "before_insert", fail)
    with factory() as session:
        assert session.scalars(select(SharingSessionModel)).all() == []
        assert session.get(SharingPermissionModel, grant_id).is_current


def test_database_session_exact_grant_fk_and_finite_expiry(store, explicit_permission, grant_id, instant):
    _, factory, _ = store
    for permission_id, end in [(uuid4(), instant + timedelta(hours=1)), (grant_id, None), (grant_id, instant)]:
        with pytest.raises(IntegrityError):
            with factory.begin() as session:
                session.add(SharingSessionModel(
                    session_id=uuid4(), friendship_id=explicit_permission.friendship_id,
                    permission_id=permission_id, scope="PRESENCE", started_at=instant, expires_at=end,
                ))
    with factory() as session:
        assert session.scalars(select(SharingSessionModel)).all() == []


def test_permission_delete_cascades_and_missing_facts_deny(store, sharing_session, explicit_permission, grant_id, instant):
    repo, factory, _ = store
    with factory.begin() as session:
        session.delete(session.get(SharingPermissionModel, grant_id))
    assert active(repo, sharing_session, explicit_permission, instant) is None
    with factory() as session:
        assert session.get(SharingSessionModel, sharing_session.session_id) is None


def test_friendship_delete_cascades_metadata(store, sharing_session, explicit_permission, grant_id, instant):
    repo, factory, _ = store
    with factory.begin() as session:
        session.delete(session.get(FriendshipModel, explicit_permission.friendship_id))
    assert active(repo, sharing_session, explicit_permission, instant) is None
    with factory() as session:
        assert session.get(SharingPermissionModel, grant_id) is None
        assert session.get(SharingSessionModel, sharing_session.session_id) is None


def test_malformed_stored_session_start_and_scope_deny(store, sharing_session, explicit_permission, instant):
    repo, factory, _ = store
    with factory.begin() as session:
        row = session.get(SharingSessionModel, sharing_session.session_id)
        row.started_at = instant - timedelta(minutes=1)
    assert active(repo, sharing_session, explicit_permission, instant) is None
    with factory.begin() as session:
        row = session.get(SharingSessionModel, sharing_session.session_id)
        row.started_at = instant
        row.scope = "PRECISE"
    assert active(repo, sharing_session, explicit_permission, instant) is None


def test_exact_session_expiry_at_consent_ceiling(store, explicit_permission, grant_id, instant):
    repo = store[0]
    p = explicit_permission
    value = repo.start_session(p.friendship_id, p.sharer_user_id, p.recipient_user_id,
                              SharingScope.APPROXIMATE, instant, p.grant.expires_at)
    assert active(repo, value, p, value.expires_at - timedelta(microseconds=1)) == value
    assert active(repo, value, p, value.expires_at) is None


def test_current_consent_expiry_is_rechecked_without_cached_allow(store, sharing_session, explicit_permission, grant_id, instant):
    repo, factory, _ = store
    assert active(repo, sharing_session, explicit_permission, instant) == sharing_session
    expiry = instant + timedelta(minutes=30)
    with factory.begin() as session:
        session.get(SharingPermissionModel, grant_id).expires_at = expiry
    assert active(repo, sharing_session, explicit_permission, expiry) is None
    with factory() as session:
        assert session.get(SharingSessionModel, sharing_session.session_id) is not None
