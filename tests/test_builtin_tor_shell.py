"""Tests for the built-in Tor shell wrapper plugin.

This module provides comprehensive test coverage for the TorShellPlugin,
including manifest validation, capability execution, and error handling.
All shell operations are mocked to enable offline testing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mother.plugins.base import ResultStatus
from mother.plugins.builtin.tor_shell import TorShellPlugin, _create_manifest


class TestCreateManifest:
    """Tests for _create_manifest function."""

    def test_creates_valid_manifest(self):
        """Test that manifest is created correctly."""
        manifest = _create_manifest()

        assert manifest.plugin.name == "tor-shell"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) > 0

    def test_manifest_has_expected_capabilities(self):
        """Test manifest has expected capabilities."""
        manifest = _create_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        assert "darknet_dw" in cap_names
        assert "darknet_voa" in cap_names
        assert "darknet_rferl" in cap_names
        assert "darknet_bellingcat" in cap_names
        assert "darknet_propublica" in cap_names
        assert "darknet_nyt" in cap_names
        assert "darknet_bookmarks" in cap_names
        assert "darknet_news" in cap_names

    def test_manifest_has_correct_permissions(self):
        """Test manifest has correct permissions."""
        manifest = _create_manifest()

        assert "shell:execute" in manifest.permissions
        assert "tor:read" in manifest.permissions

    def test_all_browse_capabilities_have_timeout(self):
        """Test that all browse capabilities have appropriate timeout."""
        manifest = _create_manifest()
        browse_caps = [
            c
            for c in manifest.capabilities
            if c.name.startswith("darknet_") and c.name not in ("darknet_bookmarks", "darknet_news")
        ]

        for cap in browse_caps:
            assert cap.timeout >= 60, f"{cap.name} should have timeout >= 60"


class TestTorShellPluginInit:
    """Tests for TorShellPlugin initialization."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        plugin = TorShellPlugin()

        assert plugin is not None
        assert plugin.manifest.plugin.name == "tor-shell"

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = {"custom_option": "value"}
        plugin = TorShellPlugin(config=config)

        assert plugin is not None

    def test_onion_sites_defined(self):
        """Test that onion sites are defined."""
        plugin = TorShellPlugin()

        assert "dw" in plugin._ONION_SITES
        assert "voa" in plugin._ONION_SITES
        assert "rferl" in plugin._ONION_SITES
        assert "bellingcat" in plugin._ONION_SITES
        assert "propub" in plugin._ONION_SITES
        assert "nyt" in plugin._ONION_SITES

        # Verify all URLs are .onion
        for key, url in plugin._ONION_SITES.items():
            assert ".onion" in url, f"{key} URL should contain .onion"


class TestTorShellPluginExecute:
    """Tests for execute method dispatch."""

    @pytest.mark.asyncio
    async def test_execute_unknown_capability(self):
        """Test execute with unknown capability."""
        plugin = TorShellPlugin()

        result = await plugin.execute("unknown_cap", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_execute_bookmarks_no_shell(self):
        """Test that bookmarks command works without shell calls."""
        plugin = TorShellPlugin()

        result = await plugin.execute("darknet_bookmarks", {})

        assert result.success is True
        assert "search_engines" in result.data
        assert "news_sites" in result.data

    @pytest.mark.asyncio
    async def test_execute_news_no_shell(self):
        """Test that news command works without shell calls."""
        plugin = TorShellPlugin()

        result = await plugin.execute("darknet_news", {})

        assert result.success is True
        assert "sites" in result.data
        assert len(result.data["sites"]) > 0


class TestDarknetBrowse:
    """Tests for _darknet_browse method."""

    @pytest.mark.asyncio
    async def test_browse_success(self):
        """Test successful browse through torsocks + w3m."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Deutsche Welle content", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_dw", {})

            assert result.success is True
            assert result.data["site"] == "Deutsche Welle"
            assert result.data["site_key"] == "dw"
            assert "content" in result.data
            assert result.data["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_browse_unknown_site(self):
        """Test browse with unknown site key."""
        plugin = TorShellPlugin()

        # Directly call _darknet_browse with unknown key
        result = await plugin._darknet_browse("nonexistent")

        assert result.success is False
        assert result.error_code == "UNKNOWN_SITE"

    @pytest.mark.asyncio
    async def test_browse_failure(self):
        """Test browse failure handling."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error: connection refused")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_voa", {})

            assert result.success is False
            assert result.error_code == "BROWSER_FAILED"

    @pytest.mark.asyncio
    async def test_browse_timeout(self):
        """Test browse timeout handling."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()

            async def slow_communicate():
                raise TimeoutError()

            mock_process.communicate = slow_communicate
            mock_process.kill = MagicMock()
            mock_process.wait = AsyncMock()
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_rferl", {})

            assert result.success is False
            assert result.status == ResultStatus.TIMEOUT
            mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_browse_browser_not_found(self):
        """Test browse when w3m is not installed."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError("w3m not found")

            result = await plugin.execute("darknet_bellingcat", {})

            assert result.success is False
            assert result.error_code == "BROWSER_NOT_FOUND"
            assert "w3m" in result.error_message


class TestDarknetSiteShortcuts:
    """Tests for individual darknet site shortcuts."""

    @pytest.mark.asyncio
    async def test_darknet_dw(self):
        """Test Deutsche Welle shortcut."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"DW content", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_dw", {})

            assert result.success is True
            assert result.data["site"] == "Deutsche Welle"
            # Verify correct URL was passed to browser
            call_args = mock_exec.call_args
            assert "dwnews" in str(call_args).lower() or "dw" in result.data["url"].lower()

    @pytest.mark.asyncio
    async def test_darknet_voa(self):
        """Test Voice of America shortcut."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"VOA content", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_voa", {})

            assert result.success is True
            assert result.data["site"] == "Voice of America"

    @pytest.mark.asyncio
    async def test_darknet_rferl(self):
        """Test Radio Free Europe shortcut."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"RFE/RL content", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_rferl", {})

            assert result.success is True
            assert "Radio Free Europe" in result.data["site"]

    @pytest.mark.asyncio
    async def test_darknet_bellingcat(self):
        """Test Bellingcat shortcut."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Bellingcat content", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_bellingcat", {})

            assert result.success is True
            assert result.data["site"] == "Bellingcat"

    @pytest.mark.asyncio
    async def test_darknet_propublica(self):
        """Test ProPublica shortcut."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"ProPublica content", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_propublica", {})

            assert result.success is True
            assert result.data["site"] == "ProPublica"

    @pytest.mark.asyncio
    async def test_darknet_nyt(self):
        """Test New York Times shortcut."""
        plugin = TorShellPlugin()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"NYT content", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await plugin.execute("darknet_nyt", {})

            assert result.success is True
            assert result.data["site"] == "The New York Times"


class TestDarknetBookmarks:
    """Tests for darknet_bookmarks capability."""

    @pytest.mark.asyncio
    async def test_bookmarks_structure(self):
        """Test that bookmarks returns proper structure."""
        plugin = TorShellPlugin()

        result = await plugin.execute("darknet_bookmarks", {})

        assert result.success is True
        assert "search_engines" in result.data
        assert "news_sites" in result.data

        # Check search engines structure
        for engine in result.data["search_engines"]:
            assert "name" in engine
            assert "command" in engine
            assert "onion" in engine

        # Check news sites structure
        for site in result.data["news_sites"]:
            assert "name" in site
            assert "command" in site
            assert "onion" in site

    @pytest.mark.asyncio
    async def test_bookmarks_has_raw_output(self):
        """Test that bookmarks includes formatted raw output."""
        plugin = TorShellPlugin()

        result = await plugin.execute("darknet_bookmarks", {})

        assert result.success is True
        assert result.raw_output is not None
        assert "Darknet Bookmarks" in result.raw_output
        assert "Search Engines" in result.raw_output
        assert "News Sites" in result.raw_output


class TestDarknetNews:
    """Tests for darknet_news capability."""

    @pytest.mark.asyncio
    async def test_news_structure(self):
        """Test that news returns proper structure."""
        plugin = TorShellPlugin()

        result = await plugin.execute("darknet_news", {})

        assert result.success is True
        assert "sites" in result.data

        # Check each site has required fields
        for site in result.data["sites"]:
            assert "name" in site
            assert "onion" in site
            assert "url" in site
            assert "category" in site
            assert "verified" in site
            assert site["verified"] is True

    @pytest.mark.asyncio
    async def test_news_includes_major_outlets(self):
        """Test that news includes expected major outlets."""
        plugin = TorShellPlugin()

        result = await plugin.execute("darknet_news", {})

        site_names = [s["name"] for s in result.data["sites"]]

        assert "BBC News" in site_names
        assert "Deutsche Welle" in site_names
        assert "The New York Times" in site_names
        assert "ProPublica" in site_names

    @pytest.mark.asyncio
    async def test_news_has_raw_output(self):
        """Test that news includes formatted raw output."""
        plugin = TorShellPlugin()

        result = await plugin.execute("darknet_news", {})

        assert result.success is True
        assert result.raw_output is not None
        assert "Verified News Onions" in result.raw_output


class TestErrorHandling:
    """Tests for general error handling."""

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self):
        """Test that execute properly handles exceptions in handlers."""
        plugin = TorShellPlugin()

        with patch.object(plugin, "_darknet_browse", new_callable=AsyncMock) as mock_handler:
            mock_handler.side_effect = RuntimeError("Unexpected error")

            result = await plugin.execute("darknet_dw", {})

            assert result.success is False
            assert result.error_code == "TOR_SHELL_ERROR"
            assert "Unexpected error" in result.error_message


class TestPolicyIntegration:
    """Tests for policy engine integration with Tor shell plugin."""

    def test_tor_shell_capabilities_are_high_risk(self):
        """Test that tor-shell capabilities are identified as high-risk."""
        from mother.policy.engine import PolicyEngine

        engine = PolicyEngine()

        # tor-shell uses the pattern "tor-shell_*" which matches tor_* pattern
        # Note: The plugin uses "tor-shell" as name, so capabilities are "tor-shell_darknet_dw"
        # But when registered, they become "tor-shell_darknet_dw"
        # The policy engine checks for "^tor_" and "^tor-shell_" patterns
        assert engine._is_high_risk_capability("tor-shell_darknet_dw") is True
        assert engine._is_high_risk_capability("tor-shell_darknet_nyt") is True

    def test_safe_mode_blocks_tor_shell_capabilities(self):
        """Test that safe mode blocks tor-shell capabilities."""
        from mother.policy.engine import PolicyEngine
        from mother.policy.models import PolicyConfig

        config = PolicyConfig(
            name="test",
            version="1.0",
            safe_mode=True,
        )
        engine = PolicyEngine(config=config)

        decision = engine.evaluate("tor-shell_darknet_bbc", {})

        assert decision.allowed is False
        assert "safe mode" in decision.reason.lower()


class TestOnionURLValidation:
    """Tests for onion URL handling."""

    def test_all_onion_urls_valid_format(self):
        """Test that all onion URLs have valid format."""
        plugin = TorShellPlugin()

        for key, url in plugin._ONION_SITES.items():
            assert url.startswith("https://") or url.startswith("http://"), f"{key}: URL should have protocol"
            assert ".onion" in url, f"{key}: URL should be .onion address"
            # Onion addresses are 56 chars (v3) or 16 chars (v2)
            # Extract onion address from URL
            import re

            match = re.search(r"([a-z2-7]{16,56})\.onion", url)
            assert match is not None, f"{key}: Could not extract onion address from {url}"

    def test_site_names_match_keys(self):
        """Test that site name mappings are consistent."""
        plugin = TorShellPlugin()

        # The _darknet_browse method uses these mappings
        site_names = {
            "dw": "Deutsche Welle",
            "voa": "Voice of America",
            "rferl": "Radio Free Europe/Radio Liberty",
            "bellingcat": "Bellingcat",
            "propub": "ProPublica",
            "nyt": "The New York Times",
        }

        for key in plugin._ONION_SITES:
            assert key in site_names, f"Missing site name mapping for {key}"
