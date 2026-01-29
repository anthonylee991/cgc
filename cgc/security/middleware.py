"""Security middleware for CGC API."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class RateLimitState:
    """Tracks rate limit state for a client."""

    requests: int = 0
    window_start: float = 0.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware.

    Limits requests per IP address within a time window.
    """

    def __init__(
        self,
        app,
        requests_per_window: int = 100,
        window_seconds: int = 60,
        enabled: bool = True,
        exempt_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.enabled = enabled
        self.exempt_paths = exempt_paths or ["/health", "/", "/docs", "/openapi.json"]
        self._state: dict[str, RateLimitState] = defaultdict(RateLimitState)

    def _get_client_id(self, request: Request) -> str:
        """Get a unique identifier for the client."""
        # Try to get real IP from proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain (original client)
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection IP
        if request.client:
            return request.client.host

        return "unknown"

    def _is_rate_limited(self, client_id: str) -> tuple[bool, dict]:
        """Check if a client is rate limited.

        Returns:
            Tuple of (is_limited, headers_dict)
        """
        now = time.time()
        state = self._state[client_id]

        # Check if we're in a new window
        if now - state.window_start >= self.window_seconds:
            state.requests = 0
            state.window_start = now

        state.requests += 1
        remaining = max(0, self.requests_per_window - state.requests)
        reset_time = int(state.window_start + self.window_seconds)

        headers = {
            "X-RateLimit-Limit": str(self.requests_per_window),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

        if state.requests > self.requests_per_window:
            headers["Retry-After"] = str(int(reset_time - now))
            return True, headers

        return False, headers

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request with rate limiting."""
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_id = self._get_client_id(request)
        is_limited, headers = self._is_rate_limited(client_id)

        if is_limited:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {self.requests_per_window} per {self.window_seconds}s",
                },
                headers=headers,
            )

        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses."""

    def __init__(
        self,
        app,
        content_security_policy: str | None = None,
        custom_headers: dict[str, str] | None = None,
    ):
        super().__init__(app)
        self.custom_headers = custom_headers or {}

        # Default CSP for API (restrictive)
        self.csp = content_security_policy or "default-src 'none'; frame-ancestors 'none'"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Cache control for API responses
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        # Add custom headers
        for key, value in self.custom_headers.items():
            response.headers[key] = value

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs all requests for audit purposes."""

    def __init__(
        self,
        app,
        log_bodies: bool = False,
        mask_credentials: bool = True,
        logger=None,
    ):
        super().__init__(app)
        self.log_bodies = log_bodies
        self.mask_credentials = mask_credentials
        self.logger = logger

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"

    def _log(self, message: str) -> None:
        """Log a message."""
        if self.logger:
            self.logger.info(message)
        else:
            print(f"[CGC] {message}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log the request and response."""
        start_time = time.time()
        client_ip = self._get_client_ip(request)

        # Get API key name if present
        api_key_name = "anonymous"
        if hasattr(request.state, "api_key") and request.state.api_key:
            api_key_name = request.state.api_key.name

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            self._log(
                f"{client_ip} | {api_key_name} | {request.method} {request.url.path} | "
                f"{response.status_code} | {duration_ms:.2f}ms"
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Mask any credentials in error messages
            error_msg = str(e)
            if self.mask_credentials:
                from cgc.security.validation import mask_credentials
                error_msg = mask_credentials(error_msg)

            self._log(
                f"{client_ip} | {api_key_name} | {request.method} {request.url.path} | "
                f"ERROR | {duration_ms:.2f}ms | {error_msg}"
            )

            raise


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limits the size of incoming requests."""

    def __init__(self, app, max_size_mb: int = 10):
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size before processing."""
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Request too large",
                            "message": f"Maximum request size is {self.max_size_bytes // (1024*1024)}MB",
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)
