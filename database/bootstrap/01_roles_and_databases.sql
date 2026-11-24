-- =============================================================================
-- AI Product Manager Copilot - database bootstrap (run once per machine, as a superuser)
--
-- Creates the three roles from D07 section 5 and the dev + test databases, installs
-- pgvector and sets default privileges. Idempotent and NON-destructive: it never drops
-- anything; re-running it only re-applies passwords and grants.
--
-- Passwords are never written in this file. They come from environment variables
-- (COPILOT_OWNER_PASSWORD, COPILOT_API_PASSWORD, COPILOT_WORKER_PASSWORD), which keeps
-- them off the command line, or from psql -v variables of the same lower-case names.
-- scripts/windows/30-setup-database.ps1 runs this for you with the values from .env.
-- =============================================================================
\set ON_ERROR_STOP on
\if :{?owner_password}
\else
  \getenv owner_password COPILOT_OWNER_PASSWORD
\endif
\if :{?api_password}
\else
  \getenv api_password COPILOT_API_PASSWORD
\endif
\if :{?worker_password}
\else
  \getenv worker_password COPILOT_WORKER_PASSWORD
\endif
\if :{?owner_password}
  \if :{?api_password}
    \if :{?worker_password}
    \else
      DO $$ BEGIN RAISE EXCEPTION 'COPILOT_WORKER_PASSWORD is not set'; END $$;
    \endif
  \else
    DO $$ BEGIN RAISE EXCEPTION 'COPILOT_API_PASSWORD is not set'; END $$;
  \endif
\else
  DO $$ BEGIN RAISE EXCEPTION 'COPILOT_OWNER_PASSWORD is not set'; END $$;
\endif

-- ---------- roles (LOGIN, no superuser, no createrole) ----------
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB', r)
  FROM unnest(ARRAY['app_owner', 'app_api', 'app_worker']) AS r
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r)
\gexec

SELECT format('ALTER ROLE app_owner  PASSWORD %L', :'owner_password')  \gexec
SELECT format('ALTER ROLE app_api    PASSWORD %L', :'api_password')    \gexec
SELECT format('ALTER ROLE app_worker PASSWORD %L', :'worker_password') \gexec

-- ---------- databases ----------
SELECT format('CREATE DATABASE %I OWNER app_owner ENCODING ''UTF8'' TEMPLATE template0', d)
  FROM unnest(ARRAY['copilot_dev', 'copilot_test']) AS d
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = d)
\gexec

-- ---------- per-database setup ----------
\c copilot_dev
\ir 02_database_setup.sql
\c copilot_test
\ir 02_database_setup.sql

\echo 'Bootstrap complete: roles app_owner, app_api, app_worker; databases copilot_dev, copilot_test.'
