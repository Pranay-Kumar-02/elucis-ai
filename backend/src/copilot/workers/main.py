"""Worker process entry point (``copilot-worker`` / ``python -m copilot.workers.main``).

Job handlers (ingest, analysis, generate_document, suggest_inputs, ...) are registered here
as each module is implemented. Until then the worker starts, verifies the database and
idles; it never invents work.
"""

from __future__ import annotations

import logging
import sys

from copilot.core.config import get_settings
from copilot.core.logging import configure_logging
from copilot.db.engine import get_engine
from copilot.workers.runtime import Handler, Worker

logger = logging.getLogger("copilot.worker")

HANDLERS: dict[str, Handler] = {}


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format.value)
    worker = Worker(
        get_engine("worker", settings),
        HANDLERS,
        poll_interval_s=settings.worker_poll_interval_s,
        heartbeat_interval_s=settings.worker_heartbeat_interval_s,
    )
    worker.install_signal_handlers()
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
