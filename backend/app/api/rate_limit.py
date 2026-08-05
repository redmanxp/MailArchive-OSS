"""Simple in-memory rate limiter for auth/install endpoints."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import Settings, get_settings

logger = logging.getLogger("mailarchive.rate_limit")


class InMemoryRateLimiter:
    """Sliding-window limiter keyed by scope + client IP."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                logger.warning("Rate limit exceeded key=%s limit=%s window=%ss", key, limit, window_seconds)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiados intentos. Probá de nuevo más tarde.",
                )
            bucket.append(now)


_limiter = InMemoryRateLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request, scope: str, settings: Settings | None = None) -> None:
    """Raise 429 when the client exceeds the configured window for *scope*."""
    cfg = settings or get_settings()
    if not cfg.rate_limit_enabled:
        return
    ip = client_ip(request)
    key = f"{scope}:{ip}"
    _limiter.check(key, limit=cfg.rate_limit_requests, window_seconds=cfg.rate_limit_window_seconds)
