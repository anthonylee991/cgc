"""In-memory rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, HTTPException


class RateLimiter:
    """Per-IP / per-key rate limiter with sliding window."""

    def __init__(self):
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int, window: int = 60) -> None:
        """Check if the key has exceeded the rate limit.

        Args:
            key: Identifier (IP or license key)
            limit: Max requests per window
            window: Window size in seconds
        """
        now = time.time()
        cutoff = now - window

        # Prune old entries
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]

        if len(self._hits[key]) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(window)},
            )

        self._hits[key].append(now)


# Global instance
limiter = RateLimiter()


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"
