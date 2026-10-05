from fastapi.testclient import TestClient


def test_app_import():
    from burrow_clock_api.main import app

    assert app is not None
    assert app.title == "The Burrow Clock API"


def test_health_endpoint():
    from burrow_clock_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "burrow-clock-api"}


def test_undefined_endpoint_returns_404():
    from burrow_clock_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/undefined-endpoint")

    assert response.status_code == 404
