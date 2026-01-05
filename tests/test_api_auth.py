"""Tests for the API authentication module."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from mother.api.auth import optional_api_key, verify_api_key


class TestVerifyApiKey:
    """Tests for verify_api_key function."""

    @pytest.mark.asyncio
    async def test_no_api_key_configured_allows_all(self):
        """Test that requests are allowed when no API key is configured."""
        mock_settings = MagicMock()
        mock_settings.api_key = None

        with patch("mother.api.auth.get_settings", return_value=mock_settings):
            result = await verify_api_key(api_key=None)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_api_key_configured_with_key_provided(self):
        """Test that requests with key are allowed when no API key is configured."""
        mock_settings = MagicMock()
        mock_settings.api_key = None

        with patch("mother.api.auth.get_settings", return_value=mock_settings):
            result = await verify_api_key(api_key="some-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_auth_required_no_key_provided_raises_401(self):
        """Test that 401 is raised when auth required but no key provided."""
        mock_settings = MagicMock()
        mock_settings.api_key = "secret-key"
        mock_settings.require_auth = True

        with patch("mother.api.auth.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(api_key=None)

        assert exc_info.value.status_code == 401
        assert "API key required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_403(self):
        """Test that 403 is raised for invalid API key."""
        mock_settings = MagicMock()
        mock_settings.api_key = "correct-key"
        mock_settings.require_auth = True

        with patch("mother.api.auth.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(api_key="wrong-key")

        assert exc_info.value.status_code == 403
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_api_key_returns_key(self):
        """Test that valid API key is returned."""
        mock_settings = MagicMock()
        mock_settings.api_key = "correct-key"
        mock_settings.require_auth = True

        with patch("mother.api.auth.get_settings", return_value=mock_settings):
            result = await verify_api_key(api_key="correct-key")

        assert result == "correct-key"

    @pytest.mark.asyncio
    async def test_auth_not_required_no_key_allowed(self):
        """Test that requests without key are allowed when auth not required."""
        mock_settings = MagicMock()
        mock_settings.api_key = "configured-key"
        mock_settings.require_auth = False

        with patch("mother.api.auth.get_settings", return_value=mock_settings):
            result = await verify_api_key(api_key=None)

        assert result is None

    @pytest.mark.asyncio
    async def test_auth_not_required_wrong_key_raises_403(self):
        """Test that wrong key still raises 403 even when auth not required."""
        mock_settings = MagicMock()
        mock_settings.api_key = "configured-key"
        mock_settings.require_auth = False

        with patch("mother.api.auth.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(api_key="wrong-key")

        assert exc_info.value.status_code == 403


class TestOptionalApiKey:
    """Tests for optional_api_key function."""

    def test_returns_provided_key(self):
        """Test that provided key is returned."""
        result = optional_api_key(api_key="test-key")
        assert result == "test-key"

    def test_returns_none_when_no_key(self):
        """Test that None is returned when no key provided."""
        result = optional_api_key(api_key=None)
        assert result is None
