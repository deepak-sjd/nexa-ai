"""
Small in-memory rate limiter (no extra dependency).

Limits are per client IP and per endpoint group, using a sliding
window. State lives in this process, so with N worker processes the
effective limit is N x the configured one. That's fine for protecting
the Gemini quota; use Redis if you ever need exact limits.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

from app.core.config import settings


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()
        self._calls = 0

    def check(self, key: str) -> int:
        """Returns 0 if allowed, otherwise seconds until a retry works."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            hits = self._hits[key]

            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.max_requests:
                return max(1, int(hits[0] + self.window_seconds - now) + 1)

            hits.append(now)

            # Occasionally drop keys that have gone quiet.
            self._calls += 1
            if self._calls % 1000 == 0:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]

            return 0


def client_ip(request: Request) -> str:
    # Only trust X-Forwarded-For when running behind your own proxy
    # (TRUST_PROXY_HEADERS=true); otherwise anyone could fake it.
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def rate_limit(name: str, max_requests: int, window_seconds: float = 60):
    """FastAPI dependency: `dependencies=[Depends(...)]` or use the
    ready-made ones below."""
    limiter = SlidingWindowLimiter(max_requests, window_seconds)

    def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return

        retry_after = limiter.check(f"{name}:{client_ip(request)}")

        if retry_after:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a minute and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


chat_rate_limit = rate_limit("chat", settings.rate_limit_chat_per_minute)
image_rate_limit = rate_limit("image", settings.rate_limit_image_per_minute)
upload_rate_limit = rate_limit("upload", settings.rate_limit_upload_per_minute)
auth_rate_limit = rate_limit("auth", settings.rate_limit_auth_per_minute)