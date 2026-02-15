"""MatterCraft plugin for Mother AI OS.

Provides legal matter management capabilities:
- Matter lifecycle (create, edit, archive, delete)
- Document ingestion and RAG query
- Entity extraction and timeline
- Tender import from LeadEngine
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..base import PluginBase, PluginResult
from ..manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)


def _create_manifest() -> PluginManifest:
    """Create the mattercraft plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="mattercraft",
            version="1.0.0",
            description="Legal matter management with knowledge graph RAG",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Create matter
            CapabilitySpec(
                name="create",
                description="Create a new legal matter.",
                parameters=[
                    ParameterSpec(
                        name="name",
                        type=ParameterType.STRING,
                        description="Matter name / title",
                        required=True,
                    ),
                    ParameterSpec(
                        name="client",
                        type=ParameterType.STRING,
                        description="Client name",
                        required=False,
                    ),
                    ParameterSpec(
                        name="description",
                        type=ParameterType.STRING,
                        description="Matter description",
                        required=False,
                    ),
                    ParameterSpec(
                        name="matter_type",
                        type=ParameterType.STRING,
                        description="Type of matter (e.g., litigation, advisory, corporate)",
                        required=False,
                    ),
                ],
            ),
            # List matters
            CapabilitySpec(
                name="list",
                description="List all matters with status and client info.",
                parameters=[
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="Filter by status: active, archived, all (default: active)",
                        required=False,
                        default="active",
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum matters to show",
                        required=False,
                    ),
                ],
            ),
            # Show matter details
            CapabilitySpec(
                name="show",
                description="Show full details for a matter including documents and entities.",
                parameters=[
                    ParameterSpec(
                        name="matter",
                        type=ParameterType.STRING,
                        description="Matter ID or name",
                        required=True,
                    ),
                ],
            ),
            # Search matters
            CapabilitySpec(
                name="search",
                description="Search across all matters by name, client, description, or content.",
                parameters=[
                    ParameterSpec(
                        name="query",
                        type=ParameterType.STRING,
                        description="Search query",
                        required=True,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum results (default: 10)",
                        required=False,
                        default=10,
                    ),
                ],
            ),
            # Edit matter
            CapabilitySpec(
                name="edit",
                description="Edit matter fields (name, client, description, status).",
                parameters=[
                    ParameterSpec(
                        name="matter",
                        type=ParameterType.STRING,
                        description="Matter ID or name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="name",
                        type=ParameterType.STRING,
                        description="New matter name",
                        required=False,
                    ),
                    ParameterSpec(
                        name="client",
                        type=ParameterType.STRING,
                        description="New client name",
                        required=False,
                    ),
                    ParameterSpec(
                        name="description",
                        type=ParameterType.STRING,
                        description="New description",
                        required=False,
                    ),
                ],
            ),
            # Archive matter
            CapabilitySpec(
                name="archive",
                description="Archive a matter (reversible, matter becomes inactive).",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="matter",
                        type=ParameterType.STRING,
                        description="Matter ID or name to archive",
                        required=True,
                    ),
                ],
            ),
            # Delete matter
            CapabilitySpec(
                name="delete",
                description="Permanently delete a matter and all associated data.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="matter",
                        type=ParameterType.STRING,
                        description="Matter ID or name to delete",
                        required=True,
                    ),
                ],
            ),
            # Ingest document
            CapabilitySpec(
                name="ingest",
                description="Ingest a document into a matter for RAG indexing.",
                parameters=[
                    ParameterSpec(
                        name="matter",
                        type=ParameterType.STRING,
                        description="Matter ID or name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to file or directory to ingest",
                        required=True,
                    ),
                    ParameterSpec(
                        name="recursive",
                        type=ParameterType.BOOLEAN,
                        description="Process directories recursively",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Query documents
            CapabilitySpec(
                name="query",
                description="Ask a question about a matter's documents using RAG.",
                parameters=[
                    ParameterSpec(
                        name="matter",
                        type=ParameterType.STRING,
                        description="Matter ID or name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="question",
                        type=ParameterType.STRING,
                        description="Question to ask about the documents",
                        required=True,
                    ),
                ],
            ),
            # List entities
            CapabilitySpec(
                name="entities",
                description="List extracted entities (people, organizations, dates) for a matter.",
                parameters=[
                    ParameterSpec(
                        name="matter",
                        type=ParameterType.STRING,
                        description="Matter ID or name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="entity_type",
                        type=ParameterType.STRING,
                        description="Filter by entity type (person, organization, date, location)",
                        required=False,
                    ),
                ],
            ),
            # Timeline
            CapabilitySpec(
                name="timeline",
                description="Show chronological timeline of events for a matter.",
                parameters=[
                    ParameterSpec(
                        name="matter",
                        type=ParameterType.STRING,
                        description="Matter ID or name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum events to show",
                        required=False,
                    ),
                ],
            ),
            # Tenders list
            CapabilitySpec(
                name="tenders_list",
                description="List tender suggestions from LeadEngine for potential matters.",
                parameters=[
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="Filter by status: pending, imported, dismissed (default: pending)",
                        required=False,
                        default="pending",
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum tenders to show",
                        required=False,
                    ),
                ],
            ),
            # Tenders import
            CapabilitySpec(
                name="tenders_import",
                description="Import a tender from LeadEngine as a new matter.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="tender_id",
                        type=ParameterType.STRING,
                        description="Tender ID to import",
                        required=True,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.mattercraft",
                **{"class": "MattercraftPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "filesystem:write",
            "network:https",
        ],
    )


class MattercraftPlugin(PluginBase):
    """Legal matter management plugin."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the mattercraft plugin."""
        super().__init__(_create_manifest(), config)
        self._bin = self._find_binary()
        self._config = config or {}

    def _find_binary(self) -> str | None:
        """Find mattercraft CLI binary."""
        locations = [
            Path.home() / ".local" / "bin" / "mattercraft",
            Path.home() / "projects" / "mattercraft" / ".venv" / "bin" / "mattercraft",
            shutil.which("mattercraft"),
        ]
        for loc in locations:
            if loc and Path(str(loc)).exists():
                return str(loc)
        return None

    def _is_configured(self) -> bool:
        """Check if mattercraft is configured."""
        return self._bin is not None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a mattercraft capability."""
        handlers = {
            "create": self._create,
            "list": self._list,
            "show": self._show,
            "search": self._search,
            "edit": self._edit,
            "archive": self._archive,
            "delete": self._delete,
            "ingest": self._ingest,
            "query": self._query,
            "entities": self._entities,
            "timeline": self._timeline,
            "tenders_list": self._tenders_list,
            "tenders_import": self._tenders_import,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        if not self._is_configured():
            return PluginResult.error_result(
                "MatterCraft CLI is not installed. Install mattercraft or set path in config.",
                code="NOT_CONFIGURED",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"MatterCraft operation failed: {e}",
                code="MATTERCRAFT_ERROR",
            )

    async def _run_cli(self, *args: str, timeout: int = 120) -> tuple[str, str, int]:
        """Run mattercraft CLI command."""
        cmd = [self._bin, *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            return (
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                proc.returncode or 0,
            )
        except TimeoutError:
            return "", "Operation timed out", 1

    async def _create(
        self,
        name: str,
        client: str | None = None,
        description: str | None = None,
        matter_type: str | None = None,
    ) -> PluginResult:
        """Create a new matter."""
        args = ["create", name]
        if client:
            args.extend(["--client", client])
        if description:
            args.extend(["--description", description])
        if matter_type:
            args.extend(["--type", matter_type])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="CREATE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Created matter: {name}",
        )

    async def _list(
        self,
        status: str = "active",
        limit: int | None = None,
    ) -> PluginResult:
        """List matters."""
        args = ["list", "--status", status]
        if limit is not None:
            args.extend(["--limit", str(limit)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Matter list",
        )

    async def _show(self, matter: str) -> PluginResult:
        """Show matter details."""
        stdout, stderr, code = await self._run_cli("show", matter)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SHOW_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Matter details: {matter}",
        )

    async def _search(
        self,
        query: str,
        limit: int = 10,
    ) -> PluginResult:
        """Search across matters."""
        args = ["search", query, "--limit", str(limit)]
        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SEARCH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Search results for: {query}",
        )

    async def _edit(
        self,
        matter: str,
        name: str | None = None,
        client: str | None = None,
        description: str | None = None,
    ) -> PluginResult:
        """Edit matter fields."""
        args = ["edit", matter]
        if name:
            args.extend(["--name", name])
        if client:
            args.extend(["--client", client])
        if description:
            args.extend(["--description", description])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="EDIT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Updated matter: {matter}",
        )

    async def _archive(self, matter: str) -> PluginResult:
        """Archive a matter."""
        stdout, stderr, code = await self._run_cli("archive", matter)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="ARCHIVE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Archived matter: {matter}",
        )

    async def _delete(self, matter: str) -> PluginResult:
        """Delete a matter permanently."""
        stdout, stderr, code = await self._run_cli("delete", matter, "--yes")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DELETE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Deleted matter: {matter}",
        )

    async def _ingest(
        self,
        matter: str,
        path: str,
        recursive: bool = False,
    ) -> PluginResult:
        """Ingest documents into a matter."""
        args = ["ingest", matter, path]
        if recursive:
            args.append("--recursive")

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="INGEST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Ingested documents into {matter}",
        )

    async def _query(self, matter: str, question: str) -> PluginResult:
        """RAG query on matter documents."""
        stdout, stderr, code = await self._run_cli(
            "query", matter, question, timeout=120
        )
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="QUERY_FAILED")
        return PluginResult.success_result(
            data={"answer": stdout.strip()},
            message="Query answered",
        )

    async def _entities(
        self,
        matter: str,
        entity_type: str | None = None,
    ) -> PluginResult:
        """List extracted entities."""
        args = ["entities", matter]
        if entity_type:
            args.extend(["--type", entity_type])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="ENTITIES_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Entities for {matter}",
        )

    async def _timeline(
        self,
        matter: str,
        limit: int | None = None,
    ) -> PluginResult:
        """Show matter timeline."""
        args = ["timeline", matter]
        if limit is not None:
            args.extend(["--limit", str(limit)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="TIMELINE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Timeline for {matter}",
        )

    async def _tenders_list(
        self,
        status: str = "pending",
        limit: int | None = None,
    ) -> PluginResult:
        """List tender suggestions."""
        args = ["tenders", "list", "--status", status]
        if limit is not None:
            args.extend(["--limit", str(limit)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="TENDERS_LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Tender suggestions",
        )

    async def _tenders_import(self, tender_id: str) -> PluginResult:
        """Import a tender as a matter."""
        stdout, stderr, code = await self._run_cli(
            "tenders", "import", tender_id
        )
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="TENDERS_IMPORT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Imported tender {tender_id} as matter",
        )


__all__ = ["MattercraftPlugin"]
