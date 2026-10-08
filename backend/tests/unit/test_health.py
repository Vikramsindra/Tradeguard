from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == settings.TRADING_MODE
    assert data["environment"] == settings.APP_ENV

def test_request_id_middleware():
    response = client.get("/health")
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0

def test_explicit_request_id():
    custom_id = "test-request-123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers["X-Request-ID"] == custom_id
