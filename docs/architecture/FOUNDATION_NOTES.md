# Foundation implementation notes

What the development foundation implements, where it follows the design exactly, and every place where implementation needed a decision the design did not make. Nothing here changes the SRS. Items marked **proposed** need the team's or the mentor's agreement before they are recorded in D11.

## 1. What exists now

| Area | Implemented | Design reference |
|---|---|---|
| App factory | FastAPI app with `/api/v1` prefix, OpenAPI at `/api/v1/docs` (not in production) | D09 §1 |
| Settings | Environment-based (`pydantic-settings`), secrets as `SecretStr`, production guards | D10 §2 (SEC-18) |
| Errors | One error envelope `{error: {code, message, details, request_id}}` for every failure, typed service errors | D09 §2 (IR-06) |
| Logging | Structured logs (console or JSON), request and job correlation IDs, redaction of credentials | D10 (SEC-17, NFR-24) |
| Middleware | ULID request IDs, 1 MB body limit, 20 MB upload limit, security headers, CORS for dev origins only | D09 §1, A-06 |
| Database | SQLAlchemy 2 + psycopg 3 engines per role, transaction scope, `SET LOCAL app.workspace_id` helper, Alembic baseline | D07 §5 |
| Health | `GET /api/v1/health` (API-87) plus `/live`, `/database`, `/model-runtime` | D09 API-87, AIR-22 |
| Model gateway | Ollama client: chat with JSON-schema constrained output, embeddings with dimension check, timings | D04 |
| Ingestion | `SourceAdapter` contract, `FileAdapter` (CSV, JSON, TXT), connector catalogue, development preview endpoints | D01 §3, D03 SVC-02 |
| Security | Argon2id password hashing with the 12–128 character policy | D03 SVC-01, SEC-01 |
| Worker | PostgreSQL job queue (`FOR UPDATE SKIP LOCKED`), heartbeat, checkpoints, retries with backoff, crash reclaim | D03 SVC-21, D07 `jobs` |
| Frontend | App shell, routing, typed API client, TanStack Query, dashboard placeholder, system status, file preview tool | D12 (foundation only) |

Not implemented yet, by design: the 54 tables (next task), authentication and workspaces, the ingest pipeline, all AI calls CP-01 to CP-10, and the 12 production screens.

## 2. Implementation decisions

| ID | Decision | Reason | Status |
|---|---|---|---|
| IMP-01 | PostgreSQL runs in **WSL2 Ubuntu from the official PGDG apt repository**, not natively on Windows or in Docker | pgvector has no Windows binaries (a native build needs Visual Studio Build Tools). Docker Desktop is not installed and costs RAM. PGDG ships exactly 18.7 and pgvector 0.8.7. Needs no admin rights. See `docs/setup/WINDOWS_SETUP.md` §4 | Decided for development. EXP-10 still measures performance |
| IMP-02 | Three database URLs (`DATABASE_URL` for app_api, `DATABASE_WORKER_URL` for app_worker, `DATABASE_MIGRATION_URL` for app_owner) and a separate `copilot_test` database | D07 §5 defines the three roles; RLS only applies to non-owners. Tests must never touch dev data | Follows design |
| IMP-03 | **TypeScript 6.0.3**, not 7.x | TypeScript 7 (native port) is newer, but `typescript-eslint` 8.x supports TypeScript `>=4.8.4 <6.1.0`, so type-aware linting would not work | Revisit when typescript-eslint supports 7 |
| IMP-04 | `httpx2` instead of `httpx` | Starlette 1.10 (inside FastAPI) deprecates `httpx` for its test client in favour of `httpx2`, the maintained successor; using one HTTP library everywhere avoids two stacks | Decided |
| IMP-05 | Node.js `>=22.22.0` (current LTS recommended) | React Router 8 requires Node 22.22+; Vite 8 requires 20.19+ or 22.12+. The laptop had 22.20.0 | Upgrade needed on the laptop |
| IMP-06 | **14-day dependency cooldown**: versions pinned to releases at least 14 days old (`exclude-newer` in uv, `minimumReleaseAge` in pnpm) | Supply-chain protection: most malicious package releases are detected and removed within days | Decided. Move the date forward deliberately when updating |
| IMP-07 | Synchronous SQLAlchemy sessions (FastAPI runs sync routes in its thread pool); async only for streaming and file upload | Simpler transactions and RLS scoping, same driver for API and worker, and no async ORM pitfalls. Throughput is far above a 3-user local deployment (NFR-07) | Decided |
| IMP-08 | Health: API-87 is `GET /api/v1/health`. Added `/health/live` (liveness), `/health/database` and `/health/model-runtime` (details shown only when `EXPOSE_DIAGNOSTICS` is on, never by default in production) | The setup task asks for `/health/database`, and tooling needs a cheap liveness probe | **Proposed** addition to D09 |
| IMP-09 | Two extra error codes: `method_not_allowed` (405) and `database_unavailable` (503) | D09 §2 has no code for these statuses; the envelope must still be used for every error | **Proposed** addition to D09 §2 |
| IMP-10 | `RawItem` is the adapter output name (D03); D09's `RawRow` is exported as an alias. `fetch(cursor)` yields batches of 500 with a resumable cursor `{"position": n}` | D03 and D09 used two names for the same contract | **Proposed** wording fix in D09 §5 |
| IMP-11 | Non-UTF-8 text files are decoded with `charset-normalizer` and the conversion is reported as a warning; undecodable or binary files are rejected | DR-05 names UTF-8; SVC-02 requires encoding detection. Excel often exports Windows-1252 or UTF-16 | Follows SVC-02; warning text is new |
| IMP-12 | Development-only endpoints `/api/v1/dev/sources/{adapters,preview,map}` exercise the real file adapter without auth or storage | Lets the team and mentor see data fetching before auth and schema exist. Replaced by API-14/API-15. Disabled unless `ENABLE_DEV_ENDPOINTS=true`; refused in production | Temporary |
| IMP-13 | Worker reclaims a `running` job whose heartbeat is older than 120 s; retries wait 30 s × 2^(attempt−1), at most 10 min; `max_attempts` default 3 (D07) | D03 SVC-21 requires heartbeats and restartable steps but gives no timings | Values to tune in EXP-01/03 |
| IMP-14 | The base shadcn/ui components (button, card, badge, table, alert, skeleton) were written in the shadcn "new-york" style by hand, because the shadcn registry was not reachable from the build environment. `components.json` is configured, so `pnpm dlx shadcn@4.23.0 add <component>` works on the laptop | Same API and class names as the registry versions; can be replaced one by one with `shadcn add --overwrite` | Decided |
| IMP-15 | uv uses managed CPython builds (`python-preference = "managed"`), and the scripts clear `PYTHONPATH` for their session | Everyone gets the same Python build; this laptop has `PYTHONPATH` set, which would leak foreign packages into the venv | Decided |

## 3. Findings to resolve before the next tasks

| ID | Finding | Evidence | Proposed action |
|---|---|---|---|
| F-01 | The Ollama tag `qwen3:4b` now points to **Qwen3-4B-Thinking-2507** (digest `359d7dd4bcda`, 256K context). The non-thinking variant is `qwen3:4b-instruct` (`0edcdef34593`, same 2.5 GB). Our CP calls are schema-constrained classification and drafting, where hidden reasoning only adds latency | ollama.com library tag list, 24 Nov 2026. The gateway sends `think: false`; the smoke test records whether the model still returned thinking text and the timings | **Proposed**: keep `qwen3:4b` as specified, and add `qwen3:4b-instruct` as a benchmark candidate in EXP-01 (`40-setup-ollama.ps1 -IncludeCandidates`). Choose by measured quality and speed |
| F-02 | The embedding dimension (`vector(1024)` in D07) must be confirmed before the schema migration | The smoke test measures it (`measured_embedding_dimension` in `.setup-reports\ollama-check.json`) | If it is not 1024, change D07 before writing migration 0002 (EXP-04) |
| F-03 | The laptop has 13.7 GB usable RAM and was at about 1 GB free during inventory | `.setup-reports\inventory.json` | Close heavy apps during model work. EXP-01 must measure memory with the API, worker, PostgreSQL (WSL) and Ollama running together (NFR-07) |
| F-04 | Ollama 0.40.4 is installed; the current release is 0.40.18 | GitHub release tags | Optional update; record the version used for EXP-01 |
