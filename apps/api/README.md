# apps/api — aeogenerator FastAPI backend

Python 3.12 + FastAPI backend (LangChain / LangGraph land in Faz 3). Managed by `uv`.

## Setup

```powershell
cd apps/api
uv python pin 3.12        # one-time, if uv-managed Python is preferred
uv sync --all-extras
cp .env.example .env.local  # optional — defaults are fine for dev
```

## Run

```powershell
uv run uvicorn aeogen.main:app --reload
```

Then `GET http://127.0.0.1:8000/health/live` or open `http://127.0.0.1:8000/docs`.

## Quality gates

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

## Conventions

- 4-space indent, type hints required on all public functions, async-first.
- Settings flow through `aeogen.settings.Settings` (pydantic-settings).
  Mirror new fields in `.env.example` whenever you add one.
- `aeogen.main.create_app()` is the factory; tests should always build
  fresh instances rather than reusing the module-level `app`.
- `pydantic-settings` loads `env_file=(".env", ".env.local")` — LATER
  files OVERRIDE earlier (Next.js parity).

## Why this is NOT in the pnpm workspace

`apps/api/` is a standalone Python project. Root `pnpm -r` scripts skip
it. To run all backend gates locally, run the commands above from inside
`apps/api/`. (See open question 4 in the A.T5 plan.)
