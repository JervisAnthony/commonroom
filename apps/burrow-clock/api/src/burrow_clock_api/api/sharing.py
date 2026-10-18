"""Authenticated metadata workflows; no public friendship creation or location disclosure."""

from datetime import timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from burrow_clock_api.api.dependencies import NowDep, PrincipalDep, RepositoryDep
from burrow_clock_api.api.schemas import (
    FriendshipResponse, GrantRequest, PermissionResponse, ScopeName,
    SessionRequest, SessionResponse, permission_response, session_response,
)
from burrow_clock_api.application.repositories import CurrentPermission, SharingStateConflict
from burrow_clock_api.domain.consent import ConsentGrant, SharingScope
from burrow_clock_api.domain.sharing import SharingPermission

router = APIRouter(prefix="/api/v1", tags=["sharing metadata"])


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Resource not found")


def distinct(sharer: UUID, recipient: UUID) -> None:
    if sharer == recipient:
        raise HTTPException(status_code=422, detail="Sharing requires distinct participants")


@router.get("/friendships/with/{other_user_id}", response_model=FriendshipResponse)
def get_friendship(other_user_id: UUID, principal: PrincipalDep, repo: RepositoryDep):
    value = repo.get_active_friendship_between(principal.user_id, other_user_id)
    if value is None:
        raise not_found()
    return FriendshipResponse(friendship_id=value.friendship_id,
                              user_a_id=value.user_a_id, user_b_id=value.user_b_id)


@router.delete("/friendships/{friendship_id}", status_code=204)
def terminate_friendship(friendship_id: UUID, principal: PrincipalDep, repo: RepositoryDep):
    if not repo.terminate_friendship_as_member(friendship_id, principal.user_id):
        raise not_found()
    return Response(status_code=204)


@router.post("/friendships/{friendship_id}/permissions", status_code=201,
             response_model=PermissionResponse)
def grant_permission(friendship_id: UUID, body: GrantRequest, principal: PrincipalDep,
                     repo: RepositoryDep, now: NowDep):
    distinct(principal.user_id, body.recipient_user_id)
    try:
        grant = ConsentGrant(SharingScope[body.scope], now.astimezone(timezone.utc), body.expires_at)
    except ValueError:
        raise HTTPException(status_code=422, detail="Expiry must be later than grant creation") from None
    permission = SharingPermission(friendship_id, principal.user_id, body.recipient_user_id, grant)
    try:
        identity = repo.grant_permission(permission)
    except ValueError:
        raise not_found() from None
    return permission_response(CurrentPermission(identity, permission))


@router.get("/friendships/{friendship_id}/permissions/{recipient_user_id}",
            response_model=PermissionResponse)
def get_permission(friendship_id: UUID, recipient_user_id: UUID,
                   principal: PrincipalDep, repo: RepositoryDep):
    value = repo.get_current_permission(friendship_id, principal.user_id, recipient_user_id)
    if value is None:
        raise not_found()
    return permission_response(value)


@router.delete("/permissions/{permission_id}", status_code=204)
def revoke_permission(permission_id: UUID, principal: PrincipalDep, repo: RepositoryDep, now: NowDep):
    if not repo.revoke_permission_as_sharer(permission_id, principal.user_id, now):
        raise not_found()
    return Response(status_code=204)


@router.post("/friendships/{friendship_id}/sessions", status_code=201, response_model=SessionResponse)
def start_session(friendship_id: UUID, body: SessionRequest, principal: PrincipalDep,
                  repo: RepositoryDep, now: NowDep):
    distinct(principal.user_id, body.recipient_user_id)
    start = now.astimezone(timezone.utc)
    try:
        value = repo.start_session(friendship_id, principal.user_id, body.recipient_user_id,
                                   SharingScope[body.requested_scope], start,
                                   start + timedelta(seconds=body.duration_seconds))
    except SharingStateConflict:
        raise
    except ValueError:
        raise not_found() from None
    return session_response(value)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID, sharer_user_id: UUID, requested_scope: ScopeName,
                principal: PrincipalDep, repo: RepositoryDep, now: NowDep):
    value = repo.get_active_session(session_id, sharer_user_id, principal.user_id,
                                    SharingScope[requested_scope], now)
    if value is None:
        raise not_found()
    return session_response(value)


@router.delete("/sessions/{session_id}", status_code=204)
def end_session(session_id: UUID, principal: PrincipalDep, repo: RepositoryDep):
    if not repo.end_session_as_sharer(session_id, principal.user_id):
        raise not_found()
    return Response(status_code=204)
