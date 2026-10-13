"""Pure immutable session interval metadata, without authorization shortcuts."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from burrow_clock_api.domain.consent import SharingScope
from burrow_clock_api.domain.session import SharingSession

T = datetime(2030, 1, 1, tzinfo=timezone.utc)
ID = UUID("11111111-1111-4111-8111-111111111111")


def session(**overrides):
    fields = dict(session_id=ID, friendship_id=ID, permission_id=ID,
                  requested_scope=SharingScope.PRESENCE, started_at=T, expires_at=T + timedelta(hours=1))
    fields.update(overrides)
    return SharingSession(**fields)


def test_frozen_interval_exact_boundaries():
    value = session()
    assert not value.is_active(T - timedelta(microseconds=1))
    assert value.is_active(T)
    assert value.is_active(value.expires_at - timedelta(microseconds=1))
    assert not value.is_active(value.expires_at)
    with pytest.raises(FrozenInstanceError):
        value.expires_at = T
    with pytest.raises(ValueError):
        value.is_active(T.replace(tzinfo=None))


@pytest.mark.parametrize("fields,error", [
    ({"session_id": str(ID)}, TypeError), ({"friendship_id": None}, TypeError),
    ({"permission_id": str(ID)}, TypeError), ({"requested_scope": "PRESENCE"}, ValueError),
    ({"started_at": T.replace(tzinfo=None)}, ValueError), ({"expires_at": None}, ValueError),
    ({"expires_at": T}, ValueError), ({"expires_at": T - timedelta(seconds=1)}, ValueError),
])
def test_invalid_session_metadata(fields, error):
    with pytest.raises(error):
        session(**fields)


def test_interval_uses_utc_across_repeated_local_clock_hour():
    from zoneinfo import ZoneInfo
    zone = ZoneInfo("America/New_York")
    first = datetime(2030, 11, 3, 1, 30, tzinfo=zone, fold=0)
    second = datetime(2030, 11, 3, 1, 15, tzinfo=zone, fold=1)
    value = session(started_at=first, expires_at=second)
    assert value.is_active(first)
    assert value.is_active(second.astimezone(timezone.utc) - timedelta(microseconds=1))
    assert not value.is_active(second)
