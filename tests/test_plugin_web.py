"""Tests for the builtin web plugin."""

import pytest

from mother.plugins.builtin.web import WebPlugin, _create_manifest


class TestWebManifest:
    """Tests for web plugin manifest."""

    def test_create_manifest(self) -> None:
        """Test manifest creation."""
        manifest = _create_manifest()
        assert manifest.plugin.name == "web"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) > 0

    def test_manifest_has_required_capabilities(self) -> None:
        """Test that required capabilities exist."""
        manifest = _create_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        assert "fetch" in cap_names
        assert "get" in cap_names

    def test_fetch_parameters(self) -> None:
        """Test that fetch has correct parameters."""
        manifest = _create_manifest()
        fetch_cap = manifest.get_capability("fetch")
        assert fetch_cap is not None

        param_names = [p.name for p in fetch_cap.parameters]
        assert "url" in param_names


class TestWebPlugin:
    """Tests for WebPlugin."""

    @pytest.fixture
    def plugin(self) -> WebPlugin:
        """Create a plugin instance for testing."""
        return WebPlugin()

    def test_plugin_creation(self, plugin: WebPlugin) -> None:
        """Test plugin creation."""
        assert plugin is not None
        assert plugin.manifest is not None
        assert plugin.manifest.plugin.name == "web"

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin: WebPlugin) -> None:
        """Test executing unknown capability."""
        result = await plugin.execute("unknown_capability", {})

        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_fetch_invalid_url(self, plugin: WebPlugin) -> None:
        """Test fetching with invalid URL."""
        result = await plugin.execute("fetch", {"url": "not-a-valid-url"})

        # Should fail due to invalid URL
        assert result.success is False

    @pytest.mark.asyncio
    async def test_fetch_nonexistent_host(self, plugin: WebPlugin) -> None:
        """Test fetching from non-existent host."""
        result = await plugin.execute(
            "fetch",
            {"url": "http://nonexistent-host-12345.invalid/"},
        )

        # Should fail due to connection error
        assert result.success is False
