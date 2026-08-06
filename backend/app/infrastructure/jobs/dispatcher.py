"""In-process archive job dispatcher.

Jobs are persisted in ``archive_jobs``. On API restart, ``running`` jobs are marked
failed; ``pending`` jobs are picked up by this poller so work survives restarts
without Redis/Celery (single-node OSS default).
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

_started = False
_stop = threading.Event()


def start_job_dispatcher(*, poll_seconds: float = 5.0) -> None:
    global _started
    if _started:
        return
    _started = True
    _stop.clear()
    t = threading.Thread(
        target=_loop,
        args=(poll_seconds,),
        name="archive-job-dispatcher",
        daemon=True,
    )
    t.start()
    logger.info("Archive job dispatcher started (poll=%.1fs)", poll_seconds)


def stop_job_dispatcher() -> None:
    _stop.set()


def _loop(poll_seconds: float) -> None:
    # Lazy imports: avoid circular import with application layer at module load.
    from app.application.use_cases.accounts.bulk_archive import run_archive_job
    from app.infrastructure.persistence.database import SessionLocal
    from app.infrastructure.persistence.repositories.job_repo import SqlAlchemyArchiveJobRepository

    while not _stop.is_set():
        try:
            db = SessionLocal()
            try:
                repo = SqlAlchemyArchiveJobRepository(db)
                pending = repo.list_pending(limit=5)
                for job in pending:
                    logger.info("Dispatcher picking pending job id=%s tenant=%s", job.id, job.tenant_id)
                    threading.Thread(
                        target=run_archive_job,
                        args=(job.id, job.tenant_id),
                        name=f"archive-job-{job.id}",
                        daemon=True,
                    ).start()
                    # Small stagger so we don't stampede the provider
                    time.sleep(0.2)
            finally:
                db.close()
        except Exception:
            logger.exception("Job dispatcher loop error")
        _stop.wait(poll_seconds)
