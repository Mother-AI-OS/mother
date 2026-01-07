"""Leads plugin for Mother AI OS.

Provides lead generation capabilities:
- German public tender discovery
- Upwork job discovery
- AI-powered lead analysis
- Lead scoring and filtering
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ...base import PluginBase, PluginResult
from ...manifest import (
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
    """Create the leads plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="leads",
            version="1.0.0",
            description="Lead generation from German tenders and Upwork",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Fetch leads
            CapabilitySpec(
                name="fetch",
                description="Fetch fresh leads from configured sources (German tenders, Upwork).",
                parameters=[
                    ParameterSpec(
                        name="source",
                        type=ParameterType.STRING,
                        description="Source to fetch: all, tenders, upwork (default: all)",
                        required=False,
                        default="all",
                    ),
                    ParameterSpec(
                        name="days",
                        type=ParameterType.INTEGER,
                        description="Fetch leads from last N days (default: 1)",
                        required=False,
                        default=1,
                    ),
                    ParameterSpec(
                        name="filter",
                        type=ParameterType.STRING,
                        description="Filter leads by keyword",
                        required=False,
                    ),
                ],
            ),
            # List leads
            CapabilitySpec(
                name="list",
                description="List cached leads with optional filters.",
                parameters=[
                    ParameterSpec(
                        name="top",
                        type=ParameterType.INTEGER,
                        description="Number of leads to show (default: 20)",
                        required=False,
                        default=20,
                    ),
                    ParameterSpec(
                        name="filter",
                        type=ParameterType.STRING,
                        description="Filter by keyword (ai, ki, ml, or custom)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="min_score",
                        type=ParameterType.INTEGER,
                        description="Minimum score threshold",
                        required=False,
                    ),
                    ParameterSpec(
                        name="source",
                        type=ParameterType.STRING,
                        description="Filter by source: all, tenders, upwork",
                        required=False,
                        default="all",
                    ),
                ],
            ),
            # Show lead details
            CapabilitySpec(
                name="show",
                description="Show detailed information about a specific tender.",
                parameters=[
                    ParameterSpec(
                        name="identifier",
                        type=ParameterType.STRING,
                        description="Tender ID or URL",
                        required=True,
                    ),
                ],
            ),
            # Analyze tender
            CapabilitySpec(
                name="analyze",
                description="Analyze tender documents with AI (downloads and reviews PDFs).",
                parameters=[
                    ParameterSpec(
                        name="identifier",
                        type=ParameterType.STRING,
                        description="Tender ID to analyze",
                        required=True,
                    ),
                    ParameterSpec(
                        name="download_only",
                        type=ParameterType.BOOLEAN,
                        description="Only download documents, skip AI analysis",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Status
            CapabilitySpec(
                name="status",
                description="Show system status (cache, API configuration, cron jobs).",
                parameters=[],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.german.leads",
                **{"class": "LeadsPlugin"},
            ),
        ),
        permissions=[
            "network:https",
            "filesystem:read",
            "filesystem:write",
        ],
    )


class LeadsPlugin(PluginBase):
    """Lead generation plugin for German tenders and Upwork."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the leads plugin."""
        super().__init__(_create_manifest(), config)

        # Check for leads CLI
        self._leads_bin = self._find_leads()
        self._config = config or {}

    def _find_leads(self) -> str | None:
        """Find leads CLI binary."""
        locations = [
            Path.home() / ".local" / "bin" / "leads",
            shutil.which("leads"),
        ]

        for loc in locations:
            if loc and Path(str(loc)).exists():
                return str(loc)

        return None

    def _is_configured(self) -> bool:
        """Check if leads is configured."""
        return self._leads_bin is not None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a leads capability."""
        handlers = {
            "fetch": self._fetch,
            "list": self._list,
            "show": self._show,
            "analyze": self._analyze,
            "status": self._status,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        # Check configuration
        if not self._is_configured():
            return PluginResult.error_result(
                "Leads CLI is not configured. Install leads CLI or set leads_path in config.",
                code="NOT_CONFIGURED",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"Leads operation failed: {e}",
                code="LEADS_ERROR",
            )

    async def _run_leads(self, *args: str, timeout: int = 120) -> tuple[str, str, int]:
        """Run leads CLI command."""
        cmd = [self._leads_bin, *args]

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
        except asyncio.TimeoutError:
            return "", "Operation timed out", 1

    async def _fetch(
        self,
        source: str = "all",
        days: int = 1,
        filter: str | None = None,  # noqa: A002
    ) -> PluginResult:
        """Fetch fresh leads."""
        args = ["fetch", "--source", source, "--days", str(days)]

        if filter:
            args.extend(["--filter", filter])

        stdout, stderr, code = await self._run_leads(*args, timeout=180)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="FETCH_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Fetched leads from {source}",
        )

    async def _list(
        self,
        top: int = 20,
        filter: str | None = None,  # noqa: A002
        min_score: int | None = None,
        source: str = "all",
    ) -> PluginResult:
        """List cached leads."""
        args = ["list", "--top", str(top), "--source", source]

        if filter:
            args.extend(["--filter", filter])
        if min_score is not None:
            args.extend(["--min-score", str(min_score)])

        stdout, stderr, code = await self._run_leads(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="LIST_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Top {top} leads",
        )

    async def _show(self, identifier: str) -> PluginResult:
        """Show lead details."""
        stdout, stderr, code = await self._run_leads("show", identifier)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="SHOW_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Lead details: {identifier}",
        )

    async def _analyze(
        self,
        identifier: str,
        download_only: bool = False,
    ) -> PluginResult:
        """Analyze tender documents."""
        args = ["analyze", identifier]

        if download_only:
            args.append("--download-only")

        stdout, stderr, code = await self._run_leads(*args, timeout=300)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="ANALYZE_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Analyzed tender: {identifier}",
        )

    async def _status(self) -> PluginResult:
        """Show system status."""
        stdout, stderr, code = await self._run_leads("status")

        return PluginResult.success_result(
            data={"output": stdout.strip(), "configured": code == 0},
            message="Leads status",
        )


__all__ = ["LeadsPlugin"]
