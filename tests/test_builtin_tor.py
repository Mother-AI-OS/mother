"""Tests for the built-in Tor plugin.

This module provides comprehensive test coverage for the TorPlugin,
including manifest validation, capability execution, and error handling.
All network operations are mocked to enable offline testing.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mother.plugins.base import ResultStatus
from mother.plugins.builtin.tor import TorPlugin, _create_manifest


class TestCreateManifest:
    """Tests for _create_manifest function."""

    def test_creates_valid_manifest(self):
        """Test that manifest is created correctly."""
        manifest = _create_manifest()

        assert manifest.plugin.name == "tor"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) > 0

    def test_manifest_has_expected_capabilities(self):
        """Test manifest has expected capabilities."""
        manifest = _create_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        assert "tor_check_status" in cap_names
        assert "tor_fetch" in cap_names
        assert "tor_browse" in cap_names
        assert "tor_start" in cap_names
        assert "tor_stop" in cap_names
        assert "tor_new_identity" in cap_names
        assert "tor_verified_sites" in cap_names
        assert "darknet_bbc" in cap_names
        assert "darknet_cia" in cap_names
        assert "darknet_ddg" in cap_names

    def test_manifest_has_correct_permissions(self):
        """Test manifest has correct permissions."""
        manifest = _create_manifest()

        assert "tor:read" in manifest.permissions
        assert "tor:write" in manifest.permissions
        assert "network:proxy" in manifest.permissions

    def test_high_risk_capabilities_require_confirmation(self):
        """Test that start/stop operations require confirmation."""
        manifest = _create_manifest()
        caps = {c.name: c for c in manifest.capabilities}

        assert caps["tor_start"].confirmation_required is True
        assert caps["tor_stop"].confirmation_required is True
        # Non-destructive operations should not require confirmation
        assert caps["tor_check_status"].confirmation_required is False
        assert caps["tor_verified_sites"].confirmation_required is False


class TestTorPluginInit:
    """Tests for TorPlugin initialization."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        plugin = TorPlugin()

        assert plugin._tor_proxy_host == "127.0.0.1"
        assert plugin._tor_proxy_port == 9050
        assert plugin._tor_control_port == 9051
        assert plugin._tor_dns_port == 9053
        assert plugin._browser == "w3m"

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = {
            "tor_proxy_host": "192.168.1.100",
            "tor_proxy_port": 9150,
            "tor_control_port": 9151,
            "tor_dns_port": 9153,
            "browser": "lynx",
        }
        plugin = TorPlugin(config=config)

        assert plugin._tor_proxy_host == "192.168.1.100"
        assert plugin._tor_proxy_port == 9150
        assert plugin._tor_control_port == 9151
        assert plugin._tor_dns_port == 9153
        assert plugin._browser == "lynx"

    def test_verified_sites_initialized(self):
        """Test that verified sites are initialized."""
        plugin = TorPlugin()

        assert "news" in plugin._verified_sites
        assert "search" in plugin._verified_sites
        assert len(plugin._verified_sites["news"]) > 0
        assert len(plugin._verified_sites["search"]) > 0


class TestTorPluginExecute:
    """Tests for execute method dispatch."""

    @pytest.mark.asyncio
    async def test_execute_unknown_capability(self):
        """Test execute with unknown capability."""
        plugin = TorPlugin()

        result = await plugin.execute("unknown_cap", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_execute_dispatches_to_handler(self):
        """Test that execute dispatches to correct handler."""
        plugin = TorPlugin()

        # Test verified_sites which is simple and doesn't need mocking
        result = await plugin.execute("tor_verified_sites", {})
        assert result.success is True
        assert "news" in result.data
        assert "search" in result.data


class TestTorCheckStatus:
    """Tests for tor_check_status capability."""

    @pytest.mark.asyncio
    async def test_status_inactive_when_proxy_unreachable(self):
        """Test status returns inactive when proxy port is closed."""
        plugin = TorPlugin()

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1  # Connection refused
            mock_socket.return_value = mock_sock

            result = await plugin.execute("tor_check_status", {})

            assert result.success is True
            assert result.data["status"] == "inactive"
            assert result.data["proxy_accessible"] is False

    @pytest.mark.asyncio
    async def test_status_active_with_tor_verification(self):
        """Test status returns active when Tor is working."""
        plugin = TorPlugin()

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0  # Connection succeeded
            mock_socket.return_value = mock_sock

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"IsTor": True, "IP": "1.2.3.4"}

                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                result = await plugin.execute("tor_check_status", {})

                assert result.success is True
                assert result.data["status"] == "active"
                assert result.data["proxy_accessible"] is True
                assert result.data["is_tor"] is True
                assert result.data["ip"] == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_status_active_but_verification_failed(self):
        """Test status when proxy works but verification API fails."""
        plugin = TorPlugin()

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.side_effect = Exception("Network error")
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                result = await plugin.execute("tor_check_status", {})

                assert result.success is True
                assert result.data["status"] == "active"
                assert result.data["is_tor"] == "unknown"
                assert "note" in result.data


class TestTorFetch:
    """Tests for tor_fetch capability."""

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """Test successful fetch through Tor."""
        plugin = TorPlugin()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.url = "https://example.com"
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "text/html"}
            mock_response.text = "<html>Hello World</html>"
            mock_response.content = b"<html>Hello World</html>"
            mock_response.encoding = "utf-8"

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await plugin.execute("tor_fetch", {"url": "https://example.com"})

            assert result.success is True
            assert result.data["status_code"] == 200
            assert "Hello World" in result.data["content"]

    @pytest.mark.asyncio
    async def test_fetch_adds_protocol_for_onion(self):
        """Test that http:// is added for .onion URLs."""
        plugin = TorPlugin()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.url = "http://example.onion"
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = "content"
            mock_response.content = b"content"
            mock_response.encoding = "utf-8"

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await plugin.execute("tor_fetch", {"url": "example.onion"})

            assert result.success is True
            # Verify that the URL was prefixed with http://
            mock_client.get.assert_called_once_with("http://example.onion")

    @pytest.mark.asyncio
    async def test_fetch_timeout(self):
        """Test fetch timeout handling."""
        plugin = TorPlugin()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await plugin.execute("tor_fetch", {"url": "https://slow.onion", "timeout": 30})

            assert result.success is False
            assert result.status == ResultStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_fetch_connection_error(self):
        """Test fetch connection error handling."""
        plugin = TorPlugin()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await plugin.execute("tor_fetch", {"url": "https://example.onion"})

            assert result.success is False
            assert result.error_code == "CONNECT_ERROR"

    @pytest.mark.asyncio
    async def test_fetch_unsupported_method(self):
        """Test fetch with unsupported HTTP method."""
        plugin = TorPlugin()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await plugin.execute("tor_fetch", {"url": "https://example.com", "method": "DELETE"})

            assert result.success is False
            assert result.error_code == "UNSUPPORTED_METHOD"

    @pytest.mark.asyncio
    async def test_fetch_post_method(self):
        """Test fetch with POST method."""
        plugin = TorPlugin()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.url = "https://example.com"
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = "OK"
            mock_response.content = b"OK"
            mock_response.encoding = "utf-8"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await plugin.execute("tor_fetch", {"url": "https://example.com", "method": "POST"})

            assert result.success is True
            mock_client.post.assert_called_once()


class TestTorBrowse:
    """Tests for tor_browse capability."""

    @pytest.mark.asyncio
    async def test_browse_success(self):
        """Test successful browse through torsocks + w3m."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Page content here", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("tor_browse", {"url": "http://example.onion"})

            assert result.success is True
            assert result.data["content"] == "Page content here"
            assert result.data["url"] == "http://example.onion"
            assert result.data["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_browse_adds_protocol(self):
        """Test that protocol is added to URL if missing."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"content", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("tor_browse", {"url": "example.onion"})

            assert result.success is True
            assert result.data["url"] == "http://example.onion"

    @pytest.mark.asyncio
    async def test_browse_failure(self):
        """Test browse failure handling."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error: connection refused")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await plugin.execute("tor_browse", {"url": "http://example.onion"})

            assert result.success is False
            assert result.error_code == "BROWSER_FAILED"

    @pytest.mark.asyncio
    async def test_browse_timeout(self):
        """Test browse timeout handling."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()

            async def slow_communicate():
                raise TimeoutError()

            mock_process.communicate = slow_communicate
            mock_process.kill = MagicMock()
            mock_process.wait = AsyncMock()
            mock_exec.return_value = mock_process

            result = await plugin.execute("tor_browse", {"url": "http://slow.onion"})

            assert result.success is False
            assert result.status == ResultStatus.TIMEOUT
            mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_browse_browser_not_found(self):
        """Test browse when w3m is not installed."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError("w3m not found")

            result = await plugin.execute("tor_browse", {"url": "http://example.onion"})

            assert result.success is False
            assert result.error_code == "BROWSER_NOT_FOUND"
            assert "w3m" in result.error_message


class TestTorStartStop:
    """Tests for tor_start and tor_stop capabilities."""

    @pytest.mark.asyncio
    async def test_tor_start_success(self):
        """Test successful Tor service start."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Started", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("tor_start", {})

            assert result.success is True
            assert result.data["action"] == "start"
            assert result.data["success"] is True
            mock_exec.assert_called_once_with(
                "systemctl", "start", "tor@default",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

    @pytest.mark.asyncio
    async def test_tor_start_failure(self):
        """Test Tor service start failure."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Failed to start")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await plugin.execute("tor_start", {})

            assert result.success is False
            assert result.error_code == "START_FAILED"

    @pytest.mark.asyncio
    async def test_tor_stop_success(self):
        """Test successful Tor service stop."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Stopped", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("tor_stop", {})

            assert result.success is True
            assert result.data["action"] == "stop"
            assert result.data["success"] is True

    @pytest.mark.asyncio
    async def test_tor_stop_failure(self):
        """Test Tor service stop failure."""
        plugin = TorPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Failed to stop")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await plugin.execute("tor_stop", {})

            assert result.success is False
            assert result.error_code == "STOP_FAILED"


class TestTorNewIdentity:
    """Tests for tor_new_identity capability."""

    @pytest.mark.asyncio
    async def test_new_identity_success(self):
        """Test successful new identity request."""
        plugin = TorPlugin()

        with patch("socket.socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"250 OK\r\n", b"250 OK\r\n"]
            mock_socket_class.return_value = mock_sock

            result = await plugin.execute("tor_new_identity", {})

            assert result.success is True
            assert result.data["action"] == "new_identity"
            assert result.data["success"] is True

    @pytest.mark.asyncio
    async def test_new_identity_auth_failed(self):
        """Test new identity when authentication fails."""
        plugin = TorPlugin()

        with patch("socket.socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_sock.recv.return_value = b"515 Authentication failed\r\n"
            mock_socket_class.return_value = mock_sock

            result = await plugin.execute("tor_new_identity", {})

            assert result.success is False
            assert result.error_code == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_new_identity_control_port_closed(self):
        """Test new identity when control port is not accessible."""
        plugin = TorPlugin()

        with patch("socket.socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_socket_class.return_value = mock_sock

            result = await plugin.execute("tor_new_identity", {})

            assert result.success is False
            assert result.error_code == "CONTROL_PORT_CLOSED"


class TestTorVerifiedSites:
    """Tests for tor_verified_sites capability."""

    @pytest.mark.asyncio
    async def test_verified_sites_returns_data(self):
        """Test that verified sites returns the site list."""
        plugin = TorPlugin()

        result = await plugin.execute("tor_verified_sites", {})

        assert result.success is True
        assert "news" in result.data
        assert "search" in result.data

        # Verify structure of news sites
        news_sites = result.data["news"]
        assert len(news_sites) > 0
        assert all("name" in site for site in news_sites)
        assert all("url" in site for site in news_sites)
        assert all("status" in site for site in news_sites)


class TestDarknetShortcuts:
    """Tests for darknet shortcut capabilities."""

    @pytest.mark.asyncio
    async def test_darknet_bbc(self):
        """Test darknet_bbc shortcut."""
        plugin = TorPlugin()

        with patch.object(plugin, "_tor_browse", new_callable=AsyncMock) as mock_browse:
            mock_browse.return_value = MagicMock(success=True)

            await plugin.execute("darknet_bbc", {})

            mock_browse.assert_called_once()
            call_args = mock_browse.call_args[0][0]
            assert "bbc" in call_args.lower()
            assert ".onion" in call_args

    @pytest.mark.asyncio
    async def test_darknet_cia(self):
        """Test darknet_cia shortcut."""
        plugin = TorPlugin()

        with patch.object(plugin, "_tor_browse", new_callable=AsyncMock) as mock_browse:
            mock_browse.return_value = MagicMock(success=True)

            await plugin.execute("darknet_cia", {})

            mock_browse.assert_called_once()
            call_args = mock_browse.call_args[0][0]
            assert "cia" in call_args.lower()
            assert ".onion" in call_args

    @pytest.mark.asyncio
    async def test_darknet_ddg(self):
        """Test darknet_ddg shortcut."""
        plugin = TorPlugin()

        with patch.object(plugin, "_tor_browse", new_callable=AsyncMock) as mock_browse:
            mock_browse.return_value = MagicMock(success=True)

            await plugin.execute("darknet_ddg", {})

            mock_browse.assert_called_once()
            call_args = mock_browse.call_args[0][0]
            assert "duckduckgo" in call_args.lower()
            assert ".onion" in call_args


class TestProxyTransport:
    """Tests for proxy transport configuration."""

    def test_get_proxy_transport(self):
        """Test proxy transport is correctly configured."""
        plugin = TorPlugin()

        transport = plugin._get_proxy_transport()

        # Verify it's an AsyncHTTPTransport with SOCKS proxy
        assert isinstance(transport, httpx.AsyncHTTPTransport)

    def test_get_proxy_transport_custom_host(self):
        """Test proxy transport with custom host."""
        config = {"tor_proxy_host": "192.168.1.100", "tor_proxy_port": 9150}
        plugin = TorPlugin(config=config)

        transport = plugin._get_proxy_transport()

        assert isinstance(transport, httpx.AsyncHTTPTransport)


class TestErrorHandling:
    """Tests for general error handling."""

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self):
        """Test that execute properly handles exceptions in handlers."""
        plugin = TorPlugin()

        with patch.object(plugin, "_tor_check_status", new_callable=AsyncMock) as mock_handler:
            mock_handler.side_effect = RuntimeError("Unexpected error")

            result = await plugin.execute("tor_check_status", {})

            assert result.success is False
            assert result.error_code == "TOR_ERROR"
            assert "Unexpected error" in result.error_message


class TestPolicyIntegration:
    """Tests for policy engine integration with Tor plugin."""

    def test_tor_capabilities_are_high_risk(self):
        """Test that tor capabilities are identified as high-risk by policy engine."""
        from mother.policy.engine import PolicyEngine

        # Create a policy engine in safe mode
        engine = PolicyEngine()

        # All tor_* capabilities should be high-risk
        assert engine._is_high_risk_capability("tor_fetch") is True
        assert engine._is_high_risk_capability("tor_browse") is True
        assert engine._is_high_risk_capability("tor_start") is True
        assert engine._is_high_risk_capability("tor_stop") is True
        assert engine._is_high_risk_capability("tor_new_identity") is True

    def test_safe_mode_blocks_tor_capabilities(self):
        """Test that safe mode blocks tor capabilities."""
        from mother.policy.engine import PolicyEngine
        from mother.policy.models import PolicyConfig

        # Create config with safe_mode=True (default)
        config = PolicyConfig(
            name="test",
            version="1.0",
            safe_mode=True,
        )
        engine = PolicyEngine(config=config)

        decision = engine.evaluate("tor_fetch", {"url": "http://example.onion"})

        assert decision.allowed is False
        assert "safe mode" in decision.reason.lower()
