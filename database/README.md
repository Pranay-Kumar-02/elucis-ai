# database

| Path | Purpose |
|---|---|
| `bootstrap/01_roles_and_databases.sql` | Run once as a superuser: roles `app_owner`, `app_api`, `app_worker` (D07 §5), databases `elucis_dev` and `elucis_test`. Idempotent; never drops anything. Passwords come from environment variables, never from this file |
| `bootstrap/02_database_setup.sql` | Per database: `CREATE EXTENSION vector`, schema ownership, default privileges for tables created later by migrations |
| `wsl/install-postgres.sh` | Installs PostgreSQL 18.7 + pgvector 0.8.7 from the official PostgreSQL apt repository in WSL2 Ubuntu and applies the bootstrap. Run through `scripts/windows/30-setup-database.ps1` |

Schema changes are Alembic migrations in `backend/migrations/` (run as `app_owner`). The 54 tables of D07/D08 start at revision 0002.
