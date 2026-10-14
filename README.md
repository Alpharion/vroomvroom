# vroomvroom

Multi-agent autonomous dispute resolution for Ryde (Tencent Cloud AI CAN DO IT Hackathon Singapore 2026, Digital Native Track).

A dispute is filed, a Rider Advocate and a Driver Advocate gather evidence and argue each side, and a Judge issues a ruling with a confidence score and plain-language explanation. Low-confidence or safety cases go to a human reviewer.

Dispute types: **No-Show Charge**, **Route Deviation**.

## Layout

```
backend/
  app/       FastAPI app
  tools/     evidence tools (plain code: route_deviation, no_show_check, ...)
  agents/    advocate + judge prompts and orchestration
  schemas/   Pydantic models (see schemas.md)
  tests/
frontend/    Streamlit UI (dispute form, courtroom log, ruling cards)
data/        sample disputes (DISP-002, ...)
docs/        team brief, sample dataset, policy doc
schemas.md   agreed JSON shapes
```

## Run the backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in keys, never commit .env
uvicorn app.main:app --reload
pytest
```

See [docs/team-brief.md](docs/team-brief.md) for the plan and roles.

## Run the frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

The UI builds against mock data (`mock_ruling.json`, `mock_agent_log.json`) so it
is not blocked on the backend. By default the courtroom log streams real agent
messages from `POST /api/disputes/resolve`, so the FastAPI backend must be running.
Demo mode (sidebar → Developer tools, default off) replays recorded hearings instead;
it does not read what the filer types.

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` to point at a
non-default backend URL.

## Deploy

Two services, each with a Dockerfile at the repo root. Build both **from the repo
root** (they read `data/` and `docs/`). Configuration comes from environment
variables; `.env`, `secrets.toml` and local caches are excluded by `.dockerignore`.

| Service | Build | Port | Environment variables |
|---|---|---|---|
| Backend (FastAPI) | `docker build -f Dockerfile.backend -t vroomvroom-backend .` | 8000 | `ADP_APP_KEY` (secret), `USE_MOCK_LLM=false`. Leave `USE_STUB_AGENTS` unset. |
| Frontend (Streamlit) | `docker build -f Dockerfile.frontend -t vroomvroom-frontend .` | 8501 | `BACKEND_URL=https://<backend address>`, `DEMO_MODE=false` |

Both honour `PORT` if the platform sets it. Check the backend with `GET /health`.

- **CloudBase Run:** create one service per Dockerfile; set the build context to the
  repo root and the Dockerfile path to `Dockerfile.backend` / `Dockerfile.frontend`.
- **Lighthouse (one VM):** run both containers, e.g.
  `docker run -d -p 8000:8000 -e ADP_APP_KEY=... -e USE_MOCK_LLM=false vroomvroom-backend` and
  `docker run -d -p 80:8501 -e BACKEND_URL=http://<vm-ip>:8000 -e DEMO_MODE=false vroomvroom-frontend`.

The agent stream sends nothing for 15–30 s while the advocates run, so set the
platform's request/idle timeout to at least 120 s. The human review queue is stored
in `backend/.review_queue.json` inside the container: it survives restarts of the
process but not a redeploy.
