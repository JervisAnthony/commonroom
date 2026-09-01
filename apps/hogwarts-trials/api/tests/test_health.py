from fastapi.testclient import TestClient

def test_app_import():
    # Verify the application can be imported without side effects
    from hogwarts_trials_api.main import app
    assert app is not None
    assert app.title == "Hogwarts Trials API"

def test_health_endpoint():
    from hogwarts_trials_api.main import app
    client = TestClient(app)
    
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "hogwarts-trials-api"
    }

def test_undefined_endpoint_returns_404():
    from hogwarts_trials_api.main import app
    client = TestClient(app)
    
    response = client.get("/api/v1/undefined-endpoint")
    assert response.status_code == 404
