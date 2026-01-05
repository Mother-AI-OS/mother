"""Tests for the built-in web plugin."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mother.plugins.builtin.web import (
    DEFAULT_USER_AGENT,
    MAX_RESPONSE_SIZE,
    WebPlugin,
    _create_manifest,
)


class TestCreateManifest:
    """Tests for _create_manifest function."""

    def test_creates_valid_manifest(self):
        """Test that manifest is created correctly."""
        manifest = _create_manifest()

        assert manifest.plugin.name == "web"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) > 0

    def test_manifest_has_expected_capabilities(self):
        """Test manifest has expected capabilities."""
        manifest = _create_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        assert "fetch" in cap_names
        assert "get" in cap_names
        assert "post" in cap_names
        assert "head" in cap_names
        assert "download" in cap_names
        assert "check_url" in cap_names
        assert "get_json" in cap_names
        assert "extract_links" in cap_names
        assert "parse_url" in cap_names
        assert "encode_url" in cap_names


class TestWebPluginInit:
    """Tests for WebPlugin initialization."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        plugin = WebPlugin()

        assert plugin._user_agent == DEFAULT_USER_AGENT
        assert plugin._max_response_size == MAX_RESPONSE_SIZE
        assert plugin._blocked_domains == []

    def test_init_with_custom_user_agent(self):
        """Test initialization with custom user agent."""
        config = {"user_agent": "Custom/1.0"}
        plugin = WebPlugin(config=config)

        assert plugin._user_agent == "Custom/1.0"

    def test_init_with_custom_max_response_size(self):
        """Test initialization with custom max response size."""
        config = {"max_response_size": 1024}
        plugin = WebPlugin(config=config)

        assert plugin._max_response_size == 1024

    def test_init_with_blocked_domains(self):
        """Test initialization with blocked domains."""
        config = {"blocked_domains": ["evil.com", "malware.org"]}
        plugin = WebPlugin(config=config)

        assert plugin._blocked_domains == ["evil.com", "malware.org"]


class TestWebPluginLifecycle:
    """Tests for WebPlugin lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        """Test initialize creates HTTP client."""
        plugin = WebPlugin()
        assert plugin._client is None

        await plugin.initialize()

        assert plugin._client is not None
        assert isinstance(plugin._client, httpx.AsyncClient)

        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_closes_client(self):
        """Test shutdown closes HTTP client."""
        plugin = WebPlugin()
        await plugin.initialize()

        await plugin.shutdown()

        assert plugin._client is None

    @pytest.mark.asyncio
    async def test_shutdown_when_no_client(self):
        """Test shutdown when no client exists."""
        plugin = WebPlugin()

        await plugin.shutdown()  # Should not raise

        assert plugin._client is None


class TestCheckUrlAllowed:
    """Tests for _check_url_allowed method."""

    def test_http_url_allowed(self):
        """Test HTTP URL is allowed."""
        plugin = WebPlugin()

        allowed, error = plugin._check_url_allowed("http://example.com")

        assert allowed is True
        assert error is None

    def test_https_url_allowed(self):
        """Test HTTPS URL is allowed."""
        plugin = WebPlugin()

        allowed, error = plugin._check_url_allowed("https://example.com")

        assert allowed is True
        assert error is None

    def test_url_without_scheme_rejected(self):
        """Test URL without scheme is rejected."""
        plugin = WebPlugin()

        allowed, error = plugin._check_url_allowed("example.com")

        assert allowed is False
        assert "scheme" in error.lower()

    def test_ftp_url_rejected(self):
        """Test FTP URL is rejected."""
        plugin = WebPlugin()

        allowed, error = plugin._check_url_allowed("ftp://files.example.com")

        assert allowed is False
        assert "http/https" in error.lower()

    def test_file_url_rejected(self):
        """Test file:// URL is rejected."""
        plugin = WebPlugin()

        allowed, error = plugin._check_url_allowed("file:///etc/passwd")

        assert allowed is False

    def test_blocked_domain_rejected(self):
        """Test blocked domain is rejected."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        allowed, error = plugin._check_url_allowed("https://evil.com/page")

        assert allowed is False
        assert "blocked" in error.lower()

    def test_blocked_subdomain_rejected(self):
        """Test subdomain of blocked domain is rejected."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        allowed, error = plugin._check_url_allowed("https://api.evil.com/page")

        assert allowed is False
        assert "blocked" in error.lower()

    def test_unrelated_domain_allowed(self):
        """Test unrelated domain is allowed."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        # "good.org" doesn't contain "evil.com"
        allowed, error = plugin._check_url_allowed("https://good.org/page")

        assert allowed is True


class TestExecute:
    """Tests for execute method."""

    @pytest.mark.asyncio
    async def test_execute_unknown_capability(self):
        """Test execute with unknown capability."""
        plugin = WebPlugin()

        result = await plugin.execute("unknown_cap", {})

        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_execute_timeout_error(self):
        """Test execute handles timeout error."""
        plugin = WebPlugin()
        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        result = await plugin.execute("fetch", {"url": "https://example.com"})

        assert result.success is False
        assert result.error_code == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_execute_connection_error(self):
        """Test execute handles connection error."""
        plugin = WebPlugin()
        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

        result = await plugin.execute("fetch", {"url": "https://example.com"})

        assert result.success is False
        assert result.error_code == "CONNECTION_ERROR"


class TestFetch:
    """Tests for fetch capability."""

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """Test successful fetch."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html>Hello</html>"

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("fetch", {"url": "https://example.com"})

        assert result.success is True
        assert result.data["status_code"] == 200
        assert result.data["content"] == "<html>Hello</html>"

    @pytest.mark.asyncio
    async def test_fetch_blocked_url(self):
        """Test fetch with blocked URL."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        result = await plugin.execute("fetch", {"url": "https://evil.com/page"})

        assert result.success is False
        assert result.error_code == "URL_NOT_ALLOWED"

    @pytest.mark.asyncio
    async def test_fetch_response_too_large_header(self):
        """Test fetch rejects response too large (from header)."""
        plugin = WebPlugin(config={"max_response_size": 100})

        mock_response = MagicMock()
        mock_response.url = "https://example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html", "content-length": "1000"}
        mock_response.text = "x" * 1000

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("fetch", {"url": "https://example.com"})

        assert result.success is False
        assert result.error_code == "RESPONSE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_fetch_content_truncated(self):
        """Test fetch truncates large content."""
        plugin = WebPlugin(config={"max_response_size": 50})

        mock_response = MagicMock()
        mock_response.url = "https://example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}  # No content-length
        mock_response.text = "x" * 100

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("fetch", {"url": "https://example.com"})

        assert result.success is True
        assert "truncated" in result.data["content"]

    @pytest.mark.asyncio
    async def test_fetch_with_custom_headers(self):
        """Test fetch with custom headers."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "Hello"

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute(
            "fetch",
            {"url": "https://example.com", "headers": {"Authorization": "Bearer token"}},
        )

        assert result.success is True
        plugin._client.get.assert_called_once()


class TestGet:
    """Tests for get capability."""

    @pytest.mark.asyncio
    async def test_get_success(self):
        """Test successful GET request."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://api.example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"data": "value"}'

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("get", {"url": "https://api.example.com"})

        assert result.success is True
        assert result.data["status_code"] == 200
        assert "headers" in result.data

    @pytest.mark.asyncio
    async def test_get_with_params(self):
        """Test GET request with query params."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://api.example.com?q=test"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"results": []}'

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute(
            "get",
            {"url": "https://api.example.com", "params": {"q": "test"}},
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_content_truncated(self):
        """Test GET truncates large content."""
        plugin = WebPlugin(config={"max_response_size": 50})

        mock_response = MagicMock()
        mock_response.url = "https://example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "x" * 100

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("get", {"url": "https://example.com"})

        assert result.success is True
        assert "truncated" in result.data["content"]


class TestPost:
    """Tests for post capability."""

    @pytest.mark.asyncio
    async def test_post_with_form_data(self):
        """Test POST with form data."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://api.example.com"
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"id": 1}'

        plugin._client = AsyncMock()
        plugin._client.post = AsyncMock(return_value=mock_response)

        result = await plugin.execute(
            "post",
            {"url": "https://api.example.com", "data": {"name": "test"}},
        )

        assert result.success is True
        assert result.data["status_code"] == 201

    @pytest.mark.asyncio
    async def test_post_with_json(self):
        """Test POST with JSON data."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://api.example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"success": true}'

        plugin._client = AsyncMock()
        plugin._client.post = AsyncMock(return_value=mock_response)

        result = await plugin.execute(
            "post",
            {"url": "https://api.example.com", "json": {"key": "value"}},
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_post_blocked_url(self):
        """Test POST with blocked URL."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        result = await plugin.execute(
            "post",
            {"url": "https://evil.com/submit", "data": {"x": "y"}},
        )

        assert result.success is False
        assert result.error_code == "URL_NOT_ALLOWED"

    @pytest.mark.asyncio
    async def test_post_content_truncated(self):
        """Test POST truncates large response."""
        plugin = WebPlugin(config={"max_response_size": 50})

        mock_response = MagicMock()
        mock_response.url = "https://example.com"
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "x" * 100

        plugin._client = AsyncMock()
        plugin._client.post = AsyncMock(return_value=mock_response)

        result = await plugin.execute("post", {"url": "https://example.com"})

        assert result.success is True
        assert "truncated" in result.data["content"]


class TestHead:
    """Tests for head capability."""

    @pytest.mark.asyncio
    async def test_head_success(self):
        """Test successful HEAD request."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://example.com"
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/html",
            "content-length": "12345",
        }

        plugin._client = AsyncMock()
        plugin._client.head = AsyncMock(return_value=mock_response)

        result = await plugin.execute("head", {"url": "https://example.com"})

        assert result.success is True
        assert result.data["status_code"] == 200
        assert result.data["content_length"] == "12345"

    @pytest.mark.asyncio
    async def test_head_blocked_url(self):
        """Test HEAD with blocked URL."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        result = await plugin.execute("head", {"url": "https://evil.com"})

        assert result.success is False
        assert result.error_code == "URL_NOT_ALLOWED"


class MockStreamResponse:
    """Mock async stream response for download tests."""

    def __init__(self, chunks, headers=None):
        self.headers = headers or {"content-type": "text/plain"}
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    async def aiter_bytes(self, chunk_size=8192):
        for chunk in self._chunks:
            yield chunk


class TestDownload:
    """Tests for download capability."""

    @pytest.mark.asyncio
    async def test_download_success(self, tmp_path):
        """Test successful file download."""
        plugin = WebPlugin()
        dest = tmp_path / "downloaded.txt"

        mock_response = MockStreamResponse([b"Hello, World!"])

        # Create a proper async context manager mock
        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        stream_cm.__aexit__ = AsyncMock(return_value=None)

        plugin._client = MagicMock()
        plugin._client.stream = MagicMock(return_value=stream_cm)

        result = await plugin.execute(
            "download",
            {"url": "https://example.com/file.txt", "destination": str(dest)},
        )

        assert result.success is True
        assert dest.exists()
        assert dest.read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_download_file_exists_no_overwrite(self, tmp_path):
        """Test download fails when file exists and overwrite is False."""
        plugin = WebPlugin()
        dest = tmp_path / "existing.txt"
        dest.write_text("existing content")

        result = await plugin.execute(
            "download",
            {"url": "https://example.com/file.txt", "destination": str(dest)},
        )

        assert result.success is False
        assert result.error_code == "FILE_EXISTS"

    @pytest.mark.asyncio
    async def test_download_file_exists_with_overwrite(self, tmp_path):
        """Test download succeeds with overwrite=True."""
        plugin = WebPlugin()
        dest = tmp_path / "existing.txt"
        dest.write_text("old content")

        mock_response = MockStreamResponse([b"new content"])

        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        stream_cm.__aexit__ = AsyncMock(return_value=None)

        plugin._client = MagicMock()
        plugin._client.stream = MagicMock(return_value=stream_cm)

        result = await plugin.execute(
            "download",
            {
                "url": "https://example.com/file.txt",
                "destination": str(dest),
                "overwrite": True,
            },
        )

        assert result.success is True
        assert dest.read_text() == "new content"

    @pytest.mark.asyncio
    async def test_download_too_large(self, tmp_path):
        """Test download fails when file is too large."""
        plugin = WebPlugin(config={"max_response_size": 10})
        dest = tmp_path / "large.txt"

        mock_response = MockStreamResponse([b"x" * 20])  # More than max_response_size

        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        stream_cm.__aexit__ = AsyncMock(return_value=None)

        plugin._client = MagicMock()
        plugin._client.stream = MagicMock(return_value=stream_cm)

        result = await plugin.execute(
            "download",
            {"url": "https://example.com/large.bin", "destination": str(dest)},
        )

        assert result.success is False
        assert result.error_code == "DOWNLOAD_TOO_LARGE"
        assert not dest.exists()  # File should be cleaned up

    @pytest.mark.asyncio
    async def test_download_blocked_url(self, tmp_path):
        """Test download with blocked URL."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})
        dest = tmp_path / "file.txt"

        result = await plugin.execute(
            "download",
            {"url": "https://evil.com/malware.exe", "destination": str(dest)},
        )

        assert result.success is False
        assert result.error_code == "URL_NOT_ALLOWED"

    @pytest.mark.asyncio
    async def test_download_creates_parent_directories(self, tmp_path):
        """Test download creates parent directories if needed."""
        plugin = WebPlugin()
        dest = tmp_path / "nested" / "dirs" / "file.txt"

        mock_response = MockStreamResponse([b"content"])

        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        stream_cm.__aexit__ = AsyncMock(return_value=None)

        plugin._client = MagicMock()
        plugin._client.stream = MagicMock(return_value=stream_cm)

        result = await plugin.execute(
            "download",
            {"url": "https://example.com/file.txt", "destination": str(dest)},
        )

        assert result.success is True
        assert dest.exists()


class TestCheckUrl:
    """Tests for check_url capability."""

    @pytest.mark.asyncio
    async def test_check_url_accessible(self):
        """Test check_url for accessible URL."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://example.com"
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/html",
            "content-length": "1234",
            "server": "nginx",
        }

        plugin._client = AsyncMock()
        plugin._client.head = AsyncMock(return_value=mock_response)

        result = await plugin.execute("check_url", {"url": "https://example.com"})

        assert result.success is True
        assert result.data["accessible"] is True
        assert result.data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_check_url_not_accessible(self):
        """Test check_url for inaccessible URL."""
        plugin = WebPlugin()

        plugin._client = AsyncMock()
        plugin._client.head = AsyncMock(side_effect=Exception("Connection refused"))

        result = await plugin.execute("check_url", {"url": "https://example.com"})

        assert result.success is True  # Method succeeded
        assert result.data["accessible"] is False
        assert "error" in result.data

    @pytest.mark.asyncio
    async def test_check_url_blocked(self):
        """Test check_url with blocked URL."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        result = await plugin.execute("check_url", {"url": "https://evil.com"})

        assert result.success is False
        assert result.error_code == "URL_NOT_ALLOWED"


class TestGetJson:
    """Tests for get_json capability."""

    @pytest.mark.asyncio
    async def test_get_json_success(self):
        """Test successful JSON fetch."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://api.example.com"
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"key": "value", "number": 42})

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("get_json", {"url": "https://api.example.com"})

        assert result.success is True
        assert result.data["json"]["key"] == "value"
        assert result.data["json"]["number"] == 42

    @pytest.mark.asyncio
    async def test_get_json_parse_error(self):
        """Test get_json with invalid JSON response."""
        plugin = WebPlugin()

        mock_response = MagicMock()
        mock_response.url = "https://api.example.com"
        mock_response.status_code = 200
        mock_response.json = MagicMock(side_effect=ValueError("Invalid JSON"))

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("get_json", {"url": "https://api.example.com"})

        assert result.success is False
        assert result.error_code == "JSON_PARSE_ERROR"

    @pytest.mark.asyncio
    async def test_get_json_blocked_url(self):
        """Test get_json with blocked URL."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        result = await plugin.execute("get_json", {"url": "https://evil.com/api"})

        assert result.success is False
        assert result.error_code == "URL_NOT_ALLOWED"


class TestExtractLinks:
    """Tests for extract_links capability."""

    @pytest.mark.asyncio
    async def test_extract_links_success(self):
        """Test successful link extraction."""
        plugin = WebPlugin()

        html = """
        <html>
        <a href="/page1">Page 1</a>
        <a href="https://example.com/page2">Page 2</a>
        <a href='page3.html'>Page 3</a>
        </html>
        """

        mock_response = MagicMock()
        mock_response.url = "https://example.com/"
        mock_response.text = html

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("extract_links", {"url": "https://example.com/"})

        assert result.success is True
        assert result.data["count"] == 3
        assert "https://example.com/page1" in result.data["links"]
        assert "https://example.com/page2" in result.data["links"]
        assert "https://example.com/page3.html" in result.data["links"]

    @pytest.mark.asyncio
    async def test_extract_links_relative_urls(self):
        """Test link extraction with relative URLs disabled."""
        plugin = WebPlugin()

        html = '<html><a href="/page1">Link</a></html>'

        mock_response = MagicMock()
        mock_response.url = "https://example.com/"
        mock_response.text = html

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute(
            "extract_links",
            {"url": "https://example.com/", "absolute": False},
        )

        assert result.success is True
        assert "/page1" in result.data["links"]

    @pytest.mark.asyncio
    async def test_extract_links_with_filter(self):
        """Test link extraction with filter pattern."""
        plugin = WebPlugin()

        html = """
        <html>
        <a href="page.html">HTML</a>
        <a href="doc.pdf">PDF</a>
        <a href="image.png">PNG</a>
        <a href="other.pdf">PDF 2</a>
        </html>
        """

        mock_response = MagicMock()
        mock_response.url = "https://example.com/"
        mock_response.text = html

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute(
            "extract_links",
            {"url": "https://example.com/", "filter_pattern": r"\.pdf$"},
        )

        assert result.success is True
        assert result.data["count"] == 2
        for link in result.data["links"]:
            assert link.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_extract_links_invalid_filter(self):
        """Test link extraction with invalid filter pattern."""
        plugin = WebPlugin()

        html = '<html><a href="page.html">Link</a></html>'

        mock_response = MagicMock()
        mock_response.url = "https://example.com/"
        mock_response.text = html

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute(
            "extract_links",
            {"url": "https://example.com/", "filter_pattern": "[invalid(regex"},
        )

        assert result.success is False
        assert result.error_code == "INVALID_PATTERN"

    @pytest.mark.asyncio
    async def test_extract_links_removes_duplicates(self):
        """Test link extraction removes duplicate links."""
        plugin = WebPlugin()

        html = """
        <html>
        <a href="/page">Link 1</a>
        <a href="/page">Link 2</a>
        <a href="/page">Link 3</a>
        </html>
        """

        mock_response = MagicMock()
        mock_response.url = "https://example.com/"
        mock_response.text = html

        plugin._client = AsyncMock()
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.execute("extract_links", {"url": "https://example.com/"})

        assert result.success is True
        assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_extract_links_blocked_url(self):
        """Test extract_links with blocked URL."""
        plugin = WebPlugin(config={"blocked_domains": ["evil.com"]})

        result = await plugin.execute("extract_links", {"url": "https://evil.com/"})

        assert result.success is False
        assert result.error_code == "URL_NOT_ALLOWED"


class TestParseUrl:
    """Tests for parse_url capability."""

    @pytest.mark.asyncio
    async def test_parse_url_success(self):
        """Test successful URL parsing."""
        plugin = WebPlugin()

        result = await plugin.execute(
            "parse_url",
            {"url": "https://user:pass@example.com:8080/path?q=test#section"},
        )

        assert result.success is True
        assert result.data["scheme"] == "https"
        assert result.data["hostname"] == "example.com"
        assert result.data["port"] == 8080
        assert result.data["path"] == "/path"
        assert result.data["query"] == "q=test"
        assert result.data["fragment"] == "section"
        assert result.data["username"] == "user"
        assert result.data["password"] == "***"  # Masked

    @pytest.mark.asyncio
    async def test_parse_url_simple(self):
        """Test parsing simple URL."""
        plugin = WebPlugin()

        result = await plugin.execute(
            "parse_url",
            {"url": "https://example.com"},
        )

        assert result.success is True
        assert result.data["scheme"] == "https"
        assert result.data["hostname"] == "example.com"
        assert result.data["port"] is None
        assert result.data["path"] == ""

    @pytest.mark.asyncio
    async def test_parse_url_error(self):
        """Test parse_url with invalid URL that causes exception."""
        plugin = WebPlugin()

        # urlparse is very permissive, but we can test the error path
        with patch("mother.plugins.builtin.web.urlparse", side_effect=Exception("parse error")):
            result = await plugin.execute("parse_url", {"url": "invalid"})

        assert result.success is False
        assert result.error_code == "PARSE_ERROR"


class TestEncodeUrl:
    """Tests for encode_url capability."""

    @pytest.mark.asyncio
    async def test_encode_url_with_params(self):
        """Test encoding URL with parameters."""
        plugin = WebPlugin()

        result = await plugin.execute(
            "encode_url",
            {"base_url": "https://example.com/search", "params": {"q": "hello world"}},
        )

        assert result.success is True
        assert "q=hello" in result.data["url"]
        assert "world" in result.data["url"] or "%20" in result.data["url"]

    @pytest.mark.asyncio
    async def test_encode_url_without_params(self):
        """Test encoding URL without parameters."""
        plugin = WebPlugin()

        result = await plugin.execute(
            "encode_url",
            {"base_url": "https://example.com/page"},
        )

        assert result.success is True
        assert result.data["url"] == "https://example.com/page"

    @pytest.mark.asyncio
    async def test_encode_url_error(self):
        """Test encode_url with invalid base URL."""
        plugin = WebPlugin()

        # Force an error by mocking httpx.URL
        with patch("mother.plugins.builtin.web.httpx.URL", side_effect=Exception("invalid URL")):
            result = await plugin.execute(
                "encode_url",
                {"base_url": "not-a-url", "params": {"x": "y"}},
            )

        assert result.success is False
        assert result.error_code == "ENCODE_ERROR"


class TestGetClient:
    """Tests for _get_client method."""

    @pytest.mark.asyncio
    async def test_get_client_creates_if_not_exists(self):
        """Test _get_client creates client if not initialized."""
        plugin = WebPlugin()
        assert plugin._client is None

        client = await plugin._get_client()

        assert client is not None
        assert plugin._client is not None

        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_get_client_returns_existing(self):
        """Test _get_client returns existing client."""
        plugin = WebPlugin()
        await plugin.initialize()
        original_client = plugin._client

        client = await plugin._get_client()

        assert client is original_client

        await plugin.shutdown()
