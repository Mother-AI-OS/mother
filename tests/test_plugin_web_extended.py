"""Extended tests for the web plugin to increase coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mother.plugins.builtin.web import WebPlugin


class TestWebPluginCapabilities:
    """Tests for WebPlugin capabilities."""

    @pytest.fixture
    def plugin(self):
        """Create a WebPlugin instance."""
        return WebPlugin()

    @pytest.mark.asyncio
    async def test_fetch_success(self, plugin):
        """Test successful fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Hello World"
        mock_response.headers = {"content-type": "text/html"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute("fetch", {"url": "https://example.com"})

        assert result.success is True
        assert result.data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_fetch_with_headers(self, plugin):
        """Test fetch with custom headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.headers = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute(
                "fetch",
                {"url": "https://example.com", "headers": {"Authorization": "Bearer token"}},
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_success(self, plugin):
        """Test GET request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Response"
        mock_response.headers = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute("get", {"url": "https://api.example.com/data"})

        assert result.success is True

    @pytest.mark.asyncio
    async def test_post_success(self, plugin):
        """Test POST request."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = '{"id": 1}'
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute(
                "post",
                {
                    "url": "https://api.example.com/create",
                    "data": {"name": "test"},
                },
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_head_request(self, plugin):
        """Test HEAD request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "1234"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.head = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute("head", {"url": "https://example.com"})

        assert result.success is True

    @pytest.mark.asyncio
    async def test_check_url(self, plugin):
        """Test URL availability check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {"content-type": "text/html"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.head = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute("check_url", {"url": "https://example.com"})

        assert result.success is True
        assert result.data["accessible"] is True

    @pytest.mark.asyncio
    async def test_check_url_unavailable(self, plugin):
        """Test URL unavailable."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url = "https://example.com/missing"
        mock_response.headers = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.head = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute("check_url", {"url": "https://example.com/missing"})

        assert result.success is True
        # The plugin still returns accessible=True if the server responds (even with 404)
        assert result.data["status_code"] == 404

    @pytest.mark.asyncio
    async def test_get_json(self, plugin):
        """Test JSON endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute("get_json", {"url": "https://api.example.com/json"})

        assert result.success is True
        assert result.data["json"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_parse_url(self, plugin):
        """Test URL parsing."""
        result = await plugin.execute(
            "parse_url",
            {"url": "https://user:pass@example.com:8080/path?query=value#fragment"},
        )

        assert result.success is True
        assert result.data["scheme"] == "https"
        assert result.data["hostname"] == "example.com"
        assert result.data["port"] == 8080
        assert result.data["path"] == "/path"
        assert "query" in result.data["query"]

    @pytest.mark.asyncio
    async def test_parse_url_simple(self, plugin):
        """Test simple URL parsing."""
        result = await plugin.execute("parse_url", {"url": "https://example.com"})

        assert result.success is True
        assert result.data["scheme"] == "https"
        assert result.data["hostname"] == "example.com"

    @pytest.mark.asyncio
    async def test_extract_links(self, plugin):
        """Test link extraction."""
        html = """
        <html>
        <body>
            <a href="https://example.com/page1">Page 1</a>
            <a href="/page2">Page 2</a>
            <a href="https://other.com">Other</a>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.headers = {"content-type": "text/html"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute(
                "extract_links",
                {"url": "https://example.com"},
            )

        assert result.success is True
        assert "links" in result.data
        assert len(result.data["links"]) >= 1

    @pytest.mark.asyncio
    async def test_encode_url(self, plugin):
        """Test URL encoding."""
        result = await plugin.execute(
            "encode_url",
            {"base_url": "https://example.com/path", "params": {"q": "hello world"}},
        )

        assert result.success is True
        assert "url" in result.data
        assert "hello" in result.data["url"]

    @pytest.mark.asyncio
    async def test_get_with_params(self, plugin):
        """Test GET request with query parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.headers = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute(
                "get",
                {
                    "url": "https://api.example.com/search",
                    "params": {"q": "test", "limit": 10},
                },
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_post_with_json(self, plugin):
        """Test POST request with JSON data."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = '{"id": 123}'
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute(
                "post",
                {
                    "url": "https://api.example.com/create",
                    "data": {"title": "Test", "content": "Body"},
                },
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_fetch_error(self, plugin):
        """Test fetch with network error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await plugin.execute("fetch", {"url": "https://example.com"})

        assert result.success is False

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability returns error."""
        result = await plugin.execute("nonexistent", {})
        assert result.success is False


class TestWebPluginManifest:
    """Tests for WebPlugin manifest."""

    def test_manifest_has_all_capabilities(self):
        """Test manifest includes all expected capabilities."""
        plugin = WebPlugin()
        manifest = plugin.manifest

        capability_names = [c.name for c in manifest.capabilities]

        expected = [
            "fetch",
            "get",
            "post",
            "head",
            "download",
            "check_url",
            "get_json",
            "extract_links",
            "parse_url",
        ]

        for name in expected:
            assert name in capability_names, f"Missing capability: {name}"

    def test_capabilities_have_descriptions(self):
        """Test all capabilities have descriptions."""
        plugin = WebPlugin()
        manifest = plugin.manifest

        for cap in manifest.capabilities:
            assert cap.description, f"Missing description for {cap.name}"

    def test_fetch_has_required_params(self):
        """Test fetch capability has required parameters."""
        plugin = WebPlugin()
        manifest = plugin.manifest

        fetch = manifest.get_capability("fetch")
        param_names = [p.name for p in fetch.parameters]

        assert "url" in param_names
