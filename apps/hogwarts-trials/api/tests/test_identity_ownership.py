"""Deterministic tests of trusted identity contracts and ownership policy."""

from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from hogwarts_trials_api.application.attempt_authorization import (
    AttemptAccessDeniedError,
    AttemptOwnership,
    can_access_attempt,
    require_attempt_owner,
)
from hogwarts_trials_api.application.identity import AuthenticatedPrincipal


# Synthetic identifiers, unrelated to any real account or attempt.
USER_ID = UUID("11111111-1111-4000-8000-111111111111")
OTHER_USER_ID = UUID("22222222-2222-4000-8000-222222222222")
ATTEMPT_ID = UUID("33333333-3333-4000-8000-333333333333")
OTHER_ATTEMPT_ID = UUID("44444444-4444-4000-8000-444444444444")
OWNER = AuthenticatedPrincipal(USER_ID)
OTHER_PRINCIPAL = AuthenticatedPrincipal(OTHER_USER_ID)
OWNERSHIP = AttemptOwnership(ATTEMPT_ID, USER_ID)


def test_valid_principal():
    principal = AuthenticatedPrincipal(USER_ID)
    assert principal.user_id == USER_ID


def test_principal_is_immutable():
    principal = AuthenticatedPrincipal(USER_ID)
    with pytest.raises(FrozenInstanceError):
        principal.user_id = OTHER_USER_ID
    assert principal.user_id == USER_ID


@pytest.mark.parametrize("invalid", [None, str(USER_ID), 1, True, b"identifier"])
def test_principal_rejects_non_uuid_without_coercion(invalid):
    with pytest.raises(TypeError, match="user_id must be a UUID"):
        AuthenticatedPrincipal(invalid)


def test_valid_ownership():
    ownership = AttemptOwnership(ATTEMPT_ID, USER_ID)
    assert ownership.attempt_id == ATTEMPT_ID
    assert ownership.owner_user_id == USER_ID


@pytest.mark.parametrize("field", ["attempt_id", "owner_user_id"])
def test_ownership_is_immutable(field):
    ownership = AttemptOwnership(ATTEMPT_ID, USER_ID)
    with pytest.raises(FrozenInstanceError):
        setattr(ownership, field, OTHER_USER_ID)
    assert ownership == OWNERSHIP


@pytest.mark.parametrize("field", ["attempt_id", "owner_user_id"])
@pytest.mark.parametrize("invalid", [None, str(USER_ID), 1, True, b"identifier"])
def test_ownership_rejects_non_uuid_without_coercion(field, invalid):
    values = {"attempt_id": ATTEMPT_ID, "owner_user_id": USER_ID}
    values[field] = invalid
    with pytest.raises(TypeError, match=f"{field} must be a UUID"):
        AttemptOwnership(**values)


@pytest.mark.parametrize(
    "ownership,principal,allowed",
    [
        (OWNERSHIP, OWNER, True),
        (OWNERSHIP, OTHER_PRINCIPAL, False),
        (OWNERSHIP, None, False),
        (None, OWNER, False),
        (None, None, False),
    ],
)
def test_default_deny_policy(ownership, principal, allowed):
    assert can_access_attempt(ownership, principal) is allowed


def test_two_attempts_owned_by_same_user_remain_distinct():
    other = AttemptOwnership(OTHER_ATTEMPT_ID, USER_ID)
    assert other != OWNERSHIP
    assert can_access_attempt(OWNERSHIP, OWNER)
    assert can_access_attempt(other, OWNER)


def test_same_attempt_with_different_owner_is_distinct():
    other = AttemptOwnership(ATTEMPT_ID, OTHER_USER_ID)
    assert other != OWNERSHIP
    assert not can_access_attempt(other, OWNER)
    assert can_access_attempt(other, OTHER_PRINCIPAL)


@pytest.mark.parametrize("principal", [None, OWNER, OTHER_PRINCIPAL])
def test_attempt_uuid_alone_is_not_ownership(principal):
    assert not can_access_attempt(ATTEMPT_ID, principal)


@pytest.mark.parametrize("identifier", [ATTEMPT_ID, USER_ID])
def test_bare_uuid_is_not_authenticated_identity(identifier):
    assert not can_access_attempt(OWNERSHIP, identifier)


def test_attempt_identifier_does_not_determine_owner():
    ownership = AttemptOwnership(USER_ID, OTHER_USER_ID)
    assert not can_access_attempt(ownership, OWNER)
    assert can_access_attempt(ownership, OTHER_PRINCIPAL)


def test_policy_is_deterministic_and_has_no_current_user_fallback(monkeypatch):
    monkeypatch.setenv("USER_ID", str(USER_ID))
    monkeypatch.setenv("CURRENT_USER_ID", str(USER_ID))
    for _ in range(3):
        assert can_access_attempt(OWNERSHIP, OWNER)
        assert not can_access_attempt(OWNERSHIP, OTHER_PRINCIPAL)
        assert not can_access_attempt(OWNERSHIP, None)
        assert not can_access_attempt(None, OWNER)
    assert OWNERSHIP == AttemptOwnership(ATTEMPT_ID, USER_ID)
    assert OWNER == AuthenticatedPrincipal(USER_ID)


def test_guard_allows_matching_owner():
    assert require_attempt_owner(OWNERSHIP, OWNER) is None


@pytest.mark.parametrize(
    "ownership,principal",
    [
        (OWNERSHIP, OTHER_PRINCIPAL),
        (OWNERSHIP, None),
        (None, OWNER),
        (None, None),
        (ATTEMPT_ID, OWNER),
        (OWNERSHIP, USER_ID),
    ],
)
def test_guard_raises_dedicated_error_on_denial(ownership, principal):
    with pytest.raises(AttemptAccessDeniedError, match="Attempt access denied"):
        require_attempt_owner(ownership, principal)
