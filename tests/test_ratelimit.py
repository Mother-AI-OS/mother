"""Tests for the rate limiting module."""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from mother.api.ratelimit import (
    RateLimitConfig,
    RateLimiter,
    RateLimitMiddleware,
    TokenBucket,
    get_rate_limiter,
    rate_limit_dependency,
)


class TestTokenBucket:
    """Tests for TokenBucket."""

    def test_initial_tokens(self):
        """Test bucket starts with full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.tokens == 10

    def test_consume_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(1) is True
        assert bucket.tokens == 9

    def test_consume_multiple(self):
        """Test consuming multiple tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(5) is True
        assert bucket.tokens == 5

    def test_consume_failure(self):
        """Test consumption fails when not enough tokens."""
        bucket = TokenBucket(capacity=1, refill_rate=0.1)
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False

    def test_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens per second
        bucket.tokens = 0
        bucket.last_refill = time.time()

        # Wait a bit and check refill
        time.sleep(0.2)
        bucket._refill()
        assert bucket.tokens >= 1.5  # Should have refilled some

    def test_refill_cap(self):
        """Test refill doesn't exceed capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=100.0)
        bucket.tokens = 5
        bucket.last_refill = time.time() - 10  # 10 seconds ago

        bucket._refill()
        assert bucket.tokens == 10  # Capped at capacity

    def test_get_retry_after(self):
        """Test retry-after calculation."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)  # 1 token per second
        bucket.tokens = 0
        bucket.last_refill = time.time()

        retry_after = bucket.get_retry_after()
        assert retry_after > 0
        assert retry_after <= 1.1  # Should need about 1 second

    def test_get_retry_after_has_tokens(self):
        """Test retry-after is 0 when tokens available."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.get_retry_after() == 0

    def test_get_remaining(self):
        """Test get remaining tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.consume(3)
        assert bucket.get_remaining() == 7


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.default_rpm == 60
        assert config.burst_multiplier == 1.5
        assert config.admin_rpm == 300
        assert config.operator_rpm == 120
        assert config.readonly_rpm == 60

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            enabled=False,
            default_rpm=100,
            admin_rpm=500,
        )
        assert config.enabled is False
        assert config.default_rpm == 100
        assert config.admin_rpm == 500

    def test_exempt_paths(self):
        """Test exempt paths configuration."""
        config = RateLimitConfig()
        assert "/health" in config.exempt_paths
        assert "/status" in config.exempt_paths


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_check_allowed(self):
        """Test request is allowed when under limit."""
        limiter = RateLimiter(RateLimitConfig(default_rpm=60))

        allowed, headers = limiter.check("test-key")
        assert allowed is True
        assert "X-RateLimit-Limit" in headers
        assert headers["X-RateLimit-Limit"] == "60"

    def test_check_blocked(self):
        """Test request is blocked when over limit."""
        # Use very low limit for testing
        config = RateLimitConfig(default_rpm=1, burst_multiplier=1.0)
        limiter = RateLimiter(config)

        # First request should be allowed
        allowed, _ = limiter.check("test-key")
        assert allowed is True

        # Second request should be blocked
        allowed, headers = limiter.check("test-key")
        assert allowed is False
        assert "Retry-After" in headers

    def test_role_based_limits(self):
        """Test different limits for different roles."""
        config = RateLimitConfig(
            admin_rpm=100,
            operator_rpm=50,
            readonly_rpm=25,
        )
        limiter = RateLimiter(config)

        _, admin_headers = limiter.check("admin-key", role="admin")
        assert admin_headers["X-RateLimit-Limit"] == "100"

        _, op_headers = limiter.check("op-key", role="operator")
        assert op_headers["X-RateLimit-Limit"] == "50"

        _, ro_headers = limiter.check("ro-key", role="readonly")
        assert ro_headers["X-RateLimit-Limit"] == "25"

    def test_disabled(self):
        """Test rate limiting can be disabled."""
        config = RateLimitConfig(enabled=False)
        limiter = RateLimiter(config)

        # Should always be allowed when disabled
        for _ in range(100):
            allowed, _ = limiter.check("test-key")
            assert allowed is True

    def test_different_keys_separate_buckets(self):
        """Test different keys have separate buckets."""
        config = RateLimitConfig(default_rpm=1, burst_multiplier=1.0)
        limiter = RateLimiter(config)

        # Exhaust first key
        allowed1, _ = limiter.check("key1")
        assert allowed1 is True
        allowed1, _ = limiter.check("key1")
        assert allowed1 is False

        # Second key should still be allowed
        allowed2, _ = limiter.check("key2")
        assert allowed2 is True

    def test_reset(self):
        """Test bucket reset."""
        config = RateLimitConfig(default_rpm=1, burst_multiplier=1.0)
        limiter = RateLimiter(config)

        # Exhaust the bucket
        limiter.check("test-key")
        allowed, _ = limiter.check("test-key")
        assert allowed is False

        # Reset and check again
        limiter.reset("test-key")
        allowed, _ = limiter.check("test-key")
        assert allowed is True

    def test_get_stats(self):
        """Test statistics retrieval."""
        limiter = RateLimiter()
        limiter.check("key1")
        limiter.check("key2")

        stats = limiter.get_stats()
        assert stats["enabled"] is True
        assert stats["active_buckets"] == 2
        assert "key1" in stats["buckets"]
        assert "key2" in stats["buckets"]


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app."""
        app = FastAPI()

        @app.get("/test")
        def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        def health_endpoint():
            return {"status": "healthy"}

        return app

    @pytest.fixture
    def limited_app(self, app):
        """Create app with rate limiting."""
        config = RateLimitConfig(default_rpm=2, burst_multiplier=1.0)
        rate_limiter = RateLimiter(config)
        app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
        return app

    def test_allows_requests_under_limit(self, limited_app):
        """Test requests under limit are allowed."""
        client = TestClient(limited_app)

        response = client.get("/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers

    def test_blocks_requests_over_limit(self, limited_app):
        """Test requests over limit are blocked."""
        client = TestClient(limited_app)

        # First two should pass
        response1 = client.get("/test")
        assert response1.status_code == 200

        response2 = client.get("/test")
        assert response2.status_code == 200

        # Third should be blocked
        response3 = client.get("/test")
        assert response3.status_code == 429
        assert "Retry-After" in response3.headers

    def test_exempt_paths(self, limited_app):
        """Test exempt paths bypass rate limiting."""
        client = TestClient(limited_app)

        # Exhaust rate limit
        client.get("/test")
        client.get("/test")

        # Health endpoint should still work (exempt)
        response = client.get("/health")
        assert response.status_code == 200

    def test_includes_rate_limit_headers(self, limited_app):
        """Test rate limit headers are included."""
        client = TestClient(limited_app)

        response = client.get("/test")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers


class TestGlobalRateLimiter:
    """Tests for global rate limiter functions."""

    def test_get_rate_limiter_singleton(self):
        """Test get_rate_limiter returns singleton."""
        # Reset the global instance
        import mother.api.ratelimit as rl

        rl._rate_limiter = None

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_get_rate_limiter_with_config(self):
        """Test get_rate_limiter with config creates new instance."""
        import mother.api.ratelimit as rl

        rl._rate_limiter = None

        config1 = RateLimitConfig(default_rpm=50)
        limiter1 = get_rate_limiter(config1)

        config2 = RateLimitConfig(default_rpm=100)
        limiter2 = get_rate_limiter(config2)

        assert limiter2.config.default_rpm == 100
        assert limiter1 is not limiter2


class TestRateLimitRecovery:
    """Tests for rate limit recovery over time."""

    def test_bucket_refills_over_time(self):
        """Test bucket refills tokens over time."""
        # Low capacity, fast refill for testing
        config = RateLimitConfig(default_rpm=60, burst_multiplier=1.0)  # 1/sec refill, 60 capacity
        limiter = RateLimiter(config)

        # Exhaust bucket completely
        for _ in range(60):
            limiter.check("test-key")

        # Should be blocked now
        allowed, _ = limiter.check("test-key")
        assert allowed is False

        # Wait for refill (at 1 token/sec, need ~1 second for 1 token)
        time.sleep(1.1)

        # Should be allowed again
        allowed, _ = limiter.check("test-key")
        assert allowed is True
