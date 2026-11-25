#!/usr/bin/env bash
# =============================================================================
# Install PostgreSQL 18 + pgvector 0.8.7 from the official PostgreSQL apt repository
# (PGDG) inside WSL2 Ubuntu, then create the Elucis roles and databases.
#
# Run by scripts/windows/30-setup-database.ps1 as:  wsl -d <distro> -u root -- bash <this>
# Reads three passwords from stdin (owner, api, worker; one per line) so they never appear
# on a command line. Idempotent and non-destructive: nothing is dropped, existing data stays.
# Optional first argument: path of a JSON summary to write (for the Windows setup report).
# =============================================================================
set -Eeuo pipefail

PG_MAJOR=18
PG_MINOR_WANTED="18.7"
PGVECTOR_WANTED="0.8.7"
PG_PORT=5432
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_DIR="$SCRIPT_DIR/../bootstrap"
ELUCIS_REPORT="${1:-}"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root (wsl -u root)"

# ---- secrets from stdin, before anything else can consume stdin ----
IFS= read -r ELUCIS_OWNER_PASSWORD || die "owner password missing on stdin"
IFS= read -r ELUCIS_API_PASSWORD || die "api password missing on stdin"
IFS= read -r ELUCIS_WORKER_PASSWORD || die "worker password missing on stdin"
ELUCIS_OWNER_PASSWORD=${ELUCIS_OWNER_PASSWORD%$'\r'}
ELUCIS_API_PASSWORD=${ELUCIS_API_PASSWORD%$'\r'}
ELUCIS_WORKER_PASSWORD=${ELUCIS_WORKER_PASSWORD%$'\r'}
export ELUCIS_OWNER_PASSWORD ELUCIS_API_PASSWORD ELUCIS_WORKER_PASSWORD
exec </dev/null

export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
log "Distribution: ${PRETTY_NAME}"

# ---- 1. PGDG repository (signed by the PostgreSQL project's key) ----
if ! grep -rqs "apt.postgresql.org" /etc/apt/sources.list.d/; then
  log "Adding the PostgreSQL apt repository (PGDG)"
  apt-get update -qq
  apt-get install -y -qq postgresql-common ca-certificates curl >/dev/null
  /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y >/dev/null
fi
apt-get update -qq

# ---- 2. exact versions ----
pg_candidate=$(apt-cache madison "postgresql-${PG_MAJOR}" | awk '{print $3}' | grep -E "^${PG_MINOR_WANTED//./\\.}-" | head -n1 || true)
vec_candidate=$(apt-cache madison "postgresql-${PG_MAJOR}-pgvector" | awk '{print $3}' | grep -E "^${PGVECTOR_WANTED//./\\.}-" | head -n1 || true)
[[ -n "$pg_candidate" ]] || die "postgresql-${PG_MAJOR} ${PG_MINOR_WANTED} not offered by PGDG for ${VERSION_CODENAME}"
[[ -n "$vec_candidate" ]] || die "postgresql-${PG_MAJOR}-pgvector ${PGVECTOR_WANTED} not offered by PGDG for ${VERSION_CODENAME}"
log "Installing postgresql-${PG_MAJOR}=${pg_candidate} and pgvector=${vec_candidate}"
apt-get install -y -qq \
  "postgresql-${PG_MAJOR}=${pg_candidate}" \
  "postgresql-client-${PG_MAJOR}=${pg_candidate}" \
  "postgresql-${PG_MAJOR}-pgvector=${vec_candidate}" >/dev/null

# ---- 3. cluster: create if missing, localhost only, fixed port ----
if ! pg_lsclusters -h | awk '{print $1" "$2}' | grep -qx "${PG_MAJOR} main"; then
  log "Creating cluster ${PG_MAJOR}/main"
  pg_createcluster "${PG_MAJOR}" main --port="${PG_PORT}" -- --auth-local=peer --auth-host=scram-sha-256 >/dev/null
fi
pg_conftool "${PG_MAJOR}" main set listen_addresses localhost
pg_conftool "${PG_MAJOR}" main set port "${PG_PORT}"
pg_conftool "${PG_MAJOR}" main set password_encryption scram-sha-256

# Start (systemd when WSL runs it, otherwise pg_ctlcluster directly).
if [[ "$(ps -p 1 -o comm=)" == "systemd" ]]; then
  systemctl enable "postgresql@${PG_MAJOR}-main" >/dev/null 2>&1 || true
  systemctl restart "postgresql@${PG_MAJOR}-main"
else
  pg_ctlcluster "${PG_MAJOR}" main restart || pg_ctlcluster "${PG_MAJOR}" main start
fi
for _ in $(seq 1 30); do
  pg_isready -q -h 127.0.0.1 -p "${PG_PORT}" && break
  sleep 1
done
pg_isready -q -h 127.0.0.1 -p "${PG_PORT}" || die "PostgreSQL did not start"

# ---- 4. roles, databases, extension (peer auth as the postgres OS user) ----
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "$BOOTSTRAP_DIR"/*.sql "$work"/
chmod 755 "$work"; chmod 644 "$work"/*.sql
log "Applying database bootstrap (roles app_owner, app_api, app_worker)"
( cd "$work" && runuser -p -u postgres -- psql -X -q -v ON_ERROR_STOP=1 -p "${PG_PORT}" \
    -f 01_roles_and_databases.sql postgres ) >/dev/null

# ---- 5. summary ----
server_version=$(runuser -u postgres -- psql -X -At -p "${PG_PORT}" -c "SHOW server_version" postgres)
vector_version=$(runuser -u postgres -- psql -X -At -p "${PG_PORT}" -d elucis_dev -c "SELECT extversion FROM pg_extension WHERE extname='vector'")
systemd=$([[ "$(ps -p 1 -o comm=)" == "systemd" ]] && echo true || echo false)
log "PostgreSQL ${server_version}, pgvector ${vector_version}, port ${PG_PORT}"
if [[ -n "${ELUCIS_REPORT:-}" ]]; then
  cat >"$ELUCIS_REPORT" <<JSON
{"distribution": "${PRETTY_NAME}", "codename": "${VERSION_CODENAME}",
 "postgresql_package": "${pg_candidate}", "pgvector_package": "${vec_candidate}",
 "server_version": "${server_version}", "pgvector_version": "${vector_version}",
 "port": ${PG_PORT}, "systemd": ${systemd}}
JSON
fi
log "Done"
