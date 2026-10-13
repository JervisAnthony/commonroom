"""Configuration remains lazy, strict, product-local and health-only."""
import importlib

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine

from burrow_clock_api.infrastructure import database
import conftest


@pytest.mark.parametrize("scheme", ["postgresql", "postgresql+psycopg"])
def test_postgres_scheme_normalization(scheme):
    url = f"{scheme}://test_user:test_password@localhost/burrow_clock_test"
    assert database.validate_database_url(url).startswith("postgresql+psycopg://")
    assert database.get_database_url({"BURROW_CLOCK_DATABASE_URL": url}) == database.validate_database_url(url)


@pytest.mark.parametrize("url", ["", "sqlite:///:memory:", "mysql://localhost/db", "postgres://localhost/db"])
def test_unsupported_datastores_denied(url):
    with pytest.raises(ValueError):
        database.create_db_engine(url)


def test_database_url_missing_and_no_test_url_fallback():
    with pytest.raises(ValueError):
        database.get_database_url({"BURROW_CLOCK_TEST_DATABASE_URL": "postgresql://localhost/test"})


def test_import_and_health_require_no_database(monkeypatch):
    monkeypatch.delenv("BURROW_CLOCK_DATABASE_URL", raising=False)
    monkeypatch.delenv("BURROW_CLOCK_TEST_DATABASE_URL", raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("app import/health constructed an engine")

    monkeypatch.setattr(database, "create_engine", forbidden)
    from burrow_clock_api import main
    importlib.reload(main)
    with TestClient(main.app) as client:
        response = client.get("/api/v1/health")
    assert response.json() == {"status": "ok", "service": "burrow-clock-api"}
    assert {route.path for route in main.app.routes if route.path.startswith("/api/")} == {"/api/v1/health"}


def test_explicit_engine_seam_and_driver(monkeypatch):
    calls = []
    monkeypatch.setattr(database, "create_engine", lambda url, **kw: calls.append((url, kw)))
    database.create_db_engine("postgresql://localhost/test", connect_args={"connect_timeout": 1})
    assert calls == [("postgresql+psycopg://localhost/test", {"pool_pre_ping": True, "connect_args": {"connect_timeout": 1}})]
    engine = create_engine("sqlite:///:memory:")
    factory = database.create_session_factory(engine)
    with factory() as session:
        assert session.bind is engine
    engine.dispose()


def test_test_database_safety_requires_explicit_url():
    with pytest.raises(ValueError, match="no production fallback"):
        conftest.validate_test_database_url(None, "postgresql://localhost/burrow_clock_test")


@pytest.mark.parametrize("name", ["burrow_clock", "postgres", "production", "commonroom", "", "burrow_clock_test_", "burrow_clock_test_bad-suffix"])
def test_test_database_safety_rejects_non_test_names(name):
    with pytest.raises(ValueError, match="Test database must"):
        conftest.validate_test_database_url(f"postgresql://localhost/{name}")


@pytest.mark.parametrize("url", [
    "not-a-url", "postgresql://user:synthetic_password@localhost:bad/burrow_clock_test",
    "sqlite:///burrow_clock_test", "mysql://localhost/burrow_clock_test",
    "postgres://localhost/burrow_clock_test", "postgresql://localhost/burrow_clock_test?host=production-host",
    "postgresql://localhost/burrow_clock_test?dbname=production", "postgresql://localhost/burrow_clock_test?service=production",
])
def test_test_database_safety_rejects_invalid_or_ambiguous_urls(url):
    with pytest.raises(ValueError) as error:
        conftest.validate_test_database_url(url)
    assert "synthetic_password" not in str(error.value)
    assert url not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("test_scheme,production_scheme", [
    ("postgresql", "postgresql"), ("postgresql", "postgresql+psycopg"),
    ("postgresql+psycopg", "postgresql"), ("postgresql+psycopg", "postgresql+psycopg"),
])
def test_test_database_safety_rejects_equivalent_targets(test_scheme, production_scheme):
    test_url = f"{test_scheme}://test_user:synthetic_test_password@LOCALHOST/burrow_clock_test?sslmode=disable"
    production_url = f"{production_scheme}://other_user:synthetic_production_password@localhost:5432/burrow_clock_test"
    with pytest.raises(ValueError, match="targets must be distinct") as error:
        conftest.validate_test_database_url(test_url, production_url)
    assert "password" not in str(error.value)


@pytest.mark.parametrize("name", ["burrow_clock_test", "burrow_clock_test_worker_1"])
def test_test_database_safety_accepts_dedicated_names(name):
    url = f"postgresql://localhost/{name}"
    assert conftest.validate_test_database_url(url) == f"postgresql+psycopg://localhost/{name}"


@pytest.mark.parametrize("production_url", [
    "postgresql://localhost/burrow_clock", "postgresql://other-host/burrow_clock_test",
    "postgresql://localhost:5433/burrow_clock_test",
])
def test_test_database_safety_accepts_distinct_production_target(production_url):
    assert conftest.validate_test_database_url("postgresql://localhost/burrow_clock_test", production_url)


def test_test_database_safety_hides_invalid_production_url_credentials():
    with pytest.raises(ValueError) as error:
        conftest.validate_test_database_url(
            "postgresql://localhost/burrow_clock_test",
            "postgresql://user:synthetic_password@localhost:bad/production",
        )
    assert "synthetic_password" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("fixture", ["migration_config", "postgres_engine"])
@pytest.mark.parametrize("unsafe", ["non_test_name", "same_production_target"])
def test_live_fixtures_validate_before_database_operations(monkeypatch, fixture, unsafe):
    test_url = "postgresql://localhost/production" if unsafe == "non_test_name" else "postgresql://localhost/burrow_clock_test"
    monkeypatch.setattr(conftest, "TEST_URL", test_url)
    monkeypatch.setenv("BURROW_CLOCK_DATABASE_URL", "postgresql+psycopg://localhost:5432/burrow_clock_test")

    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe fixture reached live database operations")

    monkeypatch.setattr(conftest, "create_db_engine", forbidden)
    monkeypatch.setattr(conftest.command, "upgrade", forbidden)
    with pytest.raises(ValueError):
        if fixture == "migration_config":
            conftest.migration_config.__wrapped__()
        else:
            next(conftest.postgres_engine.__wrapped__(None))


def test_optional_live_fixture_still_skips_without_test_url(monkeypatch):
    monkeypatch.setattr(conftest, "TEST_URL", None)
    monkeypatch.setenv("BURROW_CLOCK_DATABASE_URL", "postgresql://localhost/production")
    with pytest.raises(pytest.skip.Exception, match="no production fallback"):
        next(conftest.postgres_engine.__wrapped__(None))


def test_valid_live_fixture_uses_validated_target_without_real_connection(monkeypatch):
    from unittest.mock import Mock

    monkeypatch.setattr(conftest, "TEST_URL", "postgresql://localhost/burrow_clock_test_worker_1")
    monkeypatch.setenv("BURROW_CLOCK_DATABASE_URL", "postgresql://localhost/burrow_clock")
    engine = Mock()
    build = Mock(return_value=engine)
    migrate = Mock()
    monkeypatch.setattr(conftest, "create_db_engine", build)
    monkeypatch.setattr(conftest.command, "upgrade", migrate)
    config = conftest.migration_config.__wrapped__()
    fixture = conftest.postgres_engine.__wrapped__(config)
    assert next(fixture) is engine
    build.assert_called_once_with("postgresql+psycopg://localhost/burrow_clock_test_worker_1")
    migrate.assert_called_once_with(config, "head")
    assert config.get_main_option("sqlalchemy.url") == build.call_args.args[0]
    with pytest.raises(StopIteration):
        next(fixture)
    engine.dispose.assert_called_once()
