import os
import subprocess
import sys
import textwrap

from fastapi.testclient import TestClient


def test_app_import_and_title():
    from pensieve_api.main import app

    assert app.title == "Pensieve API"


def test_health_endpoint():
    from pensieve_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "service": "pensieve-api"}
    assert all(type(value) is str for value in body.values())


def test_unregistered_api_endpoint():
    from pensieve_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/undefined-endpoint")

    assert response.status_code == 404


def test_openapi_health_contract():
    from pensieve_api.main import app

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/api/v1/health"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    model_name = response_schema["$ref"].rsplit("/", 1)[-1]
    model = schema["components"]["schemas"][model_name]
    assert set(model["required"]) == {"status", "service"}
    assert {key: value["type"] for key, value in model["properties"].items()} == {
        "status": "string", "service": "string"
    }


def test_fresh_import_and_health_without_configuration_or_external_io(tmp_path):
    # A fresh isolated process cannot inherit a cached app or provider credentials.
    # Block network connections, database connections and filesystem mutations,
    # including during import. -B prevents Python's own bytecode cache writes.
    code = textwrap.dedent("""
        import asyncio
        import os
        import sys
        from fastapi.testclient import TestClient

        # Windows creates a local socket pair for the event loop itself.
        # Initialize test machinery before guarding application import and health.
        loop = asyncio.new_event_loop()

        def reject_external_io(event, args):
            if event in {"socket.connect", "sqlite3.connect", "os.mkdir", "os.remove", "os.rename"}:
                raise AssertionError(f"Unexpected external IO: {event}")
            if event == "open":
                _, mode, flags = args
                if (mode and any(char in mode for char in "wax+")) or flags & (
                    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
                ):
                    raise AssertionError("Unexpected filesystem write")

        sys.addaudithook(reject_external_io)
        from pensieve_api.main import app

        with TestClient(app, backend_options={"loop_factory": lambda: loop}) as client:
            response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "pensieve-api"}
    """)
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=tmp_path,
        # Windows needs SystemRoot to initialize its standard socket runtime.
        env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
