"""Tests for the German legal plugins (taxlord and leads)."""

import shutil
from pathlib import Path

import pytest

from mother.plugins.builtin.german import LeadsPlugin, TaxlordPlugin


def taxlord_available() -> bool:
    """Check if taxlord CLI is available."""
    locations = [
        Path.home() / ".local" / "bin" / "taxlord",
        Path.home() / "projects" / "taxlord" / ".venv" / "bin" / "taxlord",
        shutil.which("taxlord"),
    ]
    return any(loc and Path(str(loc)).exists() for loc in locations)


def leads_available() -> bool:
    """Check if leads CLI is available."""
    locations = [
        Path.home() / ".local" / "bin" / "leads",
        shutil.which("leads"),
    ]
    return any(loc and Path(str(loc)).exists() for loc in locations)


class TestTaxlordPlugin:
    """Tests for TaxlordPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance."""
        return TaxlordPlugin(config={})

    def test_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.manifest.plugin.name == "taxlord"
        assert plugin.manifest.plugin.version == "1.0.0"

    def test_capabilities(self, plugin):
        """Test plugin capabilities."""
        caps = plugin.get_capabilities()
        assert len(caps) == 10
        cap_names = [c.name for c in caps]
        assert "ingest" in cap_names
        assert "search" in cap_names
        assert "ask" in cap_names
        assert "balance" in cap_names
        assert "report" in cap_names
        assert "documents" in cap_names
        assert "ledgers" in cap_names
        assert "elster_status" in cap_names
        assert "vat" in cap_names
        assert "sync" in cap_names

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability."""
        result = await plugin.execute("unknown", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    @pytest.mark.skipif(taxlord_available(), reason="Taxlord CLI is installed")
    async def test_not_configured(self, plugin):
        """Test operations without taxlord CLI."""
        result = await plugin.execute("search", {"query": "invoice"})
        assert result.success is False
        assert result.error_code == "NOT_CONFIGURED"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not taxlord_available(), reason="Taxlord CLI not installed")
    async def test_search_when_configured(self, plugin):
        """Test search when taxlord is available."""
        result = await plugin.execute("search", {"query": "test", "limit": 5})
        # Should succeed (even if no results)
        assert result.success is True
        assert "output" in result.data

    @pytest.mark.asyncio
    @pytest.mark.skipif(not taxlord_available(), reason="Taxlord CLI not installed")
    async def test_documents_when_configured(self, plugin):
        """Test listing documents when taxlord is available."""
        result = await plugin.execute("documents", {"limit": 5})
        assert result.success is True
        assert "output" in result.data

    @pytest.mark.asyncio
    @pytest.mark.skipif(not taxlord_available(), reason="Taxlord CLI not installed")
    async def test_ledgers_when_configured(self, plugin):
        """Test listing ledgers when taxlord is available."""
        result = await plugin.execute("ledgers", {})
        assert result.success is True
        assert "output" in result.data


class TestLeadsPlugin:
    """Tests for LeadsPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance."""
        return LeadsPlugin(config={})

    def test_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.manifest.plugin.name == "leads"
        assert plugin.manifest.plugin.version == "1.0.0"

    def test_capabilities(self, plugin):
        """Test plugin capabilities."""
        caps = plugin.get_capabilities()
        assert len(caps) == 5
        cap_names = [c.name for c in caps]
        assert "fetch" in cap_names
        assert "list" in cap_names
        assert "show" in cap_names
        assert "analyze" in cap_names
        assert "status" in cap_names

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability."""
        result = await plugin.execute("unknown", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    @pytest.mark.skipif(leads_available(), reason="Leads CLI is installed")
    async def test_not_configured(self, plugin):
        """Test operations without leads CLI."""
        result = await plugin.execute("list", {"top": 10})
        assert result.success is False
        assert result.error_code == "NOT_CONFIGURED"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not leads_available(), reason="Leads CLI not installed")
    async def test_list_when_configured(self, plugin):
        """Test listing leads when leads CLI is available."""
        result = await plugin.execute("list", {"top": 5})
        assert result.success is True
        assert "output" in result.data

    @pytest.mark.asyncio
    @pytest.mark.skipif(not leads_available(), reason="Leads CLI not installed")
    async def test_status_when_configured(self, plugin):
        """Test status when leads CLI is available."""
        result = await plugin.execute("status", {})
        assert result.success is True
        assert "output" in result.data
        assert "configured" in result.data


class TestPluginRegistration:
    """Test that plugins are properly registered."""

    def test_taxlord_in_registry(self):
        """Test TaxlordPlugin is in BUILTIN_PLUGINS."""
        from mother.plugins.builtin import BUILTIN_PLUGINS

        assert "taxlord" in BUILTIN_PLUGINS
        assert BUILTIN_PLUGINS["taxlord"] == TaxlordPlugin

    def test_leads_in_registry(self):
        """Test LeadsPlugin is in BUILTIN_PLUGINS."""
        from mother.plugins.builtin import BUILTIN_PLUGINS

        assert "leads" in BUILTIN_PLUGINS
        assert BUILTIN_PLUGINS["leads"] == LeadsPlugin

    def test_get_builtin_plugin(self):
        """Test get_builtin_plugin function."""
        from mother.plugins.builtin import get_builtin_plugin

        assert get_builtin_plugin("taxlord") == TaxlordPlugin
        assert get_builtin_plugin("leads") == LeadsPlugin
        assert get_builtin_plugin("nonexistent") is None
