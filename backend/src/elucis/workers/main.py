"""Worker process entry point (``elucis-worker`` / ``python -m elucis.workers.main``).

Job handlers are registered here as each module is implemented (``delete_workspace`` so
far; ingest, analysis, generate_document and the others follow). Jobs without a handler
fail cleanly; the worker never invents work.
"""

from __future__ import annotations

import logging
import sys
from functools import partial

from elucis.core.config import get_settings
from elucis.core.logging import configure_logging
from elucis.db.engine import get_engine
from elucis.workers.handlers.workspaces import delete_workspace
from elucis.workers.maintenance import MAINTENANCE_INTERVAL_S, purge_expired
from elucis.workers.runtime import Handler, Worker

logger = logging.getLogger("elucis.worker")

HANDLERS: dict[str, Handler] = {"delete_workspace": delete_workspace}


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format.value)
    worker = Worker(
        get_engine("worker", settings),
        HANDLERS,
        poll_interval_s=settings.worker_poll_interval_s,
        heartbeat_interval_s=settings.worker_heartbeat_interval_s,
        maintenance=partial(purge_expired, session_idle_minutes=settings.session_idle_minutes),
        maintenance_interval_s=MAINTENANCE_INTERVAL_S,
    )
    worker.install_signal_handlers()
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
