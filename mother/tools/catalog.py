"""Tool catalog for discovering available tools.

This module loads the known tools catalog, which lists external tool repos
that are known to be compatible with Mother.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import CatalogError

logger = logging.getLogger("mother.tools.catalog")

# Default catalog location (in the Mother repo)
DEFAULT_CATALOG_PATH = Path(__file__).parent.parent.parent / "docs" / "ecosystem" / "tools-catalog.yaml"


@dataclass
class CatalogEntry:
    """Entry in the tool catalog."""

    name: str
    description: str
    repository: str  # Git URL
    version: str  # Latest known version
    risk_level: str  # low, medium, high, critical
    integration_types: list[str]  # python, cli, http, docker
    homepage: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    deprecation_notice: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "repository": self.repository,
            "version": self.version,
            "risk_level": self.risk_level,
            "integration_types": self.integration_types,
            "homepage": self.homepage,
            "author": self.author,
            "tags": self.tags,
            "deprecated": self.deprecated,
            "deprecation_notice": self.deprecation_notice,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CatalogEntry:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            repository=data["repository"],
            version=data.get("version", "latest"),
            risk_level=data.get("risk_level", "low"),
            integration_types=data.get("integration_types", ["cli"]),
            homepage=data.get("homepage"),
            author=data.get("author"),
            tags=data.get("tags", []),
            deprecated=data.get("deprecated", False),
            deprecation_notice=data.get("deprecation_notice"),
        )


class ToolCatalog:
    """Catalog of known tool repositories.

    The catalog is loaded from a YAML file that lists external tool repos
    that are known to be compatible with Mother.
    """

    def __init__(self, catalog_path: Path | None = None):
        """Initialize the catalog.

        Args:
            catalog_path: Path to catalog YAML file. Defaults to
                         docs/ecosystem/tools-catalog.yaml in the Mother repo.
        """
        self._catalog_path = catalog_path or DEFAULT_CATALOG_PATH
        self._entries: dict[str, CatalogEntry] = {}
        self._loaded = False
        self._version: str = "unknown"

    @property
    def catalog_path(self) -> Path:
        """Get the catalog file path."""
        return self._catalog_path

    def load(self) -> None:
        """Load the catalog from file."""
        if not self._catalog_path.exists():
            logger.warning(f"Catalog file not found: {self._catalog_path}")
            self._entries = {}
            self._loaded = True
            return

        try:
            with open(self._catalog_path) as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                raise CatalogError("Catalog must be a dictionary")

            self._version = data.get("version", "unknown")
            tools_data = data.get("tools", [])

            self._entries = {}
            for tool_data in tools_data:
                try:
                    entry = CatalogEntry.from_dict(tool_data)
                    self._entries[entry.name] = entry
                except Exception as e:
                    logger.warning(f"Failed to parse catalog entry: {e}")

            self._loaded = True
            logger.info(f"Loaded catalog with {len(self._entries)} tools")

        except yaml.YAMLError as e:
            raise CatalogError(f"Invalid YAML in catalog: {e}")
        except Exception as e:
            if isinstance(e, CatalogError):
                raise
            raise CatalogError(f"Failed to load catalog: {e}")

    def _ensure_loaded(self) -> None:
        """Ensure the catalog has been loaded."""
        if not self._loaded:
            self.load()

    def get_entry(self, name: str) -> CatalogEntry | None:
        """Get a catalog entry by name.

        Args:
            name: Tool name

        Returns:
            CatalogEntry or None if not found
        """
        self._ensure_loaded()
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a tool is in the catalog.

        Args:
            name: Tool name

        Returns:
            True if in catalog
        """
        self._ensure_loaded()
        return name in self._entries

    def list_entries(self) -> list[CatalogEntry]:
        """List all catalog entries.

        Returns:
            List of catalog entries
        """
        self._ensure_loaded()
        return list(self._entries.values())

    def search(self, query: str, include_deprecated: bool = False) -> list[CatalogEntry]:
        """Search the catalog by query.

        Searches tool names, descriptions, and tags.

        Args:
            query: Search query
            include_deprecated: Include deprecated tools

        Returns:
            List of matching entries, sorted by relevance
        """
        self._ensure_loaded()
        query_lower = query.lower()
        matches = []

        for entry in self._entries.values():
            if entry.deprecated and not include_deprecated:
                continue

            score = 0

            # Name match (highest priority)
            if query_lower in entry.name.lower():
                score += 10
                if entry.name.lower() == query_lower:
                    score += 5  # Exact match bonus

            # Description match
            if query_lower in entry.description.lower():
                score += 3

            # Tag match
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 2
                    break

            # Author match
            if entry.author and query_lower in entry.author.lower():
                score += 1

            if score > 0:
                matches.append((score, entry))

        # Sort by score descending
        matches.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in matches]

    def list_by_risk(self, risk_level: str) -> list[CatalogEntry]:
        """List tools by risk level.

        Args:
            risk_level: low, medium, high, or critical

        Returns:
            List of tools with the specified risk level
        """
        self._ensure_loaded()
        return [e for e in self._entries.values() if e.risk_level == risk_level.lower()]

    def list_by_integration(self, integration_type: str) -> list[CatalogEntry]:
        """List tools by integration type.

        Args:
            integration_type: python, cli, http, or docker

        Returns:
            List of tools supporting the integration type
        """
        self._ensure_loaded()
        return [e for e in self._entries.values() if integration_type.lower() in e.integration_types]

    def list_by_tag(self, tag: str) -> list[CatalogEntry]:
        """List tools by tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of tools with the tag
        """
        self._ensure_loaded()
        tag_lower = tag.lower()
        return [e for e in self._entries.values() if tag_lower in [t.lower() for t in e.tags]]

    def refresh(self) -> None:
        """Reload the catalog from file."""
        self._loaded = False
        self.load()
