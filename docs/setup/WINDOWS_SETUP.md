# Windows development setup

This guide is for the team laptops (Windows 11, NVIDIA GPU). Every step is scripted, safe to re-run and writes a JSON report to `.setup-reports\`. That folder is git-ignored and never contains secrets.

## 1. Before you start

| Need | Why | Check |
|---|---|---|
| Project folder **outside OneDrive**, ideally without spaces (for example `C:\dev\AI-Product-Manager-Copilot`) | OneDrive syncs and locks `.venv` and `node_modules` (tens of thousands of files) during installs | `scripts\windows\10-check-prerequisites.ps1` warns |
| uv | Python 3.12 and locked backend dependencies | `uv --version` |
| Node.js **22.22.0 or newer** (latest Node.js 22 LTS: `winget install --id OpenJS.NodeJS.22 --exact`) | Vite 8 and React Router 8 | `node --version` |
| pnpm 12 | Locked frontend dependencies (the project pins 12.16.1) | `pnpm --version` |
| WSL2 with Ubuntu | Runs PostgreSQL 18 + pgvector (see section 4) | `wsl --list --verbose` |
| Ollama app | Local models on the GPU | `ollama --version` |
| About 6 GB free disk and at least 4 GB free RAM during model tests | Models: qwen3:4b 2.5 GB, qwen3-embedding:0.6b 0.6 GB | Task Manager |

## 2. One-command setup

Open PowerShell in the project folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\setup.ps1
```

It runs these steps in order and stops at the first failure:

| Step | Script | What it does | Admin? |
|---|---|---|---|
| 1 | `10-check-prerequisites.ps1` | Checks tools. Installs a uv-managed Python 3.12 if missing. Offers to upgrade Node.js with winget, only after you type `y` | Only for the Node.js upgrade (Windows asks) |
| 2 | `20-setup-project.ps1` | Creates `.env` with random secrets (not shown), runs `uv sync --frozen` and `pnpm install --frozen-lockfile`, records versions | No |
| 3 | `30-setup-database.ps1` | Installs PostgreSQL 18.7 + pgvector 0.8.7 in WSL Ubuntu, creates roles and databases, runs migrations and the database check | No (runs as root inside WSL) |
| 4 | `40-setup-ollama.ps1` | Pulls `qwen3:4b` (and `qwen3-embedding:0.6b` if missing), runs the model smoke test, restarts Ollama, re-checks | No |
| 5 | `90-verify.ps1` | Lint, type checks, all tests, production build, and a live API health check; writes `verify.md` | No |

## 3. Daily commands

```powershell
.\scripts\windows\dev-db.ps1 start      # start PostgreSQL (stays up until "stop" or reboot)
.\scripts\windows\dev-api.ps1           # http://127.0.0.1:8000/api/v1/docs
.\scripts\windows\dev-worker.ps1        # background worker
.\scripts\windows\dev-web.ps1           # http://127.0.0.1:5173
.\scripts\windows\dev-db.ps1 stop       # stop PostgreSQL
```

Manual equivalents (inside `backend\` and `frontend\`):

```powershell
uv run uvicorn elucis.main:create_app --factory --reload --port 8000
uv run elucis-worker
uv run alembic upgrade head
uv run elucis-db-check                 # report: .setup-reports\db-check.json
uv run elucis-ollama-check             # report: .setup-reports\ollama-check.json
pnpm dev
```

## 4. Why PostgreSQL runs in WSL2

PostgreSQL 18.7 and pgvector 0.8.7 are fixed by the design (D07). On Windows we compared three options:

| Option | Result |
|---|---|
| Native Windows installer + pgvector | pgvector publishes no Windows binaries. Building it needs Visual Studio Build Tools (about 6–8 GB, admin) and `nmake`, and must be repeated for each pgvector update |
| Docker Desktop (`pgvector/pgvector:pg18` image) | Docker Desktop is not installed. It needs a licence check for larger organisations and adds about 2–4 GB of RAM use on a 16 GB laptop that already runs models |
| **WSL2 Ubuntu + official PostgreSQL apt repository (PGDG)** | **Chosen.** Ubuntu on WSL2 is already installed. PGDG ships `postgresql-18` 18.7 and `postgresql-18-pgvector` 0.8.7 as signed packages. No Windows admin rights are needed. Data lives in the WSL disk, never in OneDrive |

How it works:

- PostgreSQL listens on `localhost` inside WSL. WSL forwards `127.0.0.1:5432` to Windows, so the backend connects with an ordinary URL.
- WSL stops a distribution shortly after its last Windows process exits. `dev-db.ps1 start` keeps one hidden `sleep infinity` process attached so the database stays up. No global WSL settings are changed.
- Three roles follow D07 §5. `app_owner` owns the schema and runs migrations. `app_api` and `app_worker` can only read and write data, so row-level security will apply to them. Their passwords are in `.env`.
- `elucis_test` is a separate database for automated tests. Tests never touch `elucis_dev`.

## 5. Configuration

The backend reads `.env` from the project root. Every variable is listed in [`.env.example`](../../.env.example). The frontend needs no configuration for development, because the Vite dev server proxies `/api` to `127.0.0.1:8000`. See [`frontend/.env.example`](../../frontend/.env.example).

To rotate database passwords: edit the three URLs in `.env`, then run `30-setup-database.ps1` again. It re-applies the passwords and changes nothing else.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `running scripts is disabled on this system` | Use the `powershell -ExecutionPolicy Bypass -File ...` form shown above |
| A Python package from somewhere else shows up in the venv | This machine has `PYTHONPATH` set. The scripts clear it for their own session. Running `uv` by hand: `Remove-Item Env:PYTHONPATH` first |
| `127.0.0.1:5432` not reachable | `.\scripts\windows\dev-db.ps1 status`, then `start`. Check `wsl --status` |
| `pnpm install` fails with an engines error | Node.js is older than 22.22.0: run step 1 again and accept the upgrade |
| Model test is slow or runs on the CPU | Close other GPU or RAM-heavy apps. `.setup-reports\ollama-check.json` → `gpu_offload` shows how much of each model is in VRAM |
| `uv sync` or `pnpm install` stalls or reports locked files | The project is inside OneDrive: move it out (section 1) |
