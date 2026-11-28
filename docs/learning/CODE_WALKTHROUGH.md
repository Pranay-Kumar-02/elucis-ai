# Code walkthrough: how Elucis AI works, and how to debug it yourself

For the team. Read it with the code open. Every section follows one request or job from start to finish: which function calls which, what goes in and out, which errors can happen, and how to find the cause **with SQL and logs, without asking an AI**.

Paths are relative to `backend/src/elucis/` (backend) and `frontend/src/` (frontend).

---

## 0. The big picture

```text
Browser (React, Vite dev server :5173)
   │  /api/...  (Vite proxies to :8000)
   ▼
API process (FastAPI, uvicorn :8000)          Worker process (elucis-worker)
   │  one DB transaction per request              │  polls the jobs table every 2 s
   │  writes rows + queues jobs                   │  runs one job at a time, step by step
   ▼                                              ▼
PostgreSQL 18 + pgvector (WSL)  ◄─────────────────┘
                                                  │
                                       Ollama (:11434): qwen3:4b, qwen3-embedding:0.6b
```

- The **API never calls the chat model** and never runs long work. It validates, writes rows and puts a row in `jobs`. Exception: `POST /analysis-runs` asks Ollama "is the model installed?" (a quick GET).
- The **worker** does the slow work: imports (`ingest`), analysis (`analysis`), workspace deletion (`delete_workspace`).
- **Row-level security (RLS):** every tenant table only shows rows whose `workspace_id` matches `SET LOCAL app.workspace_id`. If a query "returns nothing" although the data is there, the transaction is probably not bound to the workspace (see §9).

Start everything: `.\scripts\windows\dev-db.ps1 start`, then `dev-api.ps1`, `dev-worker.ps1`, `dev-web.ps1` (or `run-local.ps1`). **The worker does not reload code:** restart it after changing backend code.

---

## 1. A request through the API

`main.py: create_app(settings)` builds the app → `api/v1/router.py: build_router` mounts the module routers under `/api/v1`.

For a typical workspace route, e.g. `GET /api/v1/workspaces/{ws}/imports`:

1. `core/middleware.py` adds a request ID (`X-Request-ID`), enforces body limits (1 MB; 20 MB on upload paths, see `is_upload_path`).
2. `api/auth.py: get_db` opens **one** transaction as `app_api` (`DbDep`).
3. `api/auth.py: current_principal` reads the `session` cookie, loads the session, checks idle/absolute expiry, checks `X-CSRF-Token` on POST/PATCH/DELETE.
4. `api/auth.py: WorkspaceAccess(min_role)` (`ViewerDep` / `EditorDep` / `OwnerDep`): membership or **404**, binds RLS (`workspace_scope`), role check or **403** + `authz.refused` audit row.
5. The route calls the module's `service` function.
6. Any `AppError` (`core/errors.py`) becomes `{"error": {"code", "message", "details", "request_id"}}`.

| Status | Code | Usual cause |
|---|---|---|
| 401 | `not_authenticated` / `session_expired` | No cookie, or the session expired (30 min idle, 12 h max) |
| 400 / 403 | `csrf_missing` / `csrf_invalid` | Write without the `X-CSRF-Token` header (the frontend adds it from `/auth/me`) |
| 403 | `forbidden_role` | e.g. a Viewer starting an import |
| 404 | `not_found` | Not a member of that workspace (deliberately the same as "does not exist") |
| 409 | `run_in_progress` | An analysis run is queued or running |
| 422 | `validation_failed` / `no_analysable_records` | Bad input; `details` says which field |
| 503 | `model_unavailable` / `database_unavailable` | Ollama or PostgreSQL not reachable |

**Debug:** every log line has the request ID. The UI shows it as "Reference: …" under errors. Search the API terminal for that ID.

---

## 2. Imports: upload → check → start (API-14, check, API-15)

Code: `modules/imports/` (new), reusing `modules/ingestion/` (reading files, mapping, row validation).

```text
POST /workspaces/{ws}/files           router.upload_file
  ingestion.service.read_source_input(file | pasted_text, max_bytes) -> SourceInput(kind, data, filename, sha256)
  imports.service.store_upload(db, settings, ctx, src, source_type)
     ingestion.service.preview_source(...)  -> FilePreviewOut (format, encoding, columns, 20 rows, suggested mapping)
     earlier file with the same sha256?      -> duplicate_of_file (DR-10: a warning, never a refusal)
     storage.write_file(upload_dir, "<ws>/<uuid>", bytes)   (atomic: .partial then rename)
     INSERT source_files (+ data_sources "File uploads" on first use)
  -> 201 SourceFileOut

POST /workspaces/{ws}/files/{id}/check   -> ingestion.service.validate_source(...) on the stored file
POST /workspaces/{ws}/imports            imports.service.start_import(db, settings, ctx, ImportIn, Idempotency-Key)
     metrics? -> 422 not_supported_yet
     ingestion.service.open_for_rows(...)    -> 422 if the mapping does not fit or > 20,000 records
     identity.repository.enqueue_job(job_type="ingest", payload={"import_job_id"})
     INSERT import_jobs (status queued) + audit "import.started"
  -> 202 JobRef {job_id, resource_id = import id}
```

Errors: 413 `file_too_large`, 415 `unsupported_format`, 422 for bad JSON/CSV with a line number, 404 for an unknown file ID.

**Debug an upload:**

```sql
-- as app_owner (psql in WSL), always bind the workspace first:
SELECT set_config('app.workspace_id', '<workspace uuid>', false);
SELECT id, original_filename, size_bytes, detected_format, created_at FROM source_files ORDER BY created_at DESC LIMIT 5;
```

The bytes are in `data/uploads/<workspace>/<file id>`.

---

## 3. The ingest job (worker)

Code: `modules/imports/pipeline.py: run_ingest(ctx, settings)`, registered in `workers/main.py: build_handlers`.

```text
Worker.run_once (workers/runtime.py) claims a job (FOR UPDATE SKIP LOCKED), starts a heartbeat thread
run_ingest
  _start           -> import row 'processing'; load the file; FileAdapter + RowValidator;
                      decrypt the workspace's customer-key secret; detect the rating scale
  while position < total:
    _ingest_batch  (ONE transaction per 500 rows)
       RowValidator.validate(item) -> NormalizedRecord | RowError
       preprocessing.prepare.prepare_batch(db, BatchContext, records)   (§4)
       INSERT feedback_records ... ON CONFLICT (workspace, import, row, segment) DO NOTHING
       INSERT import_row_errors (rejected rows, failed records)
       queue.checkpoint(job, {"position": stop, "flags": {...}}, {"processed", "total"})
  _finish          -> build_report (counts FROM THE DATABASE), reconcile (DR-40), final status
```

- **Restart safety:** results and the cursor commit in the same transaction. After a crash the job is reclaimed (heartbeat older than 120 s) and resumes at `jobs.cursor.position`. Re-running a finished import does nothing.
- **Reconciliation:** `received = imported + rejected + duplicates + filtered + failed`. A mismatch sets the import to `failed` with "Reconciliation error".
- Job statuses: `queued → running → succeeded | succeeded_with_errors | retry_wait | failed`. Import statuses mirror them (`processing`, `completed`, `completed_with_errors`, `failed`).

**Debug a stuck or failed import:**

```sql
SELECT id, job_type, status, attempts, error, cursor, progress, heartbeat_at, run_after
  FROM jobs ORDER BY created_at DESC LIMIT 5;
```

- `status = queued` forever → the worker is not running. Start `dev-worker.ps1`.
- `retry_wait` → it failed and will retry at `run_after`; `error` holds the exception type; the worker terminal has the traceback.
- `failed` with "no handler for job type" → an old worker without that handler is running. Restart it.

```sql
SELECT status, report FROM import_jobs ORDER BY created_at DESC LIMIT 1;
SELECT row_number, kind, stage, code, message FROM import_row_errors WHERE import_job_id = '<id>' ORDER BY row_number;
```

---

## 4. Preprocessing (inside each ingest batch)

Code: `modules/preprocessing/`. Pure functions, each one tested on its own. The order is D06's:

| Step | Function | In → out | Excludes as |
|---|---|---|---|
| Clean | `clean.clean_text(raw)` | raw → text without HTML, quoted replies, signatures, control characters; NFC | – |
| Noise | `noise.is_noise(text)` | bool (no letters; boilerplate; < 3 words without a signal term) | `noise` |
| Standardise | `standardise.rating_1_to_5`, `product_version`, `customer_key(secret, id)` | 1–5 rating, "3.2.1", HMAC-SHA256 key | – |
| PII | `pii.mask(text)` → `Masked(text, counts)` | `[EMAIL] [PHONE] [CARD] [ID] [NAME]` | `pii_failed` (fail closed) |
| Duplicates | `duplicates.content_hash`, `find_primary` | same masked text **and** same customer (or both unknown, same source, within 24 h) | `duplicate` + `duplicate_of` |

`prepare.prepare_batch` runs them per record. It upserts `customers` for the keys and stores each record **in its final state**: `stage = prepared` and `analysable = true`, or one `exclusion_reason`, or `stage = failed` with a row error.

- **Masking engine:** Presidio + spaCy `en_core_web_sm`, loaded once per worker process (about 30 s the first time). If imports are slow at the start, that is the load.
- **The raw text never changes** (a database trigger refuses it). Only `processed_text` is masked, and only `processed_text` is ever shown or sent to a model.

**Debug "why was this record excluded?":**

```sql
SELECT row_number, stage, analysable, exclusion_reason, duplicate_of, pii_counts, left(processed_text, 80)
  FROM feedback_records WHERE import_job_id = '<id>' ORDER BY row_number LIMIT 50;
```

Test one function quickly without the app:

```powershell
cd backend
uv run python -c "from elucis.modules.preprocessing.pii import mask; print(mask('Mail riya@example.com, thanks Priya'))"
uv run python -c "from elucis.modules.preprocessing.noise import is_noise; print(is_noise('app crashes'))"
```

---

## 5. Analysis runs (API-31, API-32, the analysis job)

Start: `POST /workspaces/{ws}/analysis-runs` → `modules/analysis/service.start_run`:

1. Idempotency-Key repeat → same run.
2. A run queued or running → **409**.
3. No analysable records → **422**.
4. `check_models`: are `qwen3-embedding:0.6b` and the chat model installed in Ollama? If not → **503**.
5. Then it inserts `analysis_runs` (with a config snapshot) and a `jobs` row `analysis`.

The job: `modules/analysis/orchestrator.run_analysis(ctx, settings, gateway_factory)`. **The workflow is the list `STEPS`**, run in order; nothing decides the order at run time (ADR-06, no agent framework).

| Step | Function | What it does | Output tables |
|---|---|---|---|
| `embed` | `embedding.embed_step` | vectors for analysable records without one; batches of 64; 2 retries, then one by one | `record_embeddings` (+ `record_classifications` `embedding_failed`) |
| `classify` | `classify.classify_step` | CP-02 in batches of 10 (keys `r1..r10`) | `record_classifications` (`classified` / `unclassified`) |
| `cluster` | `themes.cluster_step` | PCA (≤ 50 components, seed 42) + HDBSCAN | `themes`, `theme_memberships` |
| `stats` | `themes.stats_step` | counts, customers, coverage, sentiment, weekly, trend | `theme_run_stats` |
| `name` | `themes.name_step` | CP-03 names each theme from 5 central + 3 boundary records; checks cited IDs | `themes.name`, `theme_run_stats.cited_record_ids` |
| `requests` | `requests.requests_step` | candidates → CP-04 asks → embed asks → agglomerative grouping | `aggregated_requests`, `request_memberships` |
| (activate) | `orchestrator.activate` | report, `succeeded`, archive older themes/requests, set `workspaces.current_analysis_run_id` | `analysis_runs`, `workspaces` |

After each step the job's cursor becomes `{"step": "<next step>"}`, so a retry resumes there. A failed run never replaces the current one.

**Every model call** goes through `tasks.run_task(TaskContext, PromptSpec, content, Schema, check)`:

- It sends the prompt from `ai/prompts.py` with the JSON schema as Ollama `format`, then validates with Pydantic and the call's rule (`check`).
- Invalid output is retried 2 times with the error fed back, then it returns `None` and the caller falls back.
- An unreachable Ollama is retried 2 times, then the exception is raised, so the job retries later.
- Every attempt is logged in `llm_call_records`: model, prompt version, input hash, tokens, milliseconds, outcome. Prompt and reply texts are **not** stored.

**Optional Gemini backup (IMP-38):**
- `ai/gemini.py: GeminiClient` speaks Gemini's REST API (`generateContent`) and offers the same `chat_json` as the Ollama client.
- In `run_task`, it is used only when `TaskContext.fallback` is set: the workspace switch is on (Settings › General › AI backup) **and** `GEMINI_API_KEY` is set. Then it is tried after the local model failed that call.
- Its attempts are logged with `provider = 'gemini'`.
- Debug: `SELECT provider, call_id, outcome, count(*) FROM llm_call_records WHERE job_id = '<job>' GROUP BY 1, 2, 3;`.
- Check the key works: `uv run python scripts/check_gemini.py`.

Fallbacks:
- CP-02 batch invalid → one record at a time → `unclassified`.
- CP-03 invalid → "Unnamed theme n".
- CP-04 invalid → the record's own text cut to 12 words, `low_confidence = true`.

**Debug a run:**

```sql
SELECT id, status, report, started_at, finished_at FROM analysis_runs ORDER BY created_at DESC LIMIT 3;
SELECT cursor, progress, attempts, error FROM jobs WHERE id = (SELECT job_id FROM analysis_runs ORDER BY created_at DESC LIMIT 1);
-- What did the model do, and how fast?
SELECT call_id, outcome, count(*), round(avg(total_ms)) AS avg_ms
  FROM llm_call_records WHERE job_id = '<job id>' GROUP BY 1, 2 ORDER BY 1, 2;
-- Labels and themes:
SELECT category, count(*) FROM record_classifications WHERE analysis_run_id = '<run>' AND status = 'classified' GROUP BY 1;
SELECT t.name, s.record_count, s.trend FROM themes t JOIN theme_run_stats s ON s.theme_id = t.id
  WHERE t.first_run_id = '<run>' ORDER BY s.record_count DESC;
```

- Many `invalid_output` rows for CP-02 → the model is not following the schema (check the model tag, F-01).
- `error` rows → Ollama was down. `ollama ps` shows what is loaded; `ollama list` shows what is installed.
- "No themes" with few records is expected: fewer than 10 classified records are not clustered.

Run the job's steps in a test without a GPU: `tests/fakes.py: FakeGateway` (deterministic embeddings and answers), as `tests/test_themes.py` does.

---

## 6. Insights (what the dashboard shows)

`GET /workspaces/{ws}/insights?from=&to=&source_type=&pain_points_only=` → `modules/insights/service.insights`:

```text
_run(db, ws, run_id)                    current succeeded run, or None (-> empty response, not an error)
theme_list(db, ws, run, Filters)
   stats.theme_stats -> stats.group_stats(db, ws, run, ThemeMembership, theme_id, filters)
        one SQL query: members × feedback_records × record_classifications, filtered
        -> GroupStats(record_count, known_customers, unknown_identity_records, coverage,
                      share, sentiment, categories, weekly, trend, vocal_flag, pain_point)
   _evidence(...)  cited records first, then nearest to the centroid (pgvector <=>)
request_list(...)  same, via RequestMembership; asks counted per group
```

Rules, all in `insights/stats.py`:
- **Known customers** = distinct non-null customer IDs; unknown identities are never counted as customers.
- **Trend**: least-squares slope over the last 8 ISO weeks with data; "up" or "down" at ≥ 5% change and ≥ 3 records.
- **Pain point**: at least half of the theme's records are issues or negative.

The model is never used to count.

`themes/{id}` and `requests/{id}` return the same object with up to 10 quotes.

**Debug "the numbers look wrong":** call the API directly. In the browser, open `/api/v1/workspaces/<ws>/insights` while signed in. Compare with:

```sql
SELECT t.name, count(*) FROM theme_memberships m JOIN themes t ON t.id = m.theme_id
  WHERE m.analysis_run_id = '<run>' GROUP BY t.name;
```

If they differ only with a filter, check the dates: undated records drop out of a period filter, and weeks start on Monday (UTC).

---

## 7. Frontend

- `app/routes.tsx`: the route table. `features/auth/RequireAuth` guards the shell.
- `lib/api/client.ts: apiRequest`: every call. It adds the CSRF header on writes and turns the error envelope into `ApiError` (`code`, `message`, `details`, `requestId`).
- `lib/api/endpoints.ts`: one function per API call. `lib/api/types.ts`: their types, kept identical to the backend schemas.
- Data fetching is TanStack Query (`features/*/queries.ts`). Polling: imports and runs refetch every 2 s while not final.
- Screens:
  - `features/sources/ImportsPage.tsx`: upload, preview, mapping, check, Start import.
  - `features/imports/ImportDetailPage.tsx`: progress, reconciliation, PII counts, row errors.
  - `features/analysis/AnalysisPanel.tsx`: Run analysis, progress, last run.
  - `features/insights/InsightsView.tsx`: filters, tiles, themes, requests.
  - `features/dashboard/DashboardPage.tsx`: shows Insights once a run has succeeded.

**Debug in the browser:** DevTools → Network → the failing `/api/...` call → Response shows the error envelope with `request_id`. Then search the API terminal for it.

Tests: `pnpm verify` in `frontend/`. A single file: `pnpm exec vitest run src/features/insights`.

---

## 8. Tests and checks

| Command | What it proves |
|---|---|
| `uv run pytest` (backend) | Unit tests, plus real-database tests (`db`) as the real roles `app_api`/`app_worker` on `elucis_test`, each session in a throwaway schema. Plus live model tests (`ollama`), skipped with a reason if Ollama is off |
| `uv run pytest tests/test_imports.py -k resume -s` | One test, with prints |
| `uv run ruff check . ; uv run mypy` | Lint and strict types |
| `pnpm verify` (frontend) | Types, lint, format, Vitest, production build |
| `.\scripts\windows\90-verify.ps1` | All of the above plus a live API check (13 checks) |
| `uv run python scripts/benchmark_models.py` | F-01 model benchmark → `docs/evaluation/MODEL_BENCHMARK.md` |
| `uv run python scripts/evaluate.py --workspace Evaluation --labels … --source zenodo` | Accuracy report → `docs/evaluation/ACCURACY_REPORT.md` |

---

## 9. Common failures and how to find the cause

| Symptom | Where to look | Usual cause and fix |
|---|---|---|
| A query returns 0 rows although data exists | Your SQL session | RLS: run `SELECT set_config('app.workspace_id', '<ws>', false);` first (as app_owner too: RLS is forced) |
| Import stays "Queued" | `SELECT status FROM jobs …` | The worker is not running → `dev-worker.ps1` |
| New backend code has no effect in jobs | Worker terminal | The worker does not reload → restart it |
| A route returns 404 but works in tests | `GET /api/v1/openapi.json` | An old API process still holds port 8000 → stop the old uvicorn process |
| "Run analysis" says the model is unavailable (503) | `ollama list` | Model not pulled, or Ollama not started |
| Run fails with `ProgrammingError … column does not exist` | `uv run alembic current` | A migration is missing on `elucis_dev` → `uv run alembic upgrade head` |
| `uv sync` / `uv add` fails: "elucis-worker.exe … used by another process" | – | Stop the worker first, then sync |
| Import "Reconciliation error" | `import_jobs.report` | A count does not add up: compare `received` with the rows in `feedback_records` + `import_row_errors` |
| A record is `pii_failed` | Worker log: "PII masking failed" with the traceback | The masking engine raised; the record is excluded on purpose (fail closed) |
| Themes are all "Unnamed theme n" | `llm_call_records` for CP-03 | CP-03 kept failing its rules (e.g. digits in the name, unknown cited IDs) or Ollama was down |
| Tests fail with "connection timeout" | `dev-db.ps1 status` | PostgreSQL in WSL stopped (for example after sleep) → `dev-db.ps1 start` |
| A queue test fails once in a while | F-07 | The WSL clock is corrected about every 30 s; tests use times an hour in the past for that reason |
