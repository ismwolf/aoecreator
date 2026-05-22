# aeogenerator

AEO/GEO multi-agent SaaS for digital agencies. Analyzes and generates
content optimized for AI search engines using 12 GEO/AEO techniques.

## Monorepo structure

```text
apps/
  web/          Next.js 15 — dashboard + auth frontend (pnpm workspace)
  api/          FastAPI 3.12 — agent orchestration backend (uv, standalone)
packages/
  shared/       Zod ↔ Pydantic parity schemas (pnpm workspace)
infra/          Docker Compose, deployment configs
supabase/       Migrations, config, Edge Functions
docs/           Specs, plans, progress tracker
```

## Tech stack

| Layer     | Technology                                            |
| --------- | ----------------------------------------------------- |
| Frontend  | Next.js 15, TypeScript, Tailwind CSS v4, shadcn/ui    |
| Backend   | Python 3.12, FastAPI, LangChain, LangGraph            |
| Database  | Supabase (Postgres + pgvector + RLS + Auth + Storage) |
| LLM       | OpenRouter                                            |
| Queue     | Celery + Redis                                        |
| Embedding | BGE-M3 (Modal)                                        |

## Prerequisites

- Node.js ≥ 20.11 + pnpm ≥ 10
- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- [gitleaks](https://github.com/gitleaks/gitleaks#installing) (optional — pre-commit secret scan)

## Setup

```bash
# Install JS dependencies + git hooks
pnpm install

# Install Python dependencies
cd apps/api && uv sync --extra dev && cd ../..

# Copy env files and fill in values
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example apps/api/.env
```

## Development

```bash
# Start Next.js dev server
pnpm --filter @aeogen/web dev

# Start FastAPI dev server
cd apps/api && uv run uvicorn src.aeogen.main:app --reload
```

## Quality checks

```bash
# Lint + typecheck + test (all workspaces)
pnpm -r lint && pnpm -r typecheck && pnpm -r test

# Python checks
cd apps/api && uv run ruff check . && uv run mypy src && uv run pytest -v
```

## Commit conventions

This repo uses [Conventional Commits](https://www.conventionalcommits.org/).
`commitlint` enforces this on every commit. Format:

```
<type>(<scope>): <description>

Examples:
  feat(agents): add Question-Intent Analyzer
  fix(crawl): handle Cloudflare 403
  docs(progress): mark C.3 complete
```

## Branch strategy

| Branch               | Purpose            | Push policy           |
| -------------------- | ------------------ | --------------------- |
| `feature/<n>-<slug>` | Per-task work      | Direct push           |
| `dev`                | Active development | PR from feature/\*    |
| `test`               | Staging / QA       | PR from dev (manual)  |
| `main`               | Production         | PR from test (manual) |

## Documentation

- **Master plan:** `docs/plans/2026-05-13-master-plan.md`
- **Progress tracker:** `docs/PROGRESS.md`
- **Specs:** `docs/specs/`
