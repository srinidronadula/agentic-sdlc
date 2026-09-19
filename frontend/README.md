# frontend

Human control plane. No LLM calls here — the UI talks to FastAPI only.

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. In another terminal, from `backend/`:

```bash
python -m api
```

Vite proxies `/api` to `http://127.0.0.1:8000`.
