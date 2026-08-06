"""MailArchive FastAPI entrypoint — Phase 0."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.infrastructure.persistence.database import Base, engine
from app.infrastructure.persistence import models as _models  # noqa: F401
from app.schemas.auth import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mailarchive")

settings = get_settings()

_WEAK = ("change-me", "changeme", "secret", "password")


def _warn_weak_secrets() -> None:
    if (settings.app_env or "").lower() not in ("production", "prod"):
        return
    weak: list[str] = []
    for name, value in (
        ("SECRET_KEY", settings.secret_key),
        ("JWT_SECRET_KEY", settings.jwt_secret_key),
        ("DATA_ENCRYPTION_KEY", settings.data_encryption_key),
    ):
        v = (value or "").lower()
        if any(w in v for w in _WEAK) or len(value or "") < 16:
            weak.append(name)
    if weak:
        logger.error(
            "INSECURE production secrets detected (%s). Rotate before exposing the service.",
            ", ".join(weak),
        )


_warn_weak_secrets()

app = FastAPI(
    title=settings.app_name,
    version="0.9.0",
    description="MailArchive API — self-hosted email archiving",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    from app.infrastructure.persistence.migrate import run_migrations
    from app.infrastructure.system_overrides import clear_restart_flag

    # Prefer Alembic; create_all remains a safety net for empty / partially migrated DBs.
    try:
        run_migrations(engine)
    except Exception:
        logger.warning("Falling back to metadata.create_all after migration error")
        Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.create_all(bind=engine)
    _reclaim_orphaned_archive_jobs()
    from app.infrastructure.jobs.dispatcher import start_job_dispatcher

    start_job_dispatcher(poll_seconds=5.0)
    try:
        clear_restart_flag()
    except Exception:
        logger.debug("Could not clear system override restart flag", exc_info=True)
    logger.info(
        "MailArchive started env=%s db_engine=%s port=%s",
        settings.app_env,
        settings.db_engine,
        settings.bind_port,
    )


def _reclaim_orphaned_archive_jobs() -> None:
    """Mark interrupted ``running`` jobs as failed. ``pending`` jobs are left for the dispatcher."""
    from datetime import UTC, datetime

    from sqlalchemy import update

    from app.infrastructure.persistence.database import SessionLocal
    from app.infrastructure.persistence.models import ArchiveJobModel

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        result = db.execute(
            update(ArchiveJobModel)
            .where(ArchiveJobModel.status == "running")
            .values(
                status="failed",
                finished_at=now,
                updated_at=now,
                error_message="Job interrumpido: reinicio del servicio API (worker en memoria perdido)",
            )
        )
        db.commit()
        if result.rowcount:
            logger.warning("Reclaimed %s orphaned running archive job(s)", result.rowcount)
    except Exception:
        logger.exception("No se pudieron recuperar jobs huérfanos")
        db.rollback()
    finally:
        db.close()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, phase="0")
