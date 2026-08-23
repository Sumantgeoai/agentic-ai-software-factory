from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from software_factory.api import create_app
from software_factory.config import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        model_provider="fixture",
        workspace_root=tmp_path / "workspaces",
        database_url=f"sqlite:///{tmp_path / 'factory.db'}",
        command_timeout_seconds=30,
        api_key="integration-test-key",
    )


def test_api_key_protects_factory_routes_and_health_stays_public(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    health = client.get("/health")
    protected = client.get(f"/api/v1/runs/{uuid4()}")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert protected.status_code == 401
    assert protected.json() == {"detail": "Invalid API credentials"}
    assert protected.headers["x-correlation-id"]


def test_run_and_audit_endpoints_preserve_correlation_id(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    headers = {
        "X-API-Key": "integration-test-key",
        "X-Correlation-ID": "api-test-001",
    }

    created = client.post(
        "/api/v1/projects/run",
        headers=headers,
        json={
            "request": (
                "Build an employee leave-management application where employees submit leave, "
                "managers approve or reject requests, and HR can view reports."
            )
        },
    )

    assert created.status_code == 200
    assert created.headers["x-correlation-id"] == "api-test-001"
    created_payload = created.json()
    project_id = created_payload["project_id"]
    assert "workspace" not in created_payload["execution"]
    assert "path" not in created_payload["release"]

    stored = client.get(f"/api/v1/runs/{project_id}", headers=headers)
    audit = client.get(f"/api/v1/runs/{project_id}/audit", headers=headers)

    assert stored.status_code == 200
    stored_payload = stored.json()
    assert stored_payload["status"] == "completed"
    assert stored_payload["result"] is not None
    assert "workspace" not in stored_payload["result"]["execution"]
    assert "path" not in stored_payload["result"]["release"]
    assert audit.status_code == 200
    events = audit.json()
    assert {event["event_type"] for event in events} >= {
        "run.started",
        "plan.completed",
        "security.completed",
        "run.completed",
    }
    correlated = [
        event for event in events if event["payload"].get("correlation_id") == "api-test-001"
    ]
    assert len(correlated) == len(events)


def test_invalid_correlation_id_is_rejected_without_reflection(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.get("/health", headers={"X-Correlation-ID": "invalid correlation id"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid X-Correlation-ID header"}
    assert response.headers["x-correlation-id"] != "invalid correlation id"
