from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from orchestrator.engine import Orchestrator, OrchestratorError
from orchestrator.store import RunStore


class CreateRunBody(BaseModel):
    requirement: str = Field(min_length=1)


class ApproveBody(BaseModel):
    actor: str = "human"
    note: str = ""


class StopBody(BaseModel):
    reason: str = "human safe-stop"


def default_store_root() -> Path:
    override = os.environ.get("RUN_STORE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "var" / "runs"


def create_app(orchestrator: Orchestrator | None = None) -> FastAPI:
    orch = orchestrator or Orchestrator(RunStore(default_store_root()))
    app = FastAPI(
        title="agentic-sdlc",
        description="Control plane for the SDLC orchestrator. Humans approve and stop; agents do not.",
        version="0.3.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.orch = orch

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/runs")
    def create_run(body: CreateRunBody) -> dict:
        requirement = body.requirement.strip()
        if not requirement:
            raise HTTPException(status_code=422, detail="requirement is blank")
        run = orch.create(requirement)
        run = orch.run_until_blocked(run.id)
        return run.to_dict()

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        return _load(orch, run_id).to_dict()

    @app.post("/runs/{run_id}/approve")
    def approve_run(run_id: str, body: ApproveBody | None = None) -> dict:
        payload = body or ApproveBody()
        _load(orch, run_id)
        try:
            orch.approve(run_id, actor=payload.actor.strip() or "human", note=payload.note)
        except OrchestratorError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        run = orch.run_until_blocked(run_id)
        return run.to_dict()

    @app.post("/runs/{run_id}/stop")
    def stop_run(run_id: str, body: StopBody | None = None) -> dict:
        payload = body or StopBody()
        _load(orch, run_id)
        run = orch.stop(run_id, reason=payload.reason.strip() or "human safe-stop")
        return run.to_dict()

    return app


def _load(orch: Orchestrator, run_id: str):
    try:
        return orch.get(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


app = create_app()
