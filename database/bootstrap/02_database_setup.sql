-- Per-database setup, included by 01_roles_and_databases.sql while connected to the
-- target database as a superuser. Idempotent.
\set ON_ERROR_STOP on

-- pgvector is not a trusted extension, so a superuser creates it (D07: PostgreSQL 18 + pgvector).
CREATE EXTENSION IF NOT EXISTS vector;

-- Only app_owner may create objects; application roles use them.
REVOKE ALL ON DATABASE :"DBNAME" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"DBNAME" TO app_owner, app_api, app_worker;
ALTER SCHEMA public OWNER TO app_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO app_api, app_worker;

-- Tables created later by migrations (as app_owner) are usable by the application roles.
-- Row-level security (D07 section 5) restricts which rows; these grants decide which tables.
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_api, app_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_api, app_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO app_api, app_worker;

-- Sensible per-role defaults (can be overridden per transaction).
ALTER ROLE app_api    IN DATABASE :"DBNAME" SET statement_timeout = '30s';
ALTER ROLE app_worker IN DATABASE :"DBNAME" SET statement_timeout = '15min';
ALTER ROLE app_api    IN DATABASE :"DBNAME" SET idle_in_transaction_session_timeout = '60s';

SELECT current_database() AS database,
       (SELECT extversion FROM pg_extension WHERE extname = 'vector') AS pgvector;
