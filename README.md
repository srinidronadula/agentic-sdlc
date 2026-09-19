# agentic-sdlc

Prototype of an **agentic software-engineering system**: a stateful orchestrator that turns a requirement into code, tests, and docs with **human gates**, one bounded retry, and an audit log.

The URL shortener in `workspace/` is the **demo artifact agents produce**. This repo is the **system that runs that SDLC**. If you only look at the shortener, you are looking at the wrong product.

This is an ~8 hour interview prototype, not a platform.

## 10-minute walkthrough

1. Skim this file (architecture + gates).
2. Open `runs/greenfield/timeline.json` — graph, pause, approve, tests.
3. Compare `runs/brownfield/` (patch existing code) vs `runs/ambiguous/` (vague ask → listed assumptions).
4. Run the control plane (below) with `AGENTIC_STUB=1` to click Approve / Stop without spending tokens.
5. Optionally rerun one Anthropic scenario from the CLI.

## Architecture

```
Human (UI or CLI)
        │
        ▼
React control plane          FastAPI
  requirement, board,   →    POST /runs
  Approve / Stop             GET  /runs/{id}
                             POST /runs/{id}/approve
                             POST /runs/{id}/stop
        │
        ▼
Orchestrator (DAG + JSON state)
  understand → design → [gate] → implement → test → docs
        │
        ▼
Stage handlers
  stub (no LLM)  or  Anthropic Haiku + tools
        │
        ▼
Tools (workspace/ only)
  write_file · read_file · run_tests
        │
        ▼
Artifacts: workspace/ shortener + runs/*/ audit JSON
```

Two processes, one repo:

| Piece | Owns | Does not own |
|---|---|---|
| `frontend/` | Chat/requirement, stage board, Approve, Stop | LLM calls, file writes, pytest |
| `backend/` | DAG, persistence, policy, LLM, tools, HTTP API | Pretty UI |
| `workspace/` | Generated URL shortener | Orchestration |
| `runs/` | Recorded traces for review | Live state (`backend/var/` is gitignored) |

## Orchestration (the scoring surface)

Default graph — **dependencies**, not a for-loop. A stage is ready when every predecessor has **succeeded**. A custom DAG can make two stages ready at once; the default SDLC is sequential because docs should follow a green test run.

```
understand → design → implement → test → docs
                 ▲
                 └── human approval required before this node starts
```

**Gates.** High-impact action in this prototype is **writing/changing code**. The run enters `awaiting_approval` after design. Implement does not start until `POST /runs/{id}/approve` (or CLI `--approve`). Reject/stop is a human safe-stop.

**Retries.** If **test** fails: reset implement → test → docs, retry **once**. A second test failure **stops** (`retry_exhausted`). A failed understand/design does **not** retry — that is a spec problem, not a flake.

**State.** Each run is one JSON document (status, per-stage attempts/history, approvals, append-only events). Crash-safe write: temp file + replace.

**Policy / autonomy bounds**

- Tools cannot write outside `workspace/` or touch `.env`.
- No secrets in git (`.env` gitignored).
- Agents do not approve themselves.
- Stop cancels pending/running stages.

**Observability in this prototype:** audit events + stage history + test exit output. Not a metrics dashboard. Success/retry/stop are visible on the run document.

## How to run

Python 3.11+, Node 18+, an Anthropic key for live agents.

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY
```

**Orchestrator tests (no LLM):**

```bash
cd backend
python -m pip install -e ".[dev]"
python -m pytest
```

**Control plane (stub agents — good for the UI walkthrough):**

```bash
# terminal 1
cd backend
set AGENTIC_STUB=1          # Windows PowerShell: $env:AGENTIC_STUB="1"
python -m api

# terminal 2
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — Start run → wait for **awaiting approval** → Approve implement or Stop.

**Live LLM run:**

```bash
cd backend
python -m orchestrator --approve "Build a URL shortener with create, redirect, and click counts."
```

Generated app tests:

```bash
cd workspace
python -m pytest
```

APIs: `POST /runs`, `GET /runs/{id}`, `POST /runs/{id}/approve`, `POST /runs/{id}/stop`. Vite proxies `/api` to `http://127.0.0.1:8000`.

## Recorded scenarios (same orchestrator)

| Scenario | Requirement | Trace | What it shows |
|---|---|---|---|
| Greenfield | Build a URL shortener (create, redirect, clicks) | `runs/greenfield/` | New system; 12 tests |
| Brownfield | Add optional custom aliases; do not rewrite | `runs/brownfield/` | Impacted modules; 38 tests |
| Ambiguous | “Make it more reliable.” | `runs/ambiguous/` | Questions + bounded assumptions; 76 tests |

Current `workspace/` is the **end state after C7** (aliases + reliability patches). The greenfield snapshot is the first trace plus the C4 commit.

## Testing approach

- **Orchestrator:** pytest in `backend/tests/` — gate, retry-once, safe-stop, persistence, API, workspace path sandbox. 21 tests, no API key required.
- **Generated product:** pytest in `workspace/` against FastAPI TestClient.
- **UI:** exercised by starting a stub run, approving through the board, and stopping a second run.

## Decisions worth defending

1. **Orchestrator first, UI last.** The assignment scores workflow governance, not a chatbot skin.
2. **One DAG, three scenarios.** Greenfield/brownfield/ambiguous share code paths so the walkthrough is one machine, not three scripts.
3. **Approve before implement, not before understand.** Reading a requirement is cheap; writing files is the high-impact act.
4. **Test is an independent check.** The test stage runs pytest even if implement claimed success.
5. **Haiku + three tools.** Enough to produce a boring shortener; cheap enough to rerun.

## Trade-offs and limitations

| Choice | Cost |
|---|---|
| JSON files, not a DB | Fine for one operator; not multi-tenant |
| Background thread per run | UI can poll; not a job queue |
| Default graph is sequential | Parallel is supported in `Dag.ready()`, not used for the default SDLC |
| Tools are workspace-only | Agents cannot touch `backend/` |
| FastAPI `on_event` in generated app | Tests pass with a deprecation warning |
| CORS `*` | Local prototype only |

**What I would not ship**

- This orchestrator as a company-wide coding agent
- Unattended `--approve` against a real repo
- SQLite URL shortener as a production link service (no auth, no abuse controls, single process)
- The Anthropic key in chat or git (rotate if it leaked)
- Cloud/OCI/Kubernetes for this exercise — it would not raise the score

**Known prototype gaps vs a production agentic SDLC:** no rollback of `workspace/` on failure, no eval of agent patches before apply, no per-file diff approval, weak MTTR/metrics, one LLM provider, no user accounts.

## Principle

Agents execute inside a graph, a sandbox, and a retry budget. Humans own the implement gate, stop, and whether the output is good enough to keep.
