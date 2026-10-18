"""SQLite adapter checks and authoritative, separately configured PostgreSQL checks."""
import os
from pathlib import Path
import re

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import StaticPool

from burrow_clock_api.infrastructure.database import create_db_engine, create_session_factory, validate_database_url
from burrow_clock_api.infrastructure.models import Base, FriendshipModel, SharingPermissionModel, SharingSessionModel
from burrow_clock_api.infrastructure.postgres_sharing_repository import PostgresSharingRepository

TEST_URL = os.environ.get("BURROW_CLOCK_TEST_DATABASE_URL")
REQUIRE_POSTGRES = os.environ.get("BURROW_CLOCK_REQUIRE_POSTGRES_TESTS") == "1"
_postgres_reports = []


def validate_test_database_url(test_url: str | None, production_url: str | None = None) -> str:
    """Allow only explicit dedicated Burrow test targets, distinct from production.

    Credentials and transport options do not distinguish database targets. Reject
    libpq routing overrides rather than guessing their effective connection target.
    Errors deliberately contain no supplied URLs or underlying parser details.
    """
    if not test_url:
        raise ValueError("BURROW_CLOCK_TEST_DATABASE_URL is required; no production fallback")

    def parse(value):
        try:
            parsed = make_url(validate_database_url(value))
            if set(parsed.query) & {"host", "hostaddr", "port", "dbname", "database", "service", "servicefile"}:
                raise ValueError("ambiguous connection target")
            return parsed
        except (ArgumentError, TypeError, ValueError):
            raise ValueError("Database safety validation requires a valid PostgreSQL URL without routing overrides") from None

    test = parse(test_url)
    if not re.fullmatch(r"burrow_clock_test(?:_[a-z0-9][a-z0-9_]*)?", test.database or ""):
        raise ValueError("Test database must be burrow_clock_test or burrow_clock_test_<safe_suffix>")
    if production_url:
        production = parse(production_url)

        def target(url):
            return ((url.host or "").lower().rstrip("."), url.port or 5432, url.database)

        if target(test) == target(production):
            raise ValueError("Test and production database targets must be distinct")
    return test.render_as_string(hide_password=False)


def pytest_sessionstart(session):
    if REQUIRE_POSTGRES and not TEST_URL:
        raise pytest.UsageError("CI requires BURROW_CLOCK_TEST_DATABASE_URL; PostgreSQL tests must not skip")
    if TEST_URL:
        try:
            validate_test_database_url(TEST_URL, os.environ.get("BURROW_CLOCK_DATABASE_URL"))
        except ValueError as exc:
            raise pytest.UsageError(str(exc)) from None


def pytest_runtest_logreport(report):
    if "[postgres" in report.nodeid:
        _postgres_reports.append(report)


def pytest_sessionfinish(session, exitstatus):
    if REQUIRE_POSTGRES and (
        not any(r.when == "call" for r in _postgres_reports)
        or any(r.skipped for r in _postgres_reports)
    ):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(scope="session")
def migration_config():
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    # Explicit test config wins over any inherited production database variable.
    if TEST_URL:
        safe_url = validate_test_database_url(TEST_URL, os.environ.get("BURROW_CLOCK_DATABASE_URL"))
        config.set_main_option("sqlalchemy.url", safe_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def postgres_engine(migration_config):
    if not TEST_URL:
        pytest.skip("Live PostgreSQL requires BURROW_CLOCK_TEST_DATABASE_URL (no production fallback)")
    safe_url = validate_test_database_url(TEST_URL, os.environ.get("BURROW_CLOCK_DATABASE_URL"))
    engine = create_db_engine(safe_url)
    command.upgrade(migration_config, "head")
    yield engine
    engine.dispose()


@pytest.fixture(params=["sqlite", "postgres"])
def store(request):
    """Each behavior runs on SQLite and PostgreSQL, with synthetic clean rows per test."""
    backend = request.param
    if backend == "postgres":
        engine = request.getfixturevalue("postgres_engine")
    else:
        engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                               connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    def clean():
        with factory.begin() as session:
            session.query(SharingSessionModel).delete()
            session.query(SharingPermissionModel).delete()
            session.query(FriendshipModel).delete()

    clean()
    yield PostgresSharingRepository(factory), factory, engine
    clean()
    if backend == "sqlite":
        engine.dispose()


@pytest.fixture
def participants():
    from uuid import UUID
    return tuple(UUID(f"{digit * 8}-{digit * 4}-4{digit * 3}-8{digit * 3}-{digit * 12}") for digit in "1234")


@pytest.fixture
def instant():
    from datetime import datetime, timezone
    return datetime(2030, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def friendship(store, participants):
    from uuid import UUID
    from burrow_clock_api.domain.friendship import Friendship
    return store[0].create_friendship(Friendship(
        UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), participants[0], participants[1]
    ))


@pytest.fixture
def explicit_permission(friendship, instant):
    from datetime import timedelta
    from burrow_clock_api.domain.consent import ConsentGrant, SharingScope
    from burrow_clock_api.domain.sharing import SharingPermission
    return SharingPermission(friendship.friendship_id, friendship.user_a_id, friendship.user_b_id,
                             ConsentGrant(SharingScope.APPROXIMATE, instant, instant + timedelta(hours=2)))


@pytest.fixture
def grant_id(store, explicit_permission):
    return store[0].grant_permission(explicit_permission)


@pytest.fixture
def sharing_session(store, explicit_permission, grant_id, instant):
    from datetime import timedelta
    from burrow_clock_api.domain.consent import SharingScope
    return store[0].start_session(
        explicit_permission.friendship_id, explicit_permission.sharer_user_id,
        explicit_permission.recipient_user_id, SharingScope.PRESENCE, instant, instant + timedelta(hours=1),
    )
