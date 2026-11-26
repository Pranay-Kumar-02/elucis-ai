# Elucis AI

**E**vidence-**L**ed **U**nified **C**ustomer **I**ntelligence **S**ystem. *Illuminate insights. Engineer better products.*

Elucis AI turns customer feedback (reviews, support tickets, call transcripts and usage metrics) into evidence-backed product decisions, with a planning and requirements workspace. It runs local-first: the models run on your machine through Ollama, so customer data never leaves it.

Built as the *AI Product Manager Copilot* project (the name used in the SRS and design documents).

Infosys Springboard Virtual Internship 7.0 · Batch 5 · Project #Z-5-1 · Group 2 (Varshini, Lalitha, Monika, Pranay, Prasunabhika)

**Status:** foundation, source fetching and the database schema are built and tested: backend and frontend foundations, local model runtime checks, reading, matching and validating CSV, JSON, TXT and pasted feedback (Imports screen), and the full 54-table schema with row-level security on PostgreSQL 18.7 + pgvector. Authentication and the import pipeline come next. The requirements are in [`docs/requirements/SRS_v1.0.md`](docs/requirements/SRS_v1.0.md) and the design is in [`docs/design/`](docs/design/README.md).

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (psycopg 3), Alembic. One modular-monolith API plus one background worker |
| Frontend | React 19, TypeScript (strict), Vite 8, Tailwind CSS v4, shadcn/ui, TanStack Query, React Router |
| Database | PostgreSQL 18.7 with pgvector 0.8.7: relational data, vector search, full-text search and the job queue in one database |
| AI runtime | Ollama on the local GPU: `qwen3:4b` (generation), `qwen3-embedding:0.6b` (embeddings). No paid APIs and no LLM framework |
| Jobs | PostgreSQL table with `FOR UPDATE SKIP LOCKED`. No Redis, Celery or other broker |

Exact versions are in [`docs/VERSIONS.md`](docs/VERSIONS.md). The lockfiles `backend/uv.lock` and `frontend/pnpm-lock.yaml` pin every package.

## Quick start (Windows)

To just see the app running now (no database, no system changes; only the project's own
`backend\.venv` and `frontend\node_modules` are created):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\run-local.ps1
```

Full setup:

First-time setup is one command. It checks prerequisites, creates `.env` with random secrets, installs pinned dependencies, sets up PostgreSQL + pgvector in WSL2, pulls and tests the models, and runs every check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\setup.ps1
```

Daily use, in four terminals:

```powershell
.\scripts\windows\dev-db.ps1 start     # PostgreSQL in WSL2 on 127.0.0.1:5432
.\scripts\windows\dev-api.ps1          # API on http://127.0.0.1:8000  (docs: /api/v1/docs)
.\scripts\windows\dev-worker.ps1       # background worker
.\scripts\windows\dev-web.ps1          # web app on http://127.0.0.1:5173
```

Ollama runs as its own Windows app. Details, troubleshooting and manual commands are in [`docs/setup/WINDOWS_SETUP.md`](docs/setup/WINDOWS_SETUP.md).

## Repository layout

```text
backend/                     FastAPI modular monolith + worker (Python 3.12, uv)
  src/elucis/
    main.py                  app factory: middleware, error handlers, routers
    core/                    settings, structured logging, error envelope, middleware
    api/                     versioned HTTP routers (/api/v1) and shared dependencies
    db/                      engines and sessions per role, declarative base, setup verifier
    repositories/            all SQL lives here
    services/                platform services (health)
    modules/ingestion/       Module 2: file adapter, mapping, row validation; dev preview/validate/fetch endpoints
    ai/                      model gateway: Ollama client + smoke-test CLI
    security/                Argon2id password hashing
    workers/                 PostgreSQL job queue and worker runtime
    schemas/                 shared API schemas
  migrations/                Alembic (0001 pgvector baseline, 0002 the 54-table schema)
  tests/                     pytest: unit, API, real-database and job-queue tests
frontend/                    React app (pnpm)
  src/app/                   providers, routes, router
  src/components/            layout shell and shadcn/ui components
  src/features/              dashboard, system status, imports (sources)
  src/lib/                   typed API client, env handling, utilities
database/
  bootstrap/                 roles (app_owner, app_api, app_worker), databases, pgvector, grants
  wsl/                       PostgreSQL 18 + pgvector installer for WSL2 Ubuntu (PGDG packages)
scripts/windows/             setup, verification and daily-run scripts (PowerShell 5.1+)
docs/
  requirements/              SRS v1.0 (authoritative requirements)
  design/                    system design D00-D12 (v1.2)
  setup/                     Windows setup guide
  architecture/              foundation implementation notes and decisions
  VERSIONS.md                pinned and measured versions
```

## Quality checks

```powershell
.\scripts\windows\90-verify.ps1          # everything below plus a live API check, with a report
```

| Area | Commands (run inside `backend/` or `frontend/`) |
|---|---|
| Backend | `uv run ruff format --check .` · `uv run ruff check .` · `uv run mypy` · `uv run pytest` |
| Frontend | `pnpm typecheck` · `pnpm lint` · `pnpm format:check` · `pnpm test` · `pnpm build` |

## Security rules

- Secrets live only in `.env` (git-ignored, created by the setup script, readable only by your account). `.env.example` lists the names.
- Never commit `.env`, `.setup-reports/`, `data/` or database files. The history was scanned for secrets before it was published.
- Customer text is never logged. Logs mask connection-string passwords and secret-looking fields.
- Development endpoints (`/api/v1/dev/*`) exist only when `ENABLE_DEV_ENDPOINTS=true`, and the app refuses to start in production with them enabled.
