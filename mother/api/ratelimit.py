"""Rate limiting middleware for Mother API.

This module provides token bucket-based rate limiting with:
- Per-key rate limiting in multi-key mode
- Global rate limiting in legacy mode
- Configurable limits per role
- 429 Too Many Requests responses

Token Bucket Algorithm:
- Each key has a bucket with a maximum capacity (burst limit)
- Tokens are added at a fixed rate (refill rate)
- Each request consumes one token
- If no tokens available, request is rejected with 429
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("mother.api.ratelimit")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting.

    Attributes:
        enabled: Whether rate limiting is enabled
        default_rpm: Default requests per minute (legacy mode)
        burst_multiplier: Multiplier for burst limit (burst = rpm * multiplier)
        admin_rpm: RPM for admin keys
        operator_rpm: RPM for operator keys
        readonly_rpm: RPM for readonly keys
        exempt_paths: Paths exempt from rate limiting
    """

    enabled: bool = True
    default_rpm: int = 60  # 60 requests per minute
    burst_multiplier: float = 1.5  # Allow 1.5x burst
    admin_rpm: int = 300  # Admin gets higher limits
    operator_rpm: int = 120  # Operator gets moderate limits
    readonly_rpm: int = 60  # Readonly gets standard limits
    exempt_paths: list[str] = field(
        default_factory=lambda: [
            "/health",
            "/status",
            "/docs",
            "/openapi.json",
        ]
    )


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    Attributes:
        capacity: Maximum tokens in bucket (burst limit)
        refill_rate: Tokens added per second
        tokens: Current token count
        last_refill: Timestamp of last refill
    """

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self):
        """Initialize tokens to capacity."""
        self.tokens = self.capacity

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def get_retry_after(self) -> float:
        """Get seconds until a token will be available.

        Returns:
            Seconds until next token available
        """
        if self.tokens >= 1.0:
            return 0.0
        tokens_needed = 1.0 - self.tokens
        return tokens_needed / self.refill_rate

    def get_remaining(self) -> int:
        """Get the number of remaining tokens.

        Returns:
            Remaining tokens (floored to int)
        """
        self._refill()
        return int(self.tokens)


class RateLimiter:
    """Token bucket-based rate limiter.

    Manages rate limiting across multiple keys with configurable
    limits per role. Thread-safe for concurrent access.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        """Initialize the rate limiter.

        Args:
            config: Rate limiting configuration
        """
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _get_bucket(self, key: str, rpm: int) -> TokenBucket:
        """Get or create a bucket for a key.

        Args:
            key: The rate limit key (API key name or "global")
            rpm: Requests per minute limit

        Returns:
            TokenBucket for the key
        """
        with self._lock:
            if key not in self._buckets:
                capacity = rpm * self.config.burst_multiplier
                refill_rate = rpm / 60.0  # Convert RPM to tokens per second
                self._buckets[key] = TokenBucket(
                    capacity=capacity,
                    refill_rate=refill_rate,
                )
            return self._buckets[key]

    def check(
        self,
        key: str,
        role: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Check if request is allowed under rate limit.

        Args:
            key: The rate limit key (API key name or "global")
            role: Role for determining limit (admin/operator/readonly)

        Returns:
            Tuple of (allowed, headers) where headers contains rate limit info
        """
        if not self.config.enabled:
            return True, {}

        # Determine RPM based on role
        if role == "admin":
            rpm = self.config.admin_rpm
        elif role == "operator":
            rpm = self.config.operator_rpm
        elif role == "readonly":
            rpm = self.config.readonly_rpm
        else:
            rpm = self.config.default_rpm

        bucket = self._get_bucket(key, rpm)

        headers = {
            "X-RateLimit-Limit": str(rpm),
            "X-RateLimit-Remaining": str(bucket.get_remaining()),
            "X-RateLimit-Reset": str(int(time.time() + 60)),  # Reset in 60s
        }

        if bucket.consume():
            headers["X-RateLimit-Remaining"] = str(bucket.get_remaining())
            return True, headers

        retry_after = bucket.get_retry_after()
        headers["Retry-After"] = str(int(retry_after) + 1)
        return False, headers

    def reset(self, key: str) -> None:
        """Reset the bucket for a key.

        Args:
            key: The rate limit key to reset
        """
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics.

        Returns:
            Dictionary of statistics
        """
        with self._lock:
            return {
                "enabled": self.config.enabled,
                "active_buckets": len(self._buckets),
                "buckets": {
                    key: {
                        "remaining": bucket.get_remaining(),
                        "capacity": int(bucket.capacity),
                    }
                    for key, bucket in self._buckets.items()
                },
            }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting.

    Integrates with multi-key authentication to provide per-key
    rate limiting with role-based limits.
    """

    def __init__(self, app, rate_limiter: RateLimiter | None = None):
        """Initialize the middleware.

        Args:
            app: FastAPI application
            rate_limiter: RateLimiter instance (created if not provided)
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiter.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        # Check if path is exempt
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Get rate limit key and role
        key, role = self._get_key_and_role(request)

        # Check rate limit
        allowed, headers = self.rate_limiter.check(key, role)

        if not allowed:
            logger.warning(f"Rate limit exceeded for key: {key}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please retry later.",
                    "retry_after": headers.get("Retry-After", "60"),
                },
                headers=headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header, value in headers.items():
            response.headers[header] = value

        return response

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting.

        Args:
            path: Request path

        Returns:
            True if exempt
        """
        return any(path.startswith(exempt) for exempt in self.rate_limiter.config.exempt_paths)

    def _get_key_and_role(self, request: Request) -> tuple[str, str | None]:
        """Get rate limit key and role from request.

        Args:
            request: Incoming request

        Returns:
            Tuple of (key, role)
        """
        # Try to get identity from request state (set by auth middleware)
        identity = getattr(request.state, "identity", None)

        if identity:
            return identity.name, identity.role.value

        # Fall back to API key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Use hash of key as bucket key (don't store actual key)
            import hashlib

            key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            return f"key_{key_hash}", None

        # No auth - use client IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip_{client_ip}", None


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter(config: RateLimitConfig | None = None) -> RateLimiter:
    """Get the global rate limiter instance.

    Args:
        config: Optional config (creates new instance if provided)

    Returns:
        RateLimiter instance
    """
    global _rate_limiter

    if config is not None:
        _rate_limiter = RateLimiter(config)
        return _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter()

    return _rate_limiter


def rate_limit_dependency(
    rpm: int | None = None,
) -> Any:
    """Create a FastAPI dependency for rate limiting.

    This can be used as an alternative to middleware for
    more granular control.

    Args:
        rpm: Requests per minute (uses default if not specified)

    Returns:
        FastAPI dependency function
    """
    from fastapi import Depends

    from .auth import get_identity_context

    async def check_rate_limit(request: Request, identity=Depends(get_identity_context)):
        rate_limiter = get_rate_limiter()

        if not rate_limiter.config.enabled:
            return

        # Determine key
        if identity:
            key = identity.name
            role = identity.role.value
        else:
            client_ip = request.client.host if request.client else "unknown"
            key = f"ip_{client_ip}"
            role = None

        # Check rate limit
        allowed, headers = rate_limiter.check(key, role)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please retry later.",
                headers=headers,
            )

    return check_rate_limit


# Exports
__all__ = [
    "RateLimitConfig",
    "TokenBucket",
    "RateLimiter",
    "RateLimitMiddleware",
    "get_rate_limiter",
    "rate_limit_dependency",
]
