from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_application


def test_health_reports_unconfigured_database(monkeypatch):
    settings = Settings(_env_file=None)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.routes.health.get_settings", lambda: settings)
    client = TestClient(create_application())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "service": "careerpilot-api",
        "database": "not_configured",
        "environment": "development",
    }
