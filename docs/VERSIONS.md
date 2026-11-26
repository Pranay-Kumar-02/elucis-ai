# Versions

Two kinds of version are recorded here: **pinned** versions, fixed in the lockfiles, and **measured** versions, read from a real machine by the setup scripts. The scripts write the full machine record to `.setup-reports\versions.json`, `postgres-wsl.json` and `ollama-check.json`.

Pinning policy: direct dependencies are pinned exactly; the lockfiles pin every transitive package with hashes (`backend/uv.lock`: 55 packages for Windows, Linux and macOS; `frontend/pnpm-lock.yaml`). Only releases published at least 14 days before the lock date (10 Nov 2026) are allowed (IMP-06).

## Platform baseline

| Component | Version | How it is fixed |
|---|---|---|
| Python | 3.12 (uv-managed CPython build) | `backend/.python-version`, `requires-python = ">=3.12,<3.13"` |
| uv | 0.9 or newer (laptop: 0.12.12) | `required-version` in `pyproject.toml` |
| Node.js | 22.22.0 or newer, latest Node.js 22 LTS (laptop: 22.23.5) | `engines` in `package.json`, enforced by `engineStrict` (IMP-05) |
| pnpm | 12.16.1 | `packageManager` in `package.json`, recorded in the lockfile |
| PostgreSQL | 18.7 | `install-postgres.sh` installs exactly `postgresql-18=18.7-*` from PGDG |
| pgvector | 0.8.7 | `install-postgres.sh` installs exactly `postgresql-18-pgvector=0.8.7-*`; migration 0001 refuses < 0.8.0 |
| Ollama | laptop: 0.40.4 (latest release 0.40.18) | Not pinned by the project; recorded per run |
| Models | `qwen3:4b` (digest `359d7dd4bcda`), `qwen3-embedding:0.6b` | `.env`; digests recorded by `40-setup-ollama.ps1` |

## Backend (Python, direct dependencies)

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.162.2 | HTTP API framework (brings Starlette 1.10.0) |
| uvicorn[standard] | 0.54.0 | ASGI server |
| pydantic | 2.14.3 | Validation and schemas |
| pydantic-settings | 2.16.2 | Environment-based settings |
| sqlalchemy | 2.1.8 | ORM and SQL toolkit |
| psycopg[binary] | 3.3.8 | PostgreSQL driver |
| alembic | 1.20.1 | Migrations |
| pgvector | 0.5.1 | `vector` type for SQLAlchemy |
| httpx2 | 2.16.0 | HTTP client (Ollama gateway, test client) |
| charset-normalizer | 3.5.2 | File encoding detection |
| python-multipart | 0.0.33 | File uploads |
| argon2-cffi | 25.1.0 | Argon2id password hashing |
| python-dateutil | 4.0.0 | Reading written dates in feedback files (D06 step 7) |
| *dev:* ruff | 0.17.4 | Formatter and linter |
| *dev:* mypy | 2.4.1 | Static type checking (strict) |
| *dev:* pytest | 9.2.0 | Tests |
| *dev:* pytest-cov | 7.1.0 | Coverage |

## Frontend (direct dependencies)

| Package | Version | Package | Version |
|---|---|---|---|
| react, react-dom | 19.3.1 | vite | 8.3.7 |
| react-router | 8.5.1 | @vitejs/plugin-react | 6.3.0 |
| @tanstack/react-query | 5.107.1 | tailwindcss, @tailwindcss/vite | 4.3.5 |
| class-variance-authority | 0.7.1 | typescript | 6.0.3 (IMP-03) |
| clsx | 2.1.1 | eslint | 10.14.0 |
| tailwind-merge | 3.7.0 | typescript-eslint | 8.72.2 |
| lucide-react | 1.70.0 | prettier | 3.9.10 |
| @radix-ui/react-slot | 1.5.0 | vitest, @vitest/coverage-v8 | 5.1.0 |
| tw-animate-css | 1.4.0 | @testing-library/react | 16.3.3 |
| shadcn CLI (for adding components) | 4.23.0 | jsdom | 31.0.0 |
| @fontsource-variable/ibm-plex-sans | 5.3.0 | | |

## Verified environments

| Environment | What was verified | Result |
|---|---|---|
| Build environment (Linux, Python 3.12.3, Node 22.23.5, PostgreSQL 18.7 + pgvector 0.8.7 built from the official source tags) | Backend lint, type check, 195 tests including real-database and job-queue tests; frontend type check, lint, format, 25 tests, production build; API and web app run together | All passed (24 Nov 2026) |
| Team laptop (Windows 11 26H2, i7-13700HX, RTX 4060 8 GB, 13.7 GB RAM) | Setup scripts 10–90 | Recorded in `.setup-reports\` when the scripts run |
