from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from burrow_clock_api.application.repositories import (
    FriendshipRepository,
    SharingPermissionRepository,
)
from burrow_clock_api.domain.consent import ConsentGrant, SharingScope
from burrow_clock_api.domain.friendship import Friendship
from burrow_clock_api.domain.sharing import SharingPermission, is_friend_disclosure_allowed


A, B, C, D, FRIENDSHIP_ID, OTHER_ID = (UUID(int=n) for n in range(1, 7))
START = datetime(2030, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(hours=1)
TICK = timedelta(microseconds=1)
FRIENDSHIP = Friendship(FRIENDSHIP_ID, A, B)
GRANT = ConsentGrant(SharingScope.APPROXIMATE, START)
PERMISSION = SharingPermission(FRIENDSHIP_ID, A, B, GRANT)


def allowed(friendship=FRIENDSHIP, permission=PERMISSION, sharer=A, recipient=B,
            scope=SharingScope.PRESENCE, at=START):
    return is_friend_disclosure_allowed(friendship, permission, sharer, recipient, scope, at)


def test_valid_friendship():
    assert FRIENDSHIP.friendship_id == FRIENDSHIP_ID
    assert FRIENDSHIP.user_a_id == A
    assert FRIENDSHIP.user_b_id == B


@pytest.mark.parametrize("field", ["friendship_id", "user_a_id", "user_b_id"])
def test_friendship_is_immutable(field):
    with pytest.raises(FrozenInstanceError):
        setattr(FRIENDSHIP, field, OTHER_ID)


@pytest.mark.parametrize("field", ["friendship_id", "user_a_id", "user_b_id"])
@pytest.mark.parametrize("invalid", [None, 1, str(A)])
def test_friendship_rejects_non_uuid(field, invalid):
    with pytest.raises(TypeError, match=f"{field} must be a UUID"):
        replace(FRIENDSHIP, **{field: invalid})


def test_friendship_rejects_identical_members():
    with pytest.raises(ValueError, match="distinct"):
        Friendship(FRIENDSHIP_ID, A, A)


@pytest.mark.parametrize("user,expected", [(A, True), (B, True), (C, False), (str(A), False)])
def test_contains_user(user, expected):
    assert FRIENDSHIP.contains_user(user) is expected


@pytest.mark.parametrize("one,two,expected", [
    (A, B, True), (B, A, True), (A, C, False), (C, D, False),
    (A, A, False), (str(A), B, False),
])
def test_connects(one, two, expected):
    assert FRIENDSHIP.connects(one, two) is expected


def test_valid_permission():
    assert PERMISSION.friendship_id == FRIENDSHIP_ID
    assert PERMISSION.sharer_user_id == A
    assert PERMISSION.recipient_user_id == B
    assert PERMISSION.grant is GRANT


@pytest.mark.parametrize("field", ["friendship_id", "sharer_user_id", "recipient_user_id", "grant"])
def test_permission_is_immutable(field):
    with pytest.raises(FrozenInstanceError):
        setattr(PERMISSION, field, None)


@pytest.mark.parametrize("field", ["friendship_id", "sharer_user_id", "recipient_user_id"])
@pytest.mark.parametrize("invalid", [None, 1, str(A)])
def test_permission_rejects_non_uuid(field, invalid):
    with pytest.raises(TypeError, match=f"{field} must be a UUID"):
        replace(PERMISSION, **{field: invalid})


def test_permission_rejects_identical_parties():
    with pytest.raises(ValueError, match="distinct"):
        SharingPermission(FRIENDSHIP_ID, A, A, GRANT)


@pytest.mark.parametrize("invalid", [None, object(), SharingScope.PRESENCE, {}])
def test_permission_rejects_non_grant(invalid):
    with pytest.raises(TypeError, match="grant must be a ConsentGrant"):
        replace(PERMISSION, grant=invalid)


@pytest.mark.parametrize("granted", list(SharingScope))
@pytest.mark.parametrize("requested", list(SharingScope))
def test_scope_ceiling(granted, requested):
    permission = replace(PERMISSION, grant=ConsentGrant(granted, START))
    expected = {
        SharingScope.PRESENCE: {SharingScope.PRESENCE},
        SharingScope.APPROXIMATE: {SharingScope.PRESENCE, SharingScope.APPROXIMATE},
        SharingScope.PRECISE: set(SharingScope),
    }
    assert allowed(permission=permission, scope=requested) is (requested in expected[granted])


@pytest.mark.parametrize("friendship,permission", [
    (None, PERMISSION), (FRIENDSHIP, None), (None, None),
    (object(), PERMISSION), (FRIENDSHIP, object()),
    (SimpleNamespace(**FRIENDSHIP.__dict__), PERMISSION),
    (FRIENDSHIP, SimpleNamespace(**PERMISSION.__dict__)),
])
def test_missing_or_malformed_facts_deny(friendship, permission):
    assert not allowed(friendship=friendship, permission=permission)


@pytest.mark.parametrize("friendship", [
    Friendship(FRIENDSHIP_ID, A, C), Friendship(FRIENDSHIP_ID, C, D),
    Friendship(OTHER_ID, A, B),
])
def test_wrong_friendship_denies(friendship):
    assert not allowed(friendship=friendship)


@pytest.mark.parametrize("permission", [
    replace(PERMISSION, friendship_id=OTHER_ID),
    replace(PERMISSION, sharer_user_id=C),
    replace(PERMISSION, recipient_user_id=C),
    SharingPermission(FRIENDSHIP_ID, C, D, GRANT),
])
def test_mismatched_permission_denies(permission):
    assert not allowed(permission=permission)


@pytest.mark.parametrize("sharer,recipient", [
    (A, A), (C, B), (A, C), (None, B), (A, None), (str(A), B), (A, str(B)),
])
def test_invalid_or_wrong_requested_parties_deny(sharer, recipient):
    assert not allowed(sharer=sharer, recipient=recipient)


def test_friendship_order_is_not_directional():
    assert allowed(friendship=Friendship(FRIENDSHIP_ID, B, A))


def test_reverse_direction_requires_independent_permission():
    assert allowed()
    assert not allowed(sharer=B, recipient=A)
    reverse = SharingPermission(FRIENDSHIP_ID, B, A, ConsentGrant(SharingScope.PRESENCE, START))
    assert allowed(permission=reverse, sharer=B, recipient=A)
    assert not allowed(permission=reverse, sharer=B, recipient=A, scope=SharingScope.APPROXIMATE)
    assert not allowed(permission=reverse)


def test_relationship_termination_denies_stale_active_permission():
    assert allowed()
    assert not allowed(friendship=None)
    assert PERMISSION.grant.is_active(START)
    assert PERMISSION.grant.revoked_at is None


@pytest.mark.parametrize("at,expected", [(START - TICK, False), (START, True)])
def test_grant_activation_boundary(at, expected):
    assert allowed(at=at) is expected


@pytest.mark.parametrize("field", ["expires_at", "revoked_at"])
@pytest.mark.parametrize("at,expected", [(END - TICK, True), (END, False), (END + TICK, False)])
def test_consent_termination_boundary(field, at, expected):
    permission = replace(PERMISSION, grant=replace(GRANT, **{field: END}))
    assert allowed(permission=permission, at=at) is expected


@pytest.mark.parametrize("scope,at", [
    ("presence", START), (SharingScope.PRESENCE, START.replace(tzinfo=None)),
])
def test_consent_evaluation_validation_is_preserved(scope, at):
    with pytest.raises(ValueError):
        allowed(scope=scope, at=at)


def test_read_only_repository_protocols_accept_structural_test_doubles():
    class ActiveFriendshipLookup:
        def get_active_friendship_between(self, user_a_id: UUID, user_b_id: UUID) -> Friendship | None:
            return FRIENDSHIP if FRIENDSHIP.connects(user_a_id, user_b_id) else None

    class DirectionalPermissionLookup:
        def get_permission(self, friendship_id: UUID, sharer_user_id: UUID,
                           recipient_user_id: UUID) -> SharingPermission | None:
            if (friendship_id, sharer_user_id, recipient_user_id) == (FRIENDSHIP_ID, A, B):
                return PERMISSION
            return None

    friendships: FriendshipRepository = ActiveFriendshipLookup()
    permissions: SharingPermissionRepository = DirectionalPermissionLookup()
    assert isinstance(friendships, FriendshipRepository)
    assert isinstance(permissions, SharingPermissionRepository)
    assert not isinstance(object(), FriendshipRepository)
    assert not isinstance(object(), SharingPermissionRepository)
    assert friendships.get_active_friendship_between(A, B) is FRIENDSHIP
    assert friendships.get_active_friendship_between(B, A) is FRIENDSHIP
    assert friendships.get_active_friendship_between(A, C) is None
    assert permissions.get_permission(FRIENDSHIP_ID, A, B) is PERMISSION
    assert permissions.get_permission(FRIENDSHIP_ID, B, A) is None
    assert permissions.get_permission(OTHER_ID, A, B) is None
    assert permissions.get_permission(FRIENDSHIP_ID, A, C) is None
