"""Lazy persistence initialization, disposal, sanitized failure and import boundaries."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import os
import subprocess
import sys
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from burrow_clock_api.api import dependencies
from burrow_clock_api.application.identity import AuthenticatedPrincipal


def test_storage_is_lazy_shared_and_disposed(monkeypatch):
    engine, repository = Mock(), Mock()
    build = Mock(return_value=engine)
    construct = Mock(return_value=repository)
    monkeypatch.setattr(dependencies, "get_database_url", lambda: "synthetic-test-url")
    monkeypatch.setattr(dependencies, "create_db_engine", build)
    monkeypatch.setattr(dependencies, "PostgresSharingRepository", construct)
    storage = dependencies.SharingStorage()
    build.assert_not_called()
    with ThreadPoolExecutor(max_workers=4) as workers:
        assert list(workers.map(lambda _: storage.get(), range(8))) == [repository] * 8
    build.assert_called_once_with("synthetic-test-url", connect_args={"connect_timeout": 5})
    construct.assert_called_once()
    storage.close()
    storage.close()
    engine.dispose.assert_called_once()


def test_initialization_failure_disposes_engine_and_can_retry(monkeypatch):
    engine = Mock()
    monkeypatch.setattr(dependencies, "get_database_url", lambda: "synthetic-test-url")
    monkeypatch.setattr(dependencies, "create_db_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(dependencies, "create_session_factory", Mock(side_effect=RuntimeError("synthetic")))
    storage = dependencies.SharingStorage()
    with pytest.raises(RuntimeError):
        storage.get()
    engine.dispose.assert_called_once()
    assert storage._engine is None and storage._repository is None


@pytest.mark.parametrize("configuration", [None, "sqlite:///:memory:", "not-a-url"])
def test_authenticated_missing_or_invalid_persistence_is_503(monkeypatch, configuration):
    from burrow_clock_api.main import app
    if configuration is None:
        monkeypatch.delenv("BURROW_CLOCK_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("BURROW_CLOCK_DATABASE_URL", configuration)
    app.dependency_overrides[dependencies.get_current_principal] = lambda: AuthenticatedPrincipal(uuid4())
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/friendships/with/{uuid4()}")
        assert response.status_code == 503
        assert response.json() == {"detail": "Persistence unavailable"}
    finally:
        app.dependency_overrides.clear()


def test_application_lifespan_closes_lazy_storage(monkeypatch):
    from burrow_clock_api.main import app
    close = Mock()
    monkeypatch.setattr(app.state.sharing_storage, "close", close)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        close.assert_not_called()
    close.assert_called_once()


def test_import_does_not_construct_storage_or_touch_database(monkeypatch):
    forbidden = Mock(side_effect=AssertionError("import touched persistence"))
    monkeypatch.setattr(dependencies, "get_database_url", forbidden)
    monkeypatch.setattr(dependencies, "create_db_engine", forbidden)
    from burrow_clock_api import main
    importlib.reload(main)
    forbidden.assert_not_called()


def test_fresh_import_has_no_configuration_connections_or_application_files(tmp_path):
    code = """
import os
from pathlib import Path
import socket
import sqlalchemy
os.environ.pop('BURROW_CLOCK_DATABASE_URL', None)
os.environ.pop('BURROW_CLOCK_TEST_DATABASE_URL', None)
def forbidden(*args, **kwargs):
    raise AssertionError('import opened database/network')
sqlalchemy.create_engine = forbidden
socket.create_connection = forbidden
from burrow_clock_api.main import app
assert app.title == 'The Burrow Clock API'
assert not list(Path.cwd().iterdir())
"""
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
