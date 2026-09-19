# agentic-sdlc

An **agentic software-engineering prototype**: an orchestrator that takes a requirement and turns it into a reviewable outcome (plan → design → code → tests → docs) with **human gates**, retries, and an audit trail.

The URL shortener is the **demo product the agents write**. This repo is the **system that runs that SDLC**.

## What this is

- A small, walkthrough-ready prototype (about 8 hours of work).
- Python backend: DAG / state machine, LLM tools, FastAPI control plane.
- React frontend: chat, stage board, Approve / Stop.
- Three recorded runs against the same orchestrator: greenfield, brownfield, and ambiguous.

## What this is not

- Not a production SDLC platform, cloud deploy, or multi-agent fleet.
- Not “ask a chatbot to write a URL shortener.”
- Not a polished URL-shortener product. If the shortener is nicer than the orchestrator, the assignment failed.

## Layout

```
backend/     Python orchestrator + API
frontend/    React control-plane UI
workspace/   generated URL shortener (agents write here)
runs/        saved traces for the three scenarios
```

## Status

- **C1** scaffold
- **C2** stateful orchestrator: DAG, human gate before implement, one test retry, JSON audit
- **C3** FastAPI control plane: create, status, approve, stop (no LLM yet)

## Orchestrator (C2–C3)

From `backend/`:

```bash
python -m pytest
python -m orchestrator
python -m api
```

`understand → design → [approve] → implement → test → docs`. Test failure retries implement once, then stops. Run state is a JSON document.

- `POST /runs` — create and pause before implement
- `GET /runs/{id}` — status + audit
- `POST /runs/{id}/approve` — human gate
- `POST /runs/{id}/stop` — safe-stop

## Setup (later)

Copy `.env.example` to `.env`. Do not commit secrets.
