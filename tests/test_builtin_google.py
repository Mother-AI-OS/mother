"""Tests for the Google Docs plugin."""

import shutil
from pathlib import Path

import pytest

from mother.plugins.builtin.google import GoogleDocsPlugin


def gcp_draft_available() -> bool:
    """Check if gcp-draft CLI is available."""
    locations = [
        Path.home() / ".local" / "bin" / "gcp-draft",
        shutil.which("gcp-draft"),
    ]
    return any(loc and Path(str(loc)).exists() for loc in locations)


class TestGoogleDocsPlugin:
    """Tests for GoogleDocsPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance."""
        return GoogleDocsPlugin(config={})

    def test_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.manifest.plugin.name == "google-docs"
        assert plugin.manifest.plugin.version == "1.0.0"

    def test_capabilities(self, plugin):
        """Test plugin capabilities."""
        caps = plugin.get_capabilities()
        assert len(caps) == 4
        cap_names = [c.name for c in caps]
        assert "list" in cap_names
        assert "get" in cap_names
        assert "send" in cap_names
        assert "status" in cap_names

    def test_send_requires_confirmation(self, plugin):
        """Test that send capability requires confirmation."""
        caps = plugin.get_capabilities()
        send_cap = next(c for c in caps if c.name == "send")
        assert send_cap.confirmation_required is True

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability."""
        result = await plugin.execute("unknown", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    @pytest.mark.skipif(gcp_draft_available(), reason="gcp-draft CLI is installed")
    async def test_not_configured(self, plugin):
        """Test operations without gcp-draft CLI."""
        result = await plugin.execute("list", {"limit": 10})
        assert result.success is False
        assert result.error_code == "NOT_CONFIGURED"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not gcp_draft_available(), reason="gcp-draft CLI not installed")
    async def test_list_when_configured(self, plugin):
        """Test listing documents when gcp-draft is available."""
        result = await plugin.execute("list", {"limit": 5})
        assert result.success is True
        assert "documents" in result.data
        assert "count" in result.data

    @pytest.mark.asyncio
    @pytest.mark.skipif(not gcp_draft_available(), reason="gcp-draft CLI not installed")
    async def test_status_when_configured(self, plugin):
        """Test status when gcp-draft is available."""
        result = await plugin.execute("status", {})
        assert result.success is True
        assert "configured" in result.data
        assert "gcp_draft_path" in result.data

    @pytest.mark.asyncio
    @pytest.mark.skipif(not gcp_draft_available(), reason="gcp-draft CLI not installed")
    async def test_get_document_not_found(self, plugin):
        """Test getting a non-existent document."""
        result = await plugin.execute("get", {"doc_id": "nonexistent123"})
        # Should either succeed with empty or return not found
        if not result.success:
            assert result.error_code in ["NOT_FOUND", "GET_FAILED"]


class TestDocumentParsing:
    """Tests for document list parsing."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance."""
        return GoogleDocsPlugin(config={})

    def test_parse_empty_output(self, plugin):
        """Test parsing empty output."""
        result = plugin._parse_document_list("")
        assert result == []

    def test_parse_document_list(self, plugin):
        """Test parsing document list output."""
        output = """=== Recent Documents ===
Test Document
https://docs.google.com/document/d/abc123/edit
Another Doc
https://docs.google.com/document/d/xyz789/edit"""

        result = plugin._parse_document_list(output)
        assert len(result) == 2
        assert result[0]["title"] == "Test Document"
        assert result[0]["doc_id"] == "abc123"
        assert result[1]["title"] == "Another Doc"
        assert result[1]["doc_id"] == "xyz789"

    def test_parse_document_list_with_separators(self, plugin):
        """Test parsing with separator lines."""
        output = """=== Recent Documents ===
-------------------
My Document
https://docs.google.com/document/d/doc1/edit
---"""

        result = plugin._parse_document_list(output)
        assert len(result) == 1
        assert result[0]["title"] == "My Document"
        assert result[0]["doc_id"] == "doc1"

    def test_parse_document_extracts_id_from_url(self, plugin):
        """Test that document ID is extracted from URL."""
        output = """Doc Title
https://docs.google.com/document/d/1abcDEF_xyz-123/edit?usp=sharing"""

        result = plugin._parse_document_list(output)
        assert len(result) == 1
        assert result[0]["doc_id"] == "1abcDEF_xyz-123"


class TestSendValidation:
    """Tests for send parameter validation."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance."""
        return GoogleDocsPlugin(config={})

    @pytest.mark.asyncio
    @pytest.mark.skipif(not gcp_draft_available(), reason="gcp-draft CLI not installed")
    async def test_send_invalid_channel(self, plugin):
        """Test send with invalid channel."""
        result = await plugin.execute(
            "send",
            {
                "doc_id": "test123",
                "via": "invalid_channel",
                "to": "Test Recipient",
                "address": "test@example.com",
            },
        )
        assert result.success is False
        assert result.error_code == "INVALID_INPUT"


class TestPluginRegistration:
    """Test that plugin is properly registered."""

    def test_google_docs_in_registry(self):
        """Test GoogleDocsPlugin is in BUILTIN_PLUGINS."""
        from mother.plugins.builtin import BUILTIN_PLUGINS

        assert "google-docs" in BUILTIN_PLUGINS
        assert BUILTIN_PLUGINS["google-docs"] == GoogleDocsPlugin

    def test_get_builtin_plugin(self):
        """Test get_builtin_plugin function."""
        from mother.plugins.builtin import get_builtin_plugin

        assert get_builtin_plugin("google-docs") == GoogleDocsPlugin
