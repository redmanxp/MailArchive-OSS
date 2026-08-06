"""SQLAlchemy database setup."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _create_engine():
    settings = get_settings()
    url = settings.build_database_url()
    connect_args: dict = {}
    if url.startswith("sqlite"):
        # Allow worker threads + wait instead of immediate "database is locked"
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
    engine = create_engine(url, echo=settings.app_debug, future=True, connect_args=connect_args)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # WAL: readers don't block writers; needed with job/schedule threads
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def commit_with_retry(db: Session, *, attempts: int = 8, base_delay: float = 0.05) -> None:
    """Commit with backoff on SQLite 'database is locked' (no rollback — keeps pending work)."""
    import logging
    import time

    from sqlalchemy.exc import OperationalError

    log = logging.getLogger(__name__)
    last: Exception | None = None
    for i in range(max(1, attempts)):
        try:
            db.commit()
            return
        except OperationalError as exc:
            last = exc
            msg = str(exc).lower()
            if "locked" not in msg and "busy" not in msg:
                raise
            delay = base_delay * (2**i)
            log.warning("SQLite locked on commit (try %s/%s), retry in %.2fs", i + 1, attempts, delay)
            time.sleep(delay)
    assert last is not None
    raise last


def write_with_retry(db: Session, action, *, attempts: int = 8, base_delay: float = 0.05) -> None:
    """Run ``action()`` then commit; on SQLite lock, rollback and retry the whole write."""
    import logging
    import time

    from sqlalchemy.exc import OperationalError

    log = logging.getLogger(__name__)
    last: Exception | None = None
    for i in range(max(1, attempts)):
        try:
            action()
            db.commit()
            return
        except OperationalError as exc:
            last = exc
            msg = str(exc).lower()
            if "locked" not in msg and "busy" not in msg:
                raise
            db.rollback()
            delay = base_delay * (2**i)
            log.warning("SQLite locked on write (try %s/%s), retry in %.2fs", i + 1, attempts, delay)
            time.sleep(delay)
    assert last is not None
    raise last
