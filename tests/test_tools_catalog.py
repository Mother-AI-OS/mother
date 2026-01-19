"""Tests for the tool catalog module."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest
import yaml

from mother.tools.catalog import CatalogEntry, ToolCatalog
from mother.tools.exceptions import CatalogError


class TestCatalogEntry:
    """Tests for CatalogEntry dataclass."""

    def test_from_dict_minimal(self):
        """Test creating entry from minimal dict."""
        data = {
            "name": "test-tool",
            "repository": "https://github.com/org/repo",
        }

        entry = CatalogEntry.from_dict(data)

        assert entry.name == "test-tool"
        assert entry.repository == "https://github.com/org/repo"
        assert entry.description == ""
        assert entry.version == "latest"
        assert entry.risk_level == "low"
        assert entry.integration_types == ["cli"]
        assert entry.tags == []
        assert entry.deprecated is False

    def test_from_dict_full(self):
        """Test creating entry from full dict."""
        data = {
            "name": "full-tool",
            "description": "A full tool",
            "repository": "https://github.com/org/full-tool",
            "version": "2.0.0",
            "risk_level": "high",
            "integration_types": ["python", "http"],
            "homepage": "https://example.com",
            "author": "Test Author",
            "tags": ["ai", "automation"],
            "deprecated": True,
            "deprecation_notice": "Use new-tool instead",
        }

        entry = CatalogEntry.from_dict(data)

        assert entry.name == "full-tool"
        assert entry.description == "A full tool"
        assert entry.version == "2.0.0"
        assert entry.risk_level == "high"
        assert entry.integration_types == ["python", "http"]
        assert entry.homepage == "https://example.com"
        assert entry.author == "Test Author"
        assert entry.tags == ["ai", "automation"]
        assert entry.deprecated is True
        assert entry.deprecation_notice == "Use new-tool instead"

    def test_to_dict(self):
        """Test serializing entry to dict."""
        entry = CatalogEntry(
            name="test-tool",
            description="Test",
            repository="https://github.com/org/repo",
            version="1.0.0",
            risk_level="low",
            integration_types=["cli"],
        )

        data = entry.to_dict()

        assert data["name"] == "test-tool"
        assert data["repository"] == "https://github.com/org/repo"
        assert data["version"] == "1.0.0"


class TestToolCatalog:
    """Tests for ToolCatalog class."""

    def test_load_real_catalog(self):
        """Test loading the real tools catalog."""
        # Use the default path
        catalog = ToolCatalog()
        catalog.load()

        entries = catalog.list_entries()
        assert len(entries) > 0

        # Check for known tools
        contentcraft = catalog.get_entry("contentcraft")
        assert contentcraft is not None
        assert contentcraft.name == "contentcraft"

    def test_load_custom_catalog(self):
        """Test loading a custom catalog file."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "version": "1.0",
                "tools": [
                    {
                        "name": "custom-tool",
                        "description": "A custom tool",
                        "repository": "https://github.com/org/custom",
                        "version": "1.0.0",
                    }
                ],
            }
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()

            entries = catalog.list_entries()
            assert len(entries) == 1
            assert entries[0].name == "custom-tool"

    def test_load_nonexistent(self):
        """Test loading when catalog file doesn't exist."""
        catalog = ToolCatalog(catalog_path=Path("/nonexistent/catalog.yaml"))
        catalog.load()

        assert catalog.list_entries() == []

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: [")
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))

            with pytest.raises(CatalogError) as exc_info:
                catalog.load()
            assert "Invalid YAML" in str(exc_info.value)

    def test_get_entry(self):
        """Test getting a specific entry."""
        catalog = ToolCatalog()
        catalog.load()

        # Get existing
        entry = catalog.get_entry("contentcraft")
        assert entry is not None
        assert entry.name == "contentcraft"

        # Get non-existing
        entry = catalog.get_entry("nonexistent-tool")
        assert entry is None

    def test_has_entry(self):
        """Test checking if entry exists."""
        catalog = ToolCatalog()
        catalog.load()

        assert catalog.has_entry("contentcraft") is True
        assert catalog.has_entry("nonexistent-tool") is False

    def test_search_by_name(self):
        """Test searching by name."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "version": "1.0",
                "tools": [
                    {"name": "email-tool", "description": "Email", "repository": "https://r1"},
                    {"name": "data-tool", "description": "Data processing", "repository": "https://r2"},
                    {"name": "email-sender", "description": "Sends emails", "repository": "https://r3"},
                ],
            }
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()

            results = catalog.search("email")
            assert len(results) == 2
            # Both email tools should be found
            names = [r.name for r in results]
            assert "email-tool" in names
            assert "email-sender" in names

    def test_search_by_description(self):
        """Test searching by description."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "version": "1.0",
                "tools": [
                    {"name": "tool-a", "description": "Processes documents", "repository": "https://r1"},
                    {"name": "tool-b", "description": "Sends emails", "repository": "https://r2"},
                ],
            }
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()

            results = catalog.search("documents")
            assert len(results) == 1
            assert results[0].name == "tool-a"

    def test_search_by_tag(self):
        """Test searching by tag."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "version": "1.0",
                "tools": [
                    {"name": "ai-tool", "description": "AI stuff", "repository": "https://r1", "tags": ["ai", "ml"]},
                    {"name": "other-tool", "description": "Other", "repository": "https://r2", "tags": ["utility"]},
                ],
            }
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()

            results = catalog.search("ai")
            assert len(results) >= 1
            assert any(r.name == "ai-tool" for r in results)

    def test_search_excludes_deprecated(self):
        """Test that search excludes deprecated by default."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "version": "1.0",
                "tools": [
                    {"name": "active-tool", "description": "Active", "repository": "https://r1"},
                    {"name": "old-tool", "description": "Active but old", "repository": "https://r2", "deprecated": True},
                ],
            }
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()

            # Without deprecated
            results = catalog.search("active")
            assert len(results) == 1
            assert results[0].name == "active-tool"

            # With deprecated
            results = catalog.search("active", include_deprecated=True)
            assert len(results) == 2

    def test_list_by_risk(self):
        """Test listing by risk level."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "version": "1.0",
                "tools": [
                    {"name": "low-risk", "repository": "https://r1", "risk_level": "low"},
                    {"name": "high-risk", "repository": "https://r2", "risk_level": "high"},
                    {"name": "another-low", "repository": "https://r3", "risk_level": "low"},
                ],
            }
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()

            low_risk = catalog.list_by_risk("low")
            assert len(low_risk) == 2

            high_risk = catalog.list_by_risk("high")
            assert len(high_risk) == 1
            assert high_risk[0].name == "high-risk"

    def test_list_by_integration(self):
        """Test listing by integration type."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "version": "1.0",
                "tools": [
                    {"name": "cli-tool", "repository": "https://r1", "integration_types": ["cli"]},
                    {"name": "python-tool", "repository": "https://r2", "integration_types": ["python", "cli"]},
                    {"name": "http-tool", "repository": "https://r3", "integration_types": ["http"]},
                ],
            }
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()

            cli_tools = catalog.list_by_integration("cli")
            assert len(cli_tools) == 2

            python_tools = catalog.list_by_integration("python")
            assert len(python_tools) == 1
            assert python_tools[0].name == "python-tool"

    def test_list_by_tag(self):
        """Test listing by tag."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            data = {
                "version": "1.0",
                "tools": [
                    {"name": "tool-a", "repository": "https://r1", "tags": ["ai", "ml"]},
                    {"name": "tool-b", "repository": "https://r2", "tags": ["ai"]},
                    {"name": "tool-c", "repository": "https://r3", "tags": ["utility"]},
                ],
            }
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()

            ai_tools = catalog.list_by_tag("ai")
            assert len(ai_tools) == 2

            ml_tools = catalog.list_by_tag("ml")
            assert len(ml_tools) == 1

    def test_refresh(self):
        """Test refreshing the catalog."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Initial content
            data = {"version": "1.0", "tools": [{"name": "tool-1", "repository": "https://r1"}]}
            yaml.dump(data, f)
            f.flush()

            catalog = ToolCatalog(catalog_path=Path(f.name))
            catalog.load()
            assert len(catalog.list_entries()) == 1

            # Update file
            data["tools"].append({"name": "tool-2", "repository": "https://r2"})
            with open(f.name, "w") as f2:
                yaml.dump(data, f2)

            # Refresh
            catalog.refresh()
            assert len(catalog.list_entries()) == 2
