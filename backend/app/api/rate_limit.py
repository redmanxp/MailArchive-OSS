"""In-process rate limiting for public auth endpoints (login / register / install).

Design notes
------------
* Process-local only: fine for single-worker uvicorn (archive jobs already assume that).
* Not shared across replicas — use a reverse-proxy or Redis limiter for multi-instance prod.
* Key = ``{scope}:{client_ip}``; X-Forwarded-For first hop is trusted when present
  (ensure the proxy strips spoofed headers).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import Settings, get_settings

logger = logging.getLogger("mailarchive.rate_limit")


class InMemoryRateLimiter:
    """Sliding-window counter: at most *limit* hits per *window_seconds* per key."""

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
                logger.warning(
                    "Rate limit exceeded key=%s limit=%s window=%ss",
                    key,
                    limit,
                    window_seconds,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiados intentos. Probá de nuevo más tarde.",
                )
            bucket.append(now)


# Module singleton — shared by all requests in this process.
_limiter = InMemoryRateLimiter()


def client_ip(request: Request) -> str:
    """Best-effort client IP (proxy-aware)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request, scope: str, settings: Settings | None = None) -> None:
    """No-op when ``RATE_LIMIT_ENABLED`` is false; otherwise raise HTTP 429 on excess."""
    cfg = settings or get_settings()
    if not cfg.rate_limit_enabled:
        return
    ip = client_ip(request)
    key = f"{scope}:{ip}"
    _limiter.check(
        key,
        limit=cfg.rate_limit_requests,
        window_seconds=cfg.rate_limit_window_seconds,
    )
