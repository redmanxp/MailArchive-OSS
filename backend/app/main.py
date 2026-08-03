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

app = FastAPI(
    title=settings.app_name,
    version="0.1.0-phase0",
    description="MailArchive API — Fase 0 (install + auth + RBAC)",
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
    # Phase 0: create tables (Alembic also available). Safe for sqlite/mysql empty DB.
    Base.metadata.create_all(bind=engine)
    _reclaim_orphaned_archive_jobs()
    logger.info(
        "MailArchive started env=%s db_engine=%s port=%s",
        settings.app_env,
        settings.db_engine,
        settings.bind_port,
    )


def _reclaim_orphaned_archive_jobs() -> None:
    """Jobs run in in-process threads; after API restart they stay 'running' forever."""
    from datetime import UTC, datetime

    from sqlalchemy import update

    from app.infrastructure.persistence.database import SessionLocal
    from app.infrastructure.persistence.models import ArchiveJobModel

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        result = db.execute(
            update(ArchiveJobModel)
            .where(ArchiveJobModel.status.in_(("pending", "running")))
            .values(
                status="failed",
                finished_at=now,
                updated_at=now,
                error_message="Job interrumpido: reinicio del servicio API (worker en memoria perdido)",
            )
        )
        db.commit()
        if result.rowcount:
            logger.warning("Reclaimed %s orphaned archive job(s)", result.rowcount)
    except Exception:
        logger.exception("No se pudieron recuperar jobs huérfanos")
        db.rollback()
    finally:
        db.close()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, phase="0")
