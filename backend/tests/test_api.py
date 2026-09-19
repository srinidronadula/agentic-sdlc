from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from orchestrator.engine import Orchestrator
from orchestrator.store import RunStore


def client(tmp_path: Path) -> TestClient:
    orch = Orchestrator(RunStore(tmp_path))
    return TestClient(create_app(orch))


def test_create_run_pauses_before_implement(tmp_path: Path) -> None:
    response = client(tmp_path).post("/runs", json={"requirement": "Build a URL shortener"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert body["stages"]["design"]["status"] == "succeeded"
    assert body["stages"]["implement"]["status"] == "pending"
    assert any(event["type"] == "approval_required" for event in body["events"])


def test_get_run_status(tmp_path: Path) -> None:
    api = client(tmp_path)
    created = api.post("/runs", json={"requirement": "status check"}).json()
    response = api.get(f"/runs/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["status"] == "awaiting_approval"


def test_missing_run_is_404(tmp_path: Path) -> None:
    response = client(tmp_path).get("/runs/does-not-exist")
    assert response.status_code == 404


def test_approve_then_completes(tmp_path: Path) -> None:
    api = client(tmp_path)
    created = api.post("/runs", json={"requirement": "greenfield stub"}).json()
    response = api.post(
        f"/runs/{created['id']}/approve",
        json={"actor": "nikhil", "note": "design looks bounded"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["stages"]["docs"]["status"] == "succeeded"
    assert body["approvals"][0]["actor"] == "nikhil"


def test_stop_is_safe(tmp_path: Path) -> None:
    api = client(tmp_path)
    created = api.post("/runs", json={"requirement": "halt this"}).json()
    response = api.post(
        f"/runs/{created['id']}/stop",
        json={"reason": "operator halt"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "stopped"
    assert body["stop_reason"] == "operator halt"
    assert body["stages"]["implement"]["status"] == "cancelled"


def test_approve_without_gate_is_conflict(tmp_path: Path) -> None:
    api = client(tmp_path)
    created = api.post("/runs", json={"requirement": "then stop"}).json()
    api.post(f"/runs/{created['id']}/stop", json={"reason": "done"})
    response = api.post(f"/runs/{created['id']}/approve", json={"actor": "nikhil"})
    assert response.status_code == 409


def test_blank_requirement_rejected(tmp_path: Path) -> None:
    response = client(tmp_path).post("/runs", json={"requirement": "   "})
    assert response.status_code == 422


def test_health(tmp_path: Path) -> None:
    assert client(tmp_path).get("/health").json() == {"status": "ok"}
