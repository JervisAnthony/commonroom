"""Repository behavior on SQLite and authoritative PostgreSQL, without a client workflow."""
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from burrow_clock_api.application.repositories import FriendshipRepository, SharingPermissionRepository, SharingSessionRepository
from burrow_clock_api.domain.friendship import Friendship
from burrow_clock_api.infrastructure.models import FriendshipModel, SharingPermissionModel, SharingSessionModel


def test_protocols_and_order_independent_lookup(store, friendship):
    repo, _, _ = store
    assert isinstance(repo, FriendshipRepository)
    assert isinstance(repo, SharingPermissionRepository)
    assert isinstance(repo, SharingSessionRepository)
    assert repo.get_active_friendship_between(friendship.user_a_id, friendship.user_b_id) == friendship
    assert repo.get_active_friendship_between(friendship.user_b_id, friendship.user_a_id) == friendship


def test_distinct_pair_and_missing_relationship(store, friendship, participants):
    repo = store[0]
    assert repo.get_active_friendship_between(participants[0], participants[2]) is None
    other = repo.create_friendship(Friendship(uuid4(), participants[3], participants[2]))
    assert other.user_a_id < other.user_b_id
    assert repo.get_active_friendship_between(participants[3], participants[2]) == other
    assert repo.get_active_friendship_between(participants[0], participants[1]) == friendship


def test_duplicate_active_pair_is_database_rejected(store, friendship):
    repo, factory, _ = store
    with pytest.raises(IntegrityError):
        repo.create_friendship(Friendship(uuid4(), friendship.user_b_id, friendship.user_a_id))
    with factory() as session:
        assert len(session.scalars(select(FriendshipModel)).all()) == 1
    assert repo.get_active_friendship_between(friendship.user_a_id, friendship.user_b_id) == friendship


@pytest.mark.parametrize("bad_pair", ["self", "reversed"])
def test_database_canonical_pair_constraint(store, participants, bad_pair):
    _, factory, _ = store
    low, high = participants[:2]
    with pytest.raises(IntegrityError):
        with factory.begin() as session:
            session.add(FriendshipModel(friendship_id=uuid4(), user_a_id=high,
                                        user_b_id=high if bad_pair == "self" else low, is_active=True))
    with factory() as session:
        assert session.scalars(select(FriendshipModel)).all() == []


def test_termination_new_id_and_stale_permissions(store, friendship, grant_id, sharing_session):
    repo, factory, _ = store
    assert repo.terminate_friendship(friendship.friendship_id)
    assert not repo.terminate_friendship(friendship.friendship_id)
    assert repo.get_active_friendship_between(friendship.user_a_id, friendship.user_b_id) is None
    assert repo.get_permission(friendship.friendship_id, friendship.user_a_id, friendship.user_b_id) is None
    with pytest.raises(IntegrityError):
        repo.create_friendship(friendship)
    new = repo.create_friendship(Friendship(uuid4(), friendship.user_b_id, friendship.user_a_id))
    assert new.friendship_id != friendship.friendship_id
    assert repo.get_permission(new.friendship_id, new.user_a_id, new.user_b_id) is None
    with factory() as session:
        assert not session.get(FriendshipModel, friendship.friendship_id).is_active
        assert session.get(SharingPermissionModel, grant_id) is not None
        assert session.get(SharingSessionModel, sharing_session.session_id) is None


def test_invalid_identifier_types(store, participants):
    repo = store[0]
    with pytest.raises(TypeError):
        repo.get_active_friendship_between(str(participants[0]), participants[1])
    with pytest.raises(TypeError):
        repo.terminate_friendship(str(uuid4()))
    with pytest.raises(TypeError):
        repo.create_friendship(uuid4())
    with pytest.raises(ValueError):
        Friendship(uuid4(), participants[0], participants[0])
    with pytest.raises(TypeError):
        Friendship(str(uuid4()), *participants[:2])


def test_friendship_insert_failure_has_no_partial_state(store, participants):
    repo, factory, _ = store
    value = Friendship(uuid4(), *participants[:2])

    def fail(mapper, connection, target):
        raise RuntimeError("synthetic insert failure")

    event.listen(FriendshipModel, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            repo.create_friendship(value)
    finally:
        event.remove(FriendshipModel, "before_insert", fail)
    with factory() as session:
        assert session.get(FriendshipModel, value.friendship_id) is None
