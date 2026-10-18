"""Actor-aware writes cannot use identifiers or stale reads as authority."""
from datetime import timedelta
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import event

from burrow_clock_api.application.repositories import SharingStateConflict
from burrow_clock_api.domain.consent import ConsentGrant, SharingScope
from burrow_clock_api.domain.sharing import SharingPermission
from burrow_clock_api.infrastructure.models import FriendshipModel, SharingPermissionModel, SharingSessionModel


def test_member_mutation_uses_authoritative_membership(store, friendship, participants):
    repo, factory, _ = store
    assert repo.get_active_friendship_between(*participants[:2]) == friendship
    assert not repo.terminate_friendship_as_member(friendship.friendship_id, participants[2])
    with factory() as session:
        assert session.get(FriendshipModel, friendship.friendship_id).is_active
    assert repo.terminate_friendship_as_member(friendship.friendship_id, participants[1])
    assert not repo.terminate_friendship_as_member(friendship.friendship_id, participants[0])


def test_current_identity_and_unauthorized_revocation_leave_facts_unchanged(
    store, explicit_permission, grant_id, instant, participants,
):
    repo, factory, _ = store
    p = explicit_permission
    current = repo.get_current_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id)
    assert current.permission_id == grant_id and current.permission == p
    for actor in [p.recipient_user_id, participants[2]]:
        assert not repo.revoke_permission_as_sharer(grant_id, actor, instant)
    with factory() as session:
        assert session.get(SharingPermissionModel, grant_id).revoked_at is None
    assert repo.revoke_permission_as_sharer(grant_id, p.sharer_user_id, instant)
    with pytest.raises(SharingStateConflict):
        repo.revoke_permission_as_sharer(grant_id, p.sharer_user_id, instant)


def test_supersession_invalidates_prior_precheck_for_revocation(store, explicit_permission, grant_id, instant):
    repo, factory, _ = store
    p = explicit_permission
    earlier = repo.get_current_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id)
    assert earlier.permission_id == grant_id
    replacement = repo.grant_permission(p)
    assert not repo.revoke_permission_as_sharer(earlier.permission_id, p.sharer_user_id, instant)
    with factory() as session:
        assert session.get(SharingPermissionModel, replacement).revoked_at is None
        assert not session.get(SharingPermissionModel, grant_id).is_current


def test_only_exact_owner_can_end_even_revoked_session(
    store, explicit_permission, grant_id, sharing_session, instant, participants,
):
    repo, factory, _ = store
    p = explicit_permission
    for actor in [p.recipient_user_id, participants[2]]:
        assert not repo.end_session_as_sharer(sharing_session.session_id, actor)
    with factory() as session:
        assert session.get(SharingSessionModel, sharing_session.session_id) is not None
    repo.revoke_permission_as_sharer(grant_id, p.sharer_user_id, instant)
    assert repo.end_session_as_sharer(sharing_session.session_id, p.sharer_user_id)
    assert not repo.end_session_as_sharer(sharing_session.session_id, p.sharer_user_id)


def test_pending_cancellation_is_permanent_and_directional(store, explicit_permission, instant):
    repo, factory, _ = store
    p = replace(explicit_permission, grant=ConsentGrant(
        SharingScope.APPROXIMATE, instant + timedelta(hours=1), instant + timedelta(hours=2),
    ))
    identity = repo.grant_permission(p)
    reverse = SharingPermission(p.friendship_id, p.recipient_user_id, p.sharer_user_id,
                                ConsentGrant(SharingScope.PRESENCE, instant))
    reverse_id = repo.grant_permission(reverse)
    # The internal writer can hold scheduled metadata; cancellation must remove it too.
    value = repo.start_session(p.friendship_id, p.sharer_user_id, p.recipient_user_id,
                              SharingScope.PRESENCE, p.grant.granted_at,
                              p.grant.granted_at + timedelta(minutes=1))
    assert repo.revoke_permission_as_sharer(identity, p.sharer_user_id, instant)
    assert repo.get_current_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id) is None
    assert repo.get_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id) is None
    assert not repo.revoke_permission_as_sharer(identity, p.sharer_user_id, p.grant.granted_at)
    for at in [p.grant.granted_at, p.grant.granted_at + timedelta(minutes=30)]:
        with pytest.raises(ValueError):
            repo.start_session(p.friendship_id, p.sharer_user_id, p.recipient_user_id,
                               SharingScope.PRESENCE, at, at + timedelta(seconds=60))
        assert repo.get_active_session(value.session_id, p.sharer_user_id, p.recipient_user_id,
                                       SharingScope.PRESENCE, at) is None
    assert repo.get_current_permission(p.friendship_id, p.recipient_user_id, p.sharer_user_id).permission_id == reverse_id
    with factory() as session:
        row = session.get(SharingPermissionModel, identity)
        assert not row.is_current and row.revoked_at is None
        assert session.get(SharingSessionModel, value.session_id) is None
    replacement = repo.grant_permission(p)
    assert replacement != identity
    assert repo.get_current_permission(p.friendship_id, p.sharer_user_id, p.recipient_user_id).permission_id == replacement
    with factory() as session:
        assert not session.get(SharingPermissionModel, identity).is_current


@pytest.mark.parametrize("denial", ["recipient", "outsider", "terminated"])
def test_pending_cancellation_requires_sharer_and_active_friendship(
    store, explicit_permission, instant, participants, denial,
):
    repo, factory, _ = store
    p = replace(explicit_permission, grant=ConsentGrant(SharingScope.PRESENCE, instant + timedelta(hours=1)))
    identity = repo.grant_permission(p)
    actor = p.recipient_user_id if denial == "recipient" else participants[2]
    if denial == "terminated":
        assert repo.terminate_friendship_as_member(p.friendship_id, p.sharer_user_id)
        actor = p.sharer_user_id
    assert not repo.revoke_permission_as_sharer(identity, actor, instant)
    with factory() as session:
        row = session.get(SharingPermissionModel, identity)
        assert row.is_current and row.revoked_at is None


def test_pending_cancellation_rolls_back_if_session_cleanup_fails(store, explicit_permission, instant):
    repo, factory, engine = store
    p = replace(explicit_permission, grant=ConsentGrant(SharingScope.PRESENCE, instant + timedelta(hours=1)))
    identity = repo.grant_permission(p)
    value = repo.start_session(p.friendship_id, p.sharer_user_id, p.recipient_user_id,
                              SharingScope.PRESENCE, p.grant.granted_at,
                              p.grant.granted_at + timedelta(minutes=1))
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("DELETE FROM SHARING_SESSIONS"):
            raise RuntimeError("synthetic cancellation cleanup failure")
    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            repo.revoke_permission_as_sharer(identity, p.sharer_user_id, instant)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with factory() as session:
        assert session.get(SharingPermissionModel, identity).is_current
        assert session.get(SharingPermissionModel, identity).revoked_at is None
        assert session.get(SharingSessionModel, value.session_id) is not None


def test_active_revocation_preserves_exact_timestamp_boundary(
    store, explicit_permission, grant_id, sharing_session, instant,
):
    repo, factory, _ = store
    p = explicit_permission
    revoked_at = instant + timedelta(minutes=30)
    assert repo.revoke_permission_as_sharer(grant_id, p.sharer_user_id, revoked_at)
    assert repo.get_active_session(sharing_session.session_id, p.sharer_user_id, p.recipient_user_id,
                                   SharingScope.PRESENCE, revoked_at - timedelta(microseconds=1)) is not None
    assert repo.get_active_session(sharing_session.session_id, p.sharer_user_id, p.recipient_user_id,
                                   SharingScope.PRESENCE, revoked_at) is None
    with factory() as session:
        assert session.get(SharingPermissionModel, grant_id).is_current
        assert session.get(SharingSessionModel, sharing_session.session_id) is not None
    with pytest.raises(SharingStateConflict):
        repo.revoke_permission_as_sharer(grant_id, p.sharer_user_id, instant - timedelta(seconds=1))
    assert repo.get_current_permission(p.friendship_id, p.sharer_user_id,
                                       p.recipient_user_id).permission.grant.revoked_at == revoked_at


@pytest.mark.parametrize("operation", ["terminate", "revoke", "end"])
def test_missing_ids_and_invalid_uuid_types_fail_closed(store, instant, participants, operation):
    repo = store[0]
    def invoke(identity):
        if operation == "terminate": return repo.terminate_friendship_as_member(identity, participants[0])
        if operation == "revoke": return repo.revoke_permission_as_sharer(identity, participants[0], instant)
        return repo.end_session_as_sharer(identity, participants[0])
    assert not invoke(uuid4())
    with pytest.raises(TypeError):
        invoke("not-a-uuid")


def test_authorized_termination_rolls_back_on_session_deletion_failure(
    store, friendship, sharing_session, participants,
):
    repo, factory, engine = store
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("DELETE FROM SHARING_SESSIONS"):
            raise RuntimeError("synthetic deletion failure")
    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            repo.terminate_friendship_as_member(friendship.friendship_id, participants[0])
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with factory() as session:
        assert session.get(FriendshipModel, friendship.friendship_id).is_active
        assert session.get(SharingSessionModel, sharing_session.session_id) is not None
