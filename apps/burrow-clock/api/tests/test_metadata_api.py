"""Deterministic protected HTTP workflows against both repository dialects.

Principals and time are supplied only by dependency overrides, never request identity.
SQLite verifies mapping; the same tests on PostgreSQL exercise real transactions.
"""
from dataclasses import FrozenInstanceError
from datetime import timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import OperationalError

from burrow_clock_api.api.dependencies import (
    SharingStorage, get_current_principal, get_now, get_sharing_repository,
)
from burrow_clock_api.application.identity import AuthenticatedPrincipal
from burrow_clock_api.domain.consent import ConsentGrant, SharingScope
from burrow_clock_api.domain.friendship import Friendship
from burrow_clock_api.domain.sharing import SharingPermission


@pytest.fixture
def api_client(store, friendship, participants, instant):
    from burrow_clock_api.main import app
    actor, clock = [participants[0]], [instant]
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(actor[0])
    app.dependency_overrides[get_now] = lambda: clock[0]
    app.dependency_overrides[get_sharing_repository] = lambda: store[0]
    try:
        with TestClient(app) as client:
            yield SimpleNamespace(
                client=client, repo=store[0], factory=store[1], friendship=friendship,
                a=participants[0], b=participants[1], outsider=participants[2], actor=actor, clock=clock,
                base=f"/api/v1/friendships/{friendship.friendship_id}",
            )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def grant(api, **overrides):
    return api.client.post(api.base + "/permissions", json={
        "recipient_user_id": str(api.b), "scope": "APPROXIMATE", **overrides,
    })


def start(api, **overrides):
    return api.client.post(api.base + "/sessions", json={
        "recipient_user_id": str(api.b), "requested_scope": "PRESENCE",
        "duration_seconds": 60, **overrides,
    })


def read_session(api, identity, **overrides):
    return api.client.get(f"/api/v1/sessions/{identity}", params={
        "sharer_user_id": str(api.a), "requested_scope": "PRESENCE", **overrides,
    })


@pytest.mark.parametrize("invalid", [None, "10000000-0000-4000-8000-000000000001", 1])
def test_principal_requires_uuid_and_is_immutable(invalid):
    with pytest.raises(TypeError):
        AuthenticatedPrincipal(invalid)
    principal = AuthenticatedPrincipal(uuid4())
    with pytest.raises(FrozenInstanceError):
        principal.user_id = uuid4()


PROTECTED = [
    ("GET", "/friendships/with/{id}", None),
    ("DELETE", "/friendships/{id}", None),
    ("POST", "/friendships/{id}/permissions", {}),
    ("GET", "/friendships/{id}/permissions/{id}", None),
    ("DELETE", "/permissions/{id}", None),
    ("POST", "/friendships/{id}/sessions", {}),
    ("GET", "/sessions/{id}", None),
    ("DELETE", "/sessions/{id}", None),
]


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_anonymous_and_forged_identity_denied_before_storage(monkeypatch, method, path, body):
    from burrow_clock_api.main import app
    forbidden = Mock(side_effect=AssertionError("anonymous storage access"))
    monkeypatch.setattr(SharingStorage, "get", forbidden)
    monkeypatch.setenv("BURROW_CLOCK_ALLOW_ANONYMOUS", "1")
    with TestClient(app) as client:
        for headers in [{}, {"X-User-Id": str(uuid4()), "X-Actor-Id": str(uuid4()),
                             "Authorization": "Bearer synthetic-unverified-token"}]:
            response = client.request(method, "/api/v1" + path.format(id=uuid4()),
                                      json=body, headers=headers)
            assert response.status_code == 401
            assert response.json() == {"detail": "Authentication required"}
            assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/v1/health").json() == {"status": "ok", "service": "burrow-clock-api"}
    forbidden.assert_not_called()


def test_friendship_membership_and_termination(api_client):
    api = api_client
    response = api.client.get(f"/api/v1/friendships/with/{api.b}")
    assert response.status_code == 200
    assert response.json() == {"friendship_id": str(api.friendship.friendship_id),
                               "user_a_id": str(api.a), "user_b_id": str(api.b)}
    api.actor[0] = api.outsider
    assert api.client.get(f"/api/v1/friendships/with/{api.b}").status_code == 404
    assert api.client.delete(api.base).status_code == 404
    api.actor[0] = api.b
    assert api.client.get(f"/api/v1/friendships/with/{api.a}").status_code == 200
    assert api.client.delete(api.base).status_code == 204
    assert api.client.delete(api.base).status_code == 404
    assert api.client.get(f"/api/v1/friendships/with/{api.a}").status_code == 404
    api.actor[0] = api.a
    assert grant(api).status_code == 404
    assert start(api).status_code == 404


def test_current_grant_identity_direction_and_server_time(api_client):
    api = api_client
    # A supplied offset is normalized, and the server owns granted_at/identity.
    expiry = (api.clock[0] + timedelta(hours=1)).astimezone(timezone(timedelta(hours=5, minutes=30)))
    response = grant(api, expires_at=expiry.isoformat())
    assert response.status_code == 201
    value = response.json()
    assert UUID(value["permission_id"]).version == 4
    assert value["sharer_user_id"] == str(api.a)
    assert value["recipient_user_id"] == str(api.b)
    assert value["scope"] == "APPROXIMATE"
    assert value["granted_at"] == api.clock[0].isoformat().replace("+00:00", "Z")
    assert value["expires_at"].endswith("Z") and value["revoked_at"] is None
    assert api.client.get(api.base + f"/permissions/{api.b}").json() == value
    api.actor[0] = api.b
    assert api.client.get(api.base + f"/permissions/{api.a}").status_code == 404
    reverse = grant(api, recipient_user_id=str(api.a), scope="PRESENCE")
    assert reverse.status_code == 201 and reverse.json()["permission_id"] != value["permission_id"]
    assert api.client.get(api.base + f"/permissions/{api.a}").json() == reverse.json()
    api.actor[0] = api.a
    assert api.client.get(api.base + f"/permissions/{api.b}").json() == value


@pytest.mark.parametrize("field", ["sharer_user_id", "actor_user_id", "granted_at", "revoked_at",
                                    "permission_id", "is_current", "recipient_identity"])
def test_grant_rejects_identity_and_lifecycle_injection(api_client, field):
    api = api_client
    response = grant(api, **{field: "synthetic-private-input"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request data"}
    assert api.repo.get_current_permission(api.friendship.friendship_id, api.a, api.b) is None


@pytest.mark.parametrize("expiry", ["2029-01-01T00:00:00Z", "2030-01-01T00:00:00Z",
                                     "2031-01-01T00:00:00", "bad", 1893456060, "1893456060"])
def test_invalid_expiry_rejected(api_client, expiry):
    assert grant(api_client, expires_at=expiry).status_code == 422


@pytest.mark.parametrize("scope", ["presence", "UNKNOWN", 1, True])
def test_scope_names_are_strict(api_client, scope):
    assert grant(api_client, scope=scope).status_code == 422
    assert start(api_client, requested_scope=scope).status_code == 422


@pytest.mark.parametrize("scope", ["PRESENCE", "APPROXIMATE", "PRECISE"])
def test_each_stable_scope_name_roundtrips(api_client, scope):
    api = api_client
    assert grant(api, scope=scope).json()["scope"] == scope
    value = start(api, requested_scope=scope)
    assert value.status_code == 201 and value.json()["requested_scope"] == scope
    api.actor[0] = api.b
    assert read_session(api, value.json()["session_id"], requested_scope=scope).status_code == 200


def test_nonmember_self_and_missing_friendship_cannot_grant(api_client):
    api = api_client
    api.actor[0] = api.outsider
    assert grant(api).status_code == 404
    api.actor[0] = api.a
    assert grant(api, recipient_user_id=str(api.a)).status_code == 422
    assert grant(api, recipient_user_id=str(api.outsider)).status_code == 404
    api.base = f"/api/v1/friendships/{uuid4()}"
    assert grant(api).status_code == 404


def test_only_sharer_revokes_current_exact_grant(api_client):
    api = api_client
    identity = grant(api).json()["permission_id"]
    for actor in [api.b, api.outsider]:
        api.actor[0] = actor
        assert api.client.get(api.base + f"/permissions/{api.b}").status_code == 404
        denied = api.client.delete(f"/api/v1/permissions/{identity}")
        missing = api.client.delete(f"/api/v1/permissions/{uuid4()}")
        assert denied.status_code == 404 and denied.json() == missing.json()
    api.actor[0] = api.a
    assert api.client.delete(f"/api/v1/permissions/{identity}").status_code == 204
    assert api.client.delete(f"/api/v1/permissions/{identity}").status_code == 409
    assert start(api).status_code == 404
    assert api.client.get(api.base + f"/permissions/{api.b}").json()["revoked_at"] is not None


def test_authenticated_sharer_can_cancel_pending_consent(api_client):
    api = api_client
    activation = api.clock[0] + timedelta(hours=1)
    pending = SharingPermission(api.friendship.friendship_id, api.a, api.b,
                                ConsentGrant(SharingScope.PRESENCE, activation))
    identity = api.repo.grant_permission(pending)
    scheduled = api.repo.start_session(api.friendship.friendship_id, api.a, api.b,
                                       SharingScope.PRESENCE, activation,
                                       activation + timedelta(seconds=60))
    api.actor[0] = api.b
    reverse = grant(api, recipient_user_id=str(api.a), scope="PRESENCE").json()
    for actor in [api.b, api.outsider]:
        api.actor[0] = actor
        assert api.client.delete(f"/api/v1/permissions/{identity}").status_code == 404
    api.actor[0] = api.a
    assert api.client.get(api.base + f"/permissions/{api.b}").json()["permission_id"] == str(identity)
    response = api.client.delete(f"/api/v1/permissions/{identity}")
    assert response.status_code == 204 and response.content == b""
    assert api.client.get(api.base + f"/permissions/{api.b}").status_code == 404
    assert api.client.delete(f"/api/v1/permissions/{identity}").status_code == 404
    api.clock[0] = activation
    assert start(api).status_code == 404
    api.actor[0] = api.b
    assert read_session(api, scheduled.session_id).status_code == 404
    assert api.client.get(api.base + f"/permissions/{api.a}").json() == reverse
    assert start(api, recipient_user_id=str(api.a)).status_code == 201


def test_regrant_changes_identity_and_never_revives_historical_grants(api_client):
    api = api_client
    old = grant(api).json()["permission_id"]
    session_id = start(api).json()["session_id"]
    new = grant(api).json()["permission_id"]
    assert old != new
    assert api.client.get(api.base + f"/permissions/{api.b}").json()["permission_id"] == new
    assert api.client.delete(f"/api/v1/permissions/{old}").status_code == 404
    api.actor[0] = api.b
    assert read_session(api, session_id).status_code == 404
    api.actor[0] = api.a
    assert api.client.delete(f"/api/v1/permissions/{new}").status_code == 204
    assert start(api).status_code == 404


@pytest.mark.parametrize("duration", [0, 59, 86401, -1, None, True, 60.5, "60"])
def test_duration_is_explicit_strict_and_bounded(api_client, duration):
    assert start(api_client, duration_seconds=duration).status_code == 422


def test_missing_duration_and_extra_session_fields_rejected(api_client):
    api = api_client
    assert api.client.post(api.base + "/sessions", json={"recipient_user_id": str(api.b),
                                                        "requested_scope": "PRESENCE"}).status_code == 422
    for field in ["sharer_user_id", "actor_user_id", "session_id", "permission_id", "started_at", "expires_at"]:
        assert start(api, **{field: str(api.a)}).status_code == 422


@pytest.mark.parametrize("case", ["none", "reverse", "above_scope", "outlives", "future", "expired", "revoked", "outsider", "self"])
def test_session_creation_requires_current_directional_consent(api_client, case):
    api = api_client
    if case != "none":
        identity = grant(api, expires_at=(api.clock[0] + timedelta(minutes=2)).isoformat()).json()["permission_id"]
    if case == "reverse":
        api.actor[0] = api.b
        response = start(api, recipient_user_id=str(api.a))
    elif case == "above_scope":
        response = start(api, requested_scope="PRECISE")
    elif case == "outlives":
        response = start(api, duration_seconds=121)
    elif case == "future":
        api.repo.grant_permission(SharingPermission(api.friendship.friendship_id, api.a, api.b,
                                                  ConsentGrant(SharingScope.PRESENCE, api.clock[0] + timedelta(seconds=1))))
        response = start(api)
    elif case == "expired":
        api.clock[0] += timedelta(minutes=2)
        response = start(api)
    elif case == "revoked":
        assert api.client.delete(f"/api/v1/permissions/{identity}").status_code == 204
        response = start(api)
    elif case == "outsider":
        api.actor[0] = api.outsider
        response = start(api)
    elif case == "self":
        response = start(api, recipient_user_id=str(api.a))
    else:
        response = start(api)
    assert response.status_code == (409 if case == "outlives" else 422 if case == "self" else 404)


@pytest.mark.parametrize("duration", [60, 86400])
def test_session_response_and_authorized_recipient_read(api_client, duration):
    api = api_client
    identity = grant(api).json()["permission_id"]
    response = start(api, duration_seconds=duration)
    assert response.status_code == 201
    value = response.json()
    assert set(value) == {"session_id", "friendship_id", "permission_id", "requested_scope", "started_at", "expires_at"}
    assert value["permission_id"] == identity and UUID(value["session_id"]).version == 4
    assert value["started_at"] == api.clock[0].isoformat().replace("+00:00", "Z")
    assert value["expires_at"] == (api.clock[0] + timedelta(seconds=duration)).isoformat().replace("+00:00", "Z")
    assert read_session(api, value["session_id"]).status_code == 404  # Sharer isn't the recipient.
    api.actor[0] = api.b
    assert read_session(api, value["session_id"]).json() == value
    # Recipient identity in query parameters cannot change the trusted principal.
    api.actor[0] = api.outsider
    assert read_session(api, value["session_id"], recipient_user_id=str(api.b)).status_code == 404


def test_session_can_end_exactly_at_consent_expiry(api_client):
    api = api_client
    expiry = api.clock[0] + timedelta(seconds=120)
    assert grant(api, expires_at=expiry.isoformat()).status_code == 201
    value = start(api, duration_seconds=120)
    assert value.status_code == 201
    api.actor[0] = api.b
    api.clock[0] = expiry - timedelta(microseconds=1)
    assert read_session(api, value.json()["session_id"]).status_code == 200
    api.clock[0] = expiry
    assert read_session(api, value.json()["session_id"]).status_code == 404


@pytest.mark.parametrize("case", ["wrong_scope", "wrong_sharer", "unknown", "expired", "revoked", "terminated", "ended"])
def test_active_read_rechecks_every_boundary(api_client, case):
    api = api_client
    identity = grant(api).json()["permission_id"]
    session_id = start(api).json()["session_id"]
    if case == "expired": api.clock[0] += timedelta(seconds=60)
    if case == "revoked": assert api.client.delete(f"/api/v1/permissions/{identity}").status_code == 204
    if case == "terminated": assert api.client.delete(api.base).status_code == 204
    if case == "ended": assert api.client.delete(f"/api/v1/sessions/{session_id}").status_code == 204
    api.actor[0] = api.b
    params = {}
    if case == "wrong_scope": params["requested_scope"] = "APPROXIMATE"
    if case == "wrong_sharer": params["sharer_user_id"] = str(api.b)
    if case == "unknown": session_id = uuid4()
    response = read_session(api, session_id, **params)
    assert response.status_code == 404 and response.json() == {"detail": "Resource not found"}


def test_only_exact_sharer_can_end_session(api_client):
    api = api_client
    grant(api)
    session_id = start(api).json()["session_id"]
    for actor in [api.b, api.outsider]:
        api.actor[0] = actor
        assert api.client.delete(f"/api/v1/sessions/{session_id}").status_code == 404
    api.actor[0] = api.a
    response = api.client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 204 and response.content == b""
    assert api.client.delete(f"/api/v1/sessions/{session_id}").status_code == 404


def test_refriending_never_reuses_old_consent_or_sessions(api_client):
    api = api_client
    old_grant = grant(api).json()["permission_id"]
    old_session = start(api).json()["session_id"]
    assert api.client.delete(api.base).status_code == 204
    new = api.repo.create_friendship(Friendship(uuid4(), api.a, api.b))
    api.base = f"/api/v1/friendships/{new.friendship_id}"
    assert start(api).status_code == 404
    assert api.client.delete(f"/api/v1/permissions/{old_grant}").status_code == 404
    api.actor[0] = api.b
    assert read_session(api, old_session).status_code == 404


def test_bad_identifiers_are_422_without_echoing_inputs(api_client):
    api = api_client
    for path in ["/api/v1/friendships/with/invalid", "/api/v1/sessions/invalid?sharer_user_id=bad&requested_scope=PRESENCE"]:
        response = api.client.get(path)
        assert response.status_code == 422 and response.json() == {"detail": "Invalid request data"}
    assert grant(api, recipient_user_id="invalid").status_code == 422


def test_unavailable_database_is_safe(api_client, monkeypatch):
    api = api_client
    private_error = "synthetic-private-database-detail"
    monkeypatch.setattr(api.repo, "get_active_friendship_between",
                        Mock(side_effect=OperationalError("statement", {}, Exception(private_error))))
    response = api.client.get(f"/api/v1/friendships/with/{api.b}")
    assert response.status_code == 503 and response.json() == {"detail": "Persistence unavailable"}
    assert private_error not in response.text
