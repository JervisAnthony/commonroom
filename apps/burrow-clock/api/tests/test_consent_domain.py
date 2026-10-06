from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone, tzinfo

import pytest

from burrow_clock_api.domain.consent import (
    ConsentGrant,
    SharingScope,
    is_disclosure_allowed,
)


START = datetime(2030, 1, 1, tzinfo=timezone.utc)
LATER = START + timedelta(hours=1)
END = START + timedelta(hours=2)
TICK = timedelta(microseconds=1)


@pytest.mark.parametrize("scope", list(SharingScope))
def test_valid_non_expiring_grant(scope):
    grant = ConsentGrant(scope, START)
    assert grant.scope is scope
    assert grant.granted_at == START
    assert grant.expires_at is None
    assert grant.revoked_at is None
    assert grant.is_active(START + timedelta(days=36500))


@pytest.mark.parametrize("scope", list(SharingScope))
def test_missing_grant_denies_disclosure(scope):
    assert not is_disclosure_allowed(None, scope, START)


@pytest.mark.parametrize(
    "granted,requested,allowed",
    [
        (SharingScope.PRESENCE, SharingScope.PRESENCE, True),
        (SharingScope.PRESENCE, SharingScope.APPROXIMATE, False),
        (SharingScope.PRESENCE, SharingScope.PRECISE, False),
        (SharingScope.APPROXIMATE, SharingScope.PRESENCE, True),
        (SharingScope.APPROXIMATE, SharingScope.APPROXIMATE, True),
        (SharingScope.APPROXIMATE, SharingScope.PRECISE, False),
        (SharingScope.PRECISE, SharingScope.PRESENCE, True),
        (SharingScope.PRECISE, SharingScope.APPROXIMATE, True),
        (SharingScope.PRECISE, SharingScope.PRECISE, True),
    ],
)
def test_disclosure_ceiling(granted, requested, allowed):
    assert is_disclosure_allowed(ConsentGrant(granted, START), requested, START) is allowed


@pytest.mark.parametrize("at,active", [(START - TICK, False), (START, True)])
def test_grant_start_boundary(at, active):
    grant = ConsentGrant(SharingScope.PRESENCE, START)
    assert grant.is_active(at) is active
    assert is_disclosure_allowed(grant, SharingScope.PRESENCE, at) is active


@pytest.mark.parametrize("at,active", [(END - TICK, True), (END, False), (END + TICK, False)])
def test_expiration_boundary(at, active):
    grant = ConsentGrant(SharingScope.PRECISE, START, expires_at=END)
    assert grant.is_active(at) is active
    for scope in SharingScope:
        assert is_disclosure_allowed(grant, scope, at) is active


@pytest.mark.parametrize("expires_at", [START, START - TICK])
def test_expiration_must_follow_grant(expires_at):
    with pytest.raises(ValueError, match="strictly later"):
        ConsentGrant(SharingScope.PRESENCE, START, expires_at=expires_at)


class NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt):
        return None


@pytest.mark.parametrize("field", ["granted_at", "expires_at", "revoked_at"])
@pytest.mark.parametrize("invalid", [START.replace(tzinfo=None), START.replace(tzinfo=NoOffsetTimezone())])
def test_construction_rejects_naive_timestamps(field, invalid):
    terms = {"scope": SharingScope.PRESENCE, "granted_at": START}
    terms[field] = invalid
    with pytest.raises(ValueError, match=f"{field} must be a timezone-aware datetime"):
        ConsentGrant(**terms)


def test_revocation_returns_new_immutable_value():
    original = ConsentGrant(SharingScope.APPROXIMATE, START, expires_at=END)
    revoked = original.revoke(LATER)
    assert revoked is not original
    assert revoked == ConsentGrant(SharingScope.APPROXIMATE, START, END, LATER)
    assert original.revoked_at is None
    assert original.is_active(LATER)
    with pytest.raises(FrozenInstanceError):
        revoked.revoked_at = None
    with pytest.raises(FrozenInstanceError):
        original.scope = SharingScope.PRECISE


@pytest.mark.parametrize("expires_at", [None, END])
@pytest.mark.parametrize("at,active", [(LATER - TICK, True), (LATER, False), (LATER + TICK, False)])
def test_revocation_boundary(expires_at, at, active):
    grant = ConsentGrant(SharingScope.PRECISE, START, expires_at=expires_at).revoke(LATER)
    assert grant.is_active(at) is active
    for scope in SharingScope:
        assert is_disclosure_allowed(grant, scope, at) is active


@pytest.mark.parametrize("via_operation", [False, True])
def test_revocation_before_grant_is_invalid(via_operation):
    with pytest.raises(ValueError, match="not be earlier"):
        if via_operation:
            ConsentGrant(SharingScope.PRESENCE, START).revoke(START - TICK)
        else:
            ConsentGrant(SharingScope.PRESENCE, START, revoked_at=START - TICK)


def test_revocation_at_grant_start_is_valid_and_inactive():
    grant = ConsentGrant(SharingScope.PRESENCE, START).revoke(START)
    assert not is_disclosure_allowed(grant, SharingScope.PRESENCE, START)


def test_revocation_rejects_naive_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        ConsentGrant(SharingScope.PRESENCE, START).revoke(LATER.replace(tzinfo=None))


@pytest.mark.parametrize("at", [START, LATER, END])
def test_repeat_revocation_is_invalid(at):
    revoked = ConsentGrant(SharingScope.PRESENCE, START).revoke(LATER)
    with pytest.raises(ValueError, match="already revoked"):
        revoked.revoke(at)
    assert revoked.revoked_at == LATER


@pytest.mark.parametrize("missing", [False, True])
def test_disclosure_evaluation_rejects_naive_time_even_without_grant(missing):
    grant = None if missing else ConsentGrant(SharingScope.PRESENCE, START)
    with pytest.raises(ValueError, match="timezone-aware"):
        is_disclosure_allowed(grant, SharingScope.PRESENCE, START.replace(tzinfo=None))


def test_activity_evaluation_rejects_naive_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        ConsentGrant(SharingScope.PRESENCE, START).is_active(START.replace(tzinfo=None))


def test_expiry_precedes_later_revocation():
    grant = ConsentGrant(SharingScope.PRECISE, START, expires_at=LATER).revoke(END)
    assert not is_disclosure_allowed(grant, SharingScope.PRESENCE, LATER)


def test_different_timezone_offsets_compare_absolute_instants():
    offset = timezone(timedelta(hours=5, minutes=30))
    grant = ConsentGrant(SharingScope.PRECISE, START.astimezone(offset), expires_at=END)
    revoked = grant.revoke(LATER.astimezone(offset))
    assert is_disclosure_allowed(revoked, SharingScope.PRECISE, LATER - TICK)
    assert not is_disclosure_allowed(revoked, SharingScope.PRESENCE, LATER)
    assert not is_disclosure_allowed(grant, SharingScope.PRESENCE, END.astimezone(offset))
    with pytest.raises(ValueError, match="strictly later"):
        ConsentGrant(SharingScope.PRESENCE, START, expires_at=START.astimezone(offset))
    with pytest.raises(ValueError, match="not be earlier"):
        grant.revoke((START - TICK).astimezone(offset))


class RollbackTimezone(tzinfo):
    """Synthetic repeated clock hour with two distinct absolute instants."""

    def utcoffset(self, dt):
        return timedelta(hours=-5 if dt.fold else -4)


def test_repeated_clock_hour_uses_absolute_time_for_construction():
    zone = RollbackTimezone()
    first = datetime(2030, 1, 1, 1, 30, tzinfo=zone, fold=0)
    second = first.replace(fold=1)
    grant = ConsentGrant(SharingScope.PRESENCE, first, expires_at=second)
    assert grant.is_active(first)
    assert not grant.is_active(second)
    with pytest.raises(ValueError, match="strictly later"):
        ConsentGrant(SharingScope.PRESENCE, second, expires_at=first)
    with pytest.raises(ValueError, match="not be earlier"):
        ConsentGrant(SharingScope.PRESENCE, second).revoke(first)


@pytest.mark.parametrize("boundary", ["expires_at", "revoked_at"])
def test_repeated_clock_hour_cannot_extend_consent(boundary):
    zone = RollbackTimezone()
    start = datetime(2030, 1, 1, 0, tzinfo=zone)
    cutoff = start.replace(hour=1, minute=30)
    after = cutoff.replace(minute=0, fold=1)
    grant = ConsentGrant(SharingScope.PRECISE, start, **{boundary: cutoff})
    assert not is_disclosure_allowed(grant, SharingScope.PRESENCE, after)


def test_repeated_clock_hour_cannot_start_consent_early():
    zone = RollbackTimezone()
    start = datetime(2030, 1, 1, 1, tzinfo=zone, fold=1)
    before = start.replace(minute=30, fold=0)
    assert not is_disclosure_allowed(ConsentGrant(SharingScope.PRESENCE, start), SharingScope.PRESENCE, before)


@pytest.mark.parametrize("invalid", [None, "PRECISE", 3])
def test_invalid_granted_scope_is_rejected(invalid):
    with pytest.raises(ValueError, match="SharingScope"):
        ConsentGrant(invalid, START)


@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize("invalid", [None, "PRECISE", 3])
def test_invalid_requested_scope_is_rejected(missing, invalid):
    grant = None if missing else ConsentGrant(SharingScope.PRESENCE, START)
    with pytest.raises(ValueError, match="SharingScope"):
        is_disclosure_allowed(grant, invalid, START)
