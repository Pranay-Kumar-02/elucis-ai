# Elucis AI: working notes for Claude

Elucis AI (**E**vidence-**L**ed **U**nified **C**ustomer **I**ntelligence **S**ystem) turns customer feedback (reviews, tickets, transcripts, usage metrics) into evidence-backed product decisions, PRDs and roadmaps. Local-first: models run through Ollama on this machine. The SRS and design documents call the project "AI Product Manager Copilot"; that title stays in those documents only.

## Sources of truth

- Requirements: `docs/requirements/SRS_v1.0.md` (IDs like FR-ING-01, DR-07, NFR-07, A-05).
- Design: `docs/design/00`–`12` (D01–D12). D07 = database schema, D09 = API contracts, D12 = UI.
- Implementation decisions and open findings: `docs/architecture/FOUNDATION_NOTES.md` (IMP-01…IMP-21, F-01…F-05). Record every new decision the design does not make here, and mark additions to the design as **proposed**.
- Pinned versions: `docs/VERSIONS.md`. Windows setup: `docs/setup/WINDOWS_SETUP.md`.

Follow the SRS and design. Do not silently change a design decision or the stack; explain the trade-off and ask first.

## Product standards (non-negotiable)

- A premium, enterprise-grade product, not a student demo. Internship labels (programme name, group, batch, project code, "development build") never appear in the UI; a frontend test enforces it. The product name lives only in `frontend/src/config/product.ts` and `backend/src/elucis/core/config.py` (`app_name`).
- Real loading, empty and error states. No mock data presented as real, no fake success, no fabricated AI output.
- Report feature status as: implemented and verified / partial / designed only / blocked. "Complete" means frontend + backend + database + validation + error handling + tests, all run.
- Never claim something works without running it. Never claim PostgreSQL or Ollama is configured without checking.
- No overengineering. No Redis, Celery or other brokers, and no LangChain, LangGraph, CrewAI or agent frameworks, without explicit approval.

## Safety rules

- Never print, commit or expose secrets, `.env`, credentials, `.setup-reports/`, `data/` or database files. Never hardcode credentials.
- The repository is published at `origin` (GitHub, branch `main`). Commit and push only when the owner asks. Never force-push, rewrite or delete existing commits, or run destructive resets; on a remote conflict or security issue, stop and report.
- Do not delete the owner's files. Do not run destructive database commands.
- Ask before installing system-level software. Do not assume Docker exists.
- Keep approved package versions. Dependency cooldown: releases at least 14 days old (`exclude-newer` in uv, `minimumReleaseAge` in pnpm).

## Stack

Backend: Python 3.12 (uv-managed), FastAPI 0.162.2, Pydantic 2.14, SQLAlchemy 2.1 (sync) + psycopg 3, Alembic, PostgreSQL 18.7 + pgvector 0.8.7 (in WSL2 Ubuntu, IMP-01), PostgreSQL job queue for the worker. Frontend: React 19, TypeScript 6.0.3, Vite 8, Tailwind 4, shadcn-style components, TanStack Query, React Router 8, pnpm 12.16.1, Node 22.22 or newer. AI: Ollama, `qwen3:4b` (generation), `qwen3-embedding:0.6b` (embeddings, `vector(1024)`).

## Commands (Windows, from the project root)

```powershell
.\scripts\windows\run-local.ps1      # install from lockfiles, start API (:8000) and web app (:5173)
.\scripts\windows\90-verify.ps1      # all checks plus a live API check
```

Backend (in `backend/`): `uv run ruff format --check .` · `uv run ruff check .` · `uv run mypy` · `uv run pytest`
Frontend (in `frontend/`): `pnpm verify` (typecheck, lint, format check, tests, build)

Database tests need `TEST_DATABASE_URL`; without it they are skipped.

## Layout

- `backend/src/elucis/`: `core/` (config, errors, logging, middleware), `db/`, `ai/` (Ollama gateway), `api/v1/`, `modules/ingestion/` (adapters, mapping, parsing, validation, service, router), `workers/`. Error envelope `{error: {code, message, details, request_id}}`; routes under `/api/v1`.
- `frontend/src/`: `app/` (routes, tests), `components/` (layout, brand, ui), `features/` (dashboard, sources, system), `lib/api/` (client, endpoints, types), `config/product.ts`.
- `database/`: role and database bootstrap, WSL install script. `scripts/windows/`: setup and run scripts.

## Status (25 Nov 2026)

Implemented and verified (195 backend tests, 25 frontend tests, build):
- Foundation: settings, errors, logging, middleware, health endpoints, database engines and RLS helper, Alembic baseline, job queue worker, Ollama gateway, Argon2id hashing, app shell with D12 navigation and themes.
- Source fetching (SVC-02 + SVC-04, IMP-17 to IMP-20): CSV/JSON/TXT/pasted-text reading with encoding, delimiter and malformed-row handling; column-mapping suggestions and rules; row validation and normalisation to D07 names; development endpoints `POST /api/v1/dev/sources/{preview,validate,fetch}` (need `ENABLE_DEV_ENDPOINTS=true`); Imports screen (upload or paste → preview → match columns → check records).

Not built yet: the 54 D07/D08 tables (migration 0002), authentication and workspaces, API-14/API-15 and the ingest job, cleaning/PII/duplicates (SVC-05 onwards), all AI calls CP-01 to CP-10, the other production screens. "Start import" stays disabled until the database exists.

This laptop: PostgreSQL not set up yet (`30-setup-database.ps1`); Ollama 0.40.4 installed, `qwen3-embedding:0.6b` pulled, `qwen3:4b` not pulled (`40-setup-ollama.ps1`); Node should be 22.22 or newer.

## Next tasks, in order

1. Set up PostgreSQL in WSL, then write migration 0002 with the D07/D08 tables (confirm the 1024 embedding dimension first, F-02).
2. Authentication and workspaces (SVC-01, RLS by `app.workspace_id`).
3. API-14/API-15 and the ingest job, reusing `modules/ingestion` unchanged.

## Housekeeping

- "Elucis" is also the name of an FDA-cleared surgical-planning product and has a US trademark record (IMP-21). Fine for the internship; check before any commercial release.
