"""Authoritative PostgreSQL uniqueness and privacy-transition locking checks."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier, Event, current_thread
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from burrow_clock_api.domain.friendship import Friendship
from burrow_clock_api.domain.consent import SharingScope
from burrow_clock_api.infrastructure.database import create_session_factory
from burrow_clock_api.infrastructure.models import FriendshipModel, SharingPermissionModel, SharingSessionModel
from burrow_clock_api.infrastructure.postgres_sharing_repository import PostgresSharingRepository


@pytest.fixture(params=["postgres"])
def live_store(request, postgres_engine):
    factory = create_session_factory(postgres_engine)
    with factory.begin() as session:
        session.query(FriendshipModel).delete()
    yield PostgresSharingRepository(factory), factory, postgres_engine
    with factory.begin() as session:
        session.query(FriendshipModel).delete()


def test_concurrent_active_pair_has_exactly_one_winner(live_store, participants):
    repo, factory, _ = live_store
    ready = Barrier(2, timeout=10)

    def create(reverse):
        ready.wait()
        try:
            pair = participants[:2] if not reverse else participants[:2][::-1]
            return repo.create_friendship(Friendship(uuid4(), *pair))
        except IntegrityError:
            return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(create, [False, True]))
    assert results.count(None) == 1
    with factory() as session:
        assert len(session.scalars(select(FriendshipModel)).all()) == 1


@pytest.mark.parametrize("transition", ["terminate", "revoke", "regrant"])
def test_session_start_waits_for_privacy_transition(live_store, participants, instant, transition):
    from burrow_clock_api.domain.consent import ConsentGrant
    from burrow_clock_api.domain.sharing import SharingPermission
    repo, factory, engine = live_store
    friendship = repo.create_friendship(Friendship(uuid4(), *participants[:2]))
    permission = SharingPermission(friendship.friendship_id, *participants[:2],
                                   ConsentGrant(SharingScope.PRESENCE, instant, instant + timedelta(hours=2)))
    grant_id = repo.grant_permission(permission)
    reached_parent_lock = Event()

    def observe(connection, cursor, statement, parameters, context, executemany):
        if current_thread().name.startswith("contender") and "friendships" in statement and "FOR UPDATE" in statement:
            reached_parent_lock.set()

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="contender") as workers:
            with factory.begin() as writer:
                parent = writer.scalars(select(FriendshipModel).where(
                    FriendshipModel.friendship_id == friendship.friendship_id
                ).with_for_update()).one()
                grant = writer.get(SharingPermissionModel, grant_id)
                if transition == "terminate": parent.is_active = False
                if transition == "revoke": grant.revoked_at = instant
                if transition == "regrant":
                    grant.is_current = False
                    writer.flush()
                    writer.add(SharingPermissionModel(
                        permission_id=uuid4(), friendship_id=friendship.friendship_id,
                        sharer_user_id=participants[0], recipient_user_id=participants[1],
                        scope="PRESENCE", granted_at=instant + timedelta(minutes=1), is_current=True,
                    ))
                writer.flush()
                future = workers.submit(repo.start_session, friendship.friendship_id, *participants[:2],
                                        SharingScope.PRESENCE, instant, instant + timedelta(hours=1))
                assert reached_parent_lock.wait(10), "contender did not reach the PostgreSQL parent row lock"
                assert not future.done()
            # Writer committed before the blocked reader's authorization check proceeds.
            with pytest.raises(ValueError):
                future.result(timeout=10)
        with factory() as session:
            assert session.scalars(select(SharingSessionModel)).all() == []
    finally:
        event.remove(engine, "before_cursor_execute", observe)


def test_concurrent_sessions_and_regrants_have_unambiguous_binding(live_store, participants, instant):
    from burrow_clock_api.domain.consent import ConsentGrant
    from burrow_clock_api.domain.sharing import SharingPermission
    repo, factory, _ = live_store
    friendship = repo.create_friendship(Friendship(uuid4(), *participants[:2]))
    permission = SharingPermission(friendship.friendship_id, *participants[:2],
                                   ConsentGrant(SharingScope.PRESENCE, instant, instant + timedelta(hours=2)))
    original_id = repo.grant_permission(permission)
    ready = Barrier(2, timeout=10)

    def start(_):
        ready.wait()
        return repo.start_session(friendship.friendship_id, *participants[:2], SharingScope.PRESENCE,
                                  instant, instant + timedelta(hours=1))

    with ThreadPoolExecutor(max_workers=2) as workers:
        sessions = list(workers.map(start, range(2)))
    assert sessions[0].session_id != sessions[1].session_id
    assert all(value.permission_id == original_id for value in sessions)
    ready = Barrier(2, timeout=10)

    def grant(_):
        ready.wait()
        return repo.grant_permission(permission)

    with ThreadPoolExecutor(max_workers=2) as workers:
        ids = list(workers.map(grant, range(2)))
    assert ids[0] != ids[1]
    with factory() as session:
        current = session.scalars(select(SharingPermissionModel).where(SharingPermissionModel.is_current.is_(True))).all()
        assert len(current) == 1 and current[0].permission_id in ids
        assert session.scalars(select(SharingSessionModel)).all() == []
    for value in sessions:
        assert repo.get_active_session(value.session_id, *participants[:2], SharingScope.PRESENCE, instant) is None
