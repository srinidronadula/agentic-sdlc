# backend

Python orchestrator + FastAPI control plane. No LLM yet (that is C4).

```bash
cd backend
python -m pip install -e ".[dev]"
python -m pytest
python -m api
```

API (default `http://127.0.0.1:8000`):

- `POST /runs` `{ "requirement": "..." }` — create and run until the implement gate
- `GET /runs/{id}` — status, stages, audit
- `POST /runs/{id}/approve` `{ "actor": "human", "note": "" }` — pass the gate, continue
- `POST /runs/{id}/stop` `{ "reason": "human safe-stop" }`
