"""Taxlord plugin for Mother AI OS.

Provides German tax and document management capabilities:
- Document ingestion with OCR
- Semantic search over documents
- AI-powered Q&A
- Double-entry bookkeeping (SKR03/SKR04)
- ELSTER integration for tax filing
- Google Drive sync
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
    """Create the taxlord plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="taxlord",
            version="1.0.0",
            description="German tax and document management with ELSTER integration",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Document ingestion
            CapabilitySpec(
                name="ingest",
                description="Ingest documents (invoices, bank statements, receipts) into the system.",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to document or folder",
                        required=True,
                    ),
                    ParameterSpec(
                        name="ledger",
                        type=ParameterType.STRING,
                        description="Target ledger name",
                        required=False,
                    ),
                    ParameterSpec(
                        name="doc_type",
                        type=ParameterType.STRING,
                        description="Document type: invoice, receipt, bank_statement, contract, other",
                        required=False,
                    ),
                    ParameterSpec(
                        name="recursive",
                        type=ParameterType.BOOLEAN,
                        description="Process folders recursively",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Search documents
            CapabilitySpec(
                name="search",
                description="Search documents using semantic similarity.",
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
                    ParameterSpec(
                        name="doc_type",
                        type=ParameterType.STRING,
                        description="Filter by document type",
                        required=False,
                    ),
                ],
            ),
            # Ask AI about documents
            CapabilitySpec(
                name="ask",
                description="Ask a question about your documents using AI.",
                parameters=[
                    ParameterSpec(
                        name="question",
                        type=ParameterType.STRING,
                        description="Question to ask",
                        required=True,
                    ),
                    ParameterSpec(
                        name="doc_type",
                        type=ParameterType.STRING,
                        description="Limit to specific document type",
                        required=False,
                    ),
                ],
            ),
            # Show trial balance
            CapabilitySpec(
                name="balance",
                description="Show trial balance for the ledger.",
                parameters=[
                    ParameterSpec(
                        name="ledger",
                        type=ParameterType.STRING,
                        description="Ledger name (default: active ledger)",
                        required=False,
                    ),
                ],
            ),
            # Generate reports
            CapabilitySpec(
                name="report",
                description="Generate financial reports.",
                parameters=[
                    ParameterSpec(
                        name="report_type",
                        type=ParameterType.STRING,
                        description="Report type: income-statement, balance-sheet, tax-summary",
                        required=True,
                    ),
                    ParameterSpec(
                        name="year",
                        type=ParameterType.INTEGER,
                        description="Fiscal year",
                        required=False,
                    ),
                ],
            ),
            # List documents
            CapabilitySpec(
                name="documents",
                description="List all ingested documents.",
                parameters=[
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum documents to list (default: 50)",
                        required=False,
                        default=50,
                    ),
                    ParameterSpec(
                        name="doc_type",
                        type=ParameterType.STRING,
                        description="Filter by document type",
                        required=False,
                    ),
                ],
            ),
            # List ledgers
            CapabilitySpec(
                name="ledgers",
                description="List all ledgers or create a new one.",
                parameters=[
                    ParameterSpec(
                        name="create",
                        type=ParameterType.STRING,
                        description="Name of ledger to create (if creating)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="chart",
                        type=ParameterType.STRING,
                        description="Chart of accounts for new ledger: SKR03 or SKR04",
                        required=False,
                        default="SKR03",
                    ),
                ],
            ),
            # ELSTER status
            CapabilitySpec(
                name="elster_status",
                description="Check ELSTER integration status.",
                parameters=[],
            ),
            # VAT return
            CapabilitySpec(
                name="vat",
                description="Prepare VAT advance return (Umsatzsteuer-Voranmeldung).",
                parameters=[
                    ParameterSpec(
                        name="period",
                        type=ParameterType.STRING,
                        description="Period (e.g., 2024-Q1, 2024-01)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="preview",
                        type=ParameterType.BOOLEAN,
                        description="Preview without generating XML",
                        required=False,
                        default=True,
                    ),
                ],
            ),
            # Sync status
            CapabilitySpec(
                name="sync",
                description="Google Drive sync for documents.",
                parameters=[
                    ParameterSpec(
                        name="run",
                        type=ParameterType.BOOLEAN,
                        description="Run sync (default: just show status)",
                        required=False,
                        default=False,
                    ),
                    ParameterSpec(
                        name="sync_type",
                        type=ParameterType.STRING,
                        description="Sync type: private or business",
                        required=False,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.german.taxlord",
                **{"class": "TaxlordPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "filesystem:write",
            "network:https",
        ],
    )


class TaxlordPlugin(PluginBase):
    """German tax and document management plugin."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the taxlord plugin."""
        super().__init__(_create_manifest(), config)

        # Check for taxlord CLI
        self._taxlord_bin = self._find_taxlord()
        self._config = config or {}

    def _find_taxlord(self) -> str | None:
        """Find taxlord CLI binary."""
        # Check common locations
        locations = [
            Path.home() / ".local" / "bin" / "taxlord",
            Path.home() / "projects" / "taxlord" / ".venv" / "bin" / "taxlord",
            shutil.which("taxlord"),
        ]

        for loc in locations:
            if loc and Path(str(loc)).exists():
                return str(loc)

        return None

    def _is_configured(self) -> bool:
        """Check if taxlord is configured."""
        return self._taxlord_bin is not None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a taxlord capability."""
        handlers = {
            "ingest": self._ingest,
            "search": self._search,
            "ask": self._ask,
            "balance": self._balance,
            "report": self._report,
            "documents": self._documents,
            "ledgers": self._ledgers,
            "elster_status": self._elster_status,
            "vat": self._vat,
            "sync": self._sync,
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
                "Taxlord is not configured. Install taxlord CLI or set taxlord_path in config.",
                code="NOT_CONFIGURED",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"Taxlord operation failed: {e}",
                code="TAXLORD_ERROR",
            )

    async def _run_taxlord(self, *args: str) -> tuple[str, str, int]:
        """Run taxlord CLI command."""
        cmd = [self._taxlord_bin, *args]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )

    async def _ingest(
        self,
        path: str,
        ledger: str | None = None,
        doc_type: str | None = None,
        recursive: bool = False,
    ) -> PluginResult:
        """Ingest documents."""
        args = ["ingest", path]

        if ledger:
            args.extend(["--ledger", ledger])
        if doc_type:
            args.extend(["--type", doc_type])
        if recursive:
            args.append("--recursive")

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="INGEST_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Ingested documents from {path}",
        )

    async def _search(
        self,
        query: str,
        limit: int = 10,
        doc_type: str | None = None,
    ) -> PluginResult:
        """Search documents."""
        args = ["search", query, "--limit", str(limit)]

        if doc_type:
            args.extend(["--type", doc_type])

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="SEARCH_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Search results for: {query}",
        )

    async def _ask(
        self,
        question: str,
        doc_type: str | None = None,
    ) -> PluginResult:
        """Ask AI about documents."""
        args = ["ask", question]

        if doc_type:
            args.extend(["--type", doc_type])

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="ASK_FAILED",
            )

        return PluginResult.success_result(
            data={"answer": stdout.strip()},
            message="AI answer generated",
        )

    async def _balance(self, ledger: str | None = None) -> PluginResult:
        """Show trial balance."""
        args = ["balance"]

        if ledger:
            args.extend(["--ledger", ledger])

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="BALANCE_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Trial balance",
        )

    async def _report(
        self,
        report_type: str,
        year: int | None = None,
    ) -> PluginResult:
        """Generate financial report."""
        args = ["report", report_type]

        if year:
            args.extend(["--year", str(year)])

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="REPORT_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Generated {report_type} report",
        )

    async def _documents(
        self,
        limit: int = 50,
        doc_type: str | None = None,
    ) -> PluginResult:
        """List documents."""
        args = ["documents", "list", "--limit", str(limit)]

        if doc_type:
            args.extend(["--type", doc_type])

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="LIST_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Document list",
        )

    async def _ledgers(
        self,
        create: str | None = None,
        chart: str = "SKR03",
    ) -> PluginResult:
        """List or create ledgers."""
        if create:
            args = ["ledgers", "create", create, "--chart", chart]
        else:
            args = ["ledgers", "list"]

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="LEDGER_FAILED",
            )

        if create:
            return PluginResult.success_result(
                data={"output": stdout.strip()},
                message=f"Created ledger: {create}",
            )
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Ledger list",
        )

    async def _elster_status(self) -> PluginResult:
        """Check ELSTER status."""
        stdout, stderr, code = await self._run_taxlord("elster", "status")

        return PluginResult.success_result(
            data={"output": stdout.strip(), "configured": code == 0},
            message="ELSTER status",
        )

    async def _vat(
        self,
        period: str,
        preview: bool = True,
    ) -> PluginResult:
        """Prepare VAT return."""
        args = ["elster", "vat", period]

        if preview:
            args.append("--preview")

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="VAT_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"VAT return for {period}",
        )

    async def _sync(
        self,
        run: bool = False,
        sync_type: str | None = None,
    ) -> PluginResult:
        """Google Drive sync."""
        if run:
            args = ["sync", "run"]
            if sync_type:
                args.extend(["--type", sync_type])
        else:
            args = ["sync", "status"]

        stdout, stderr, code = await self._run_taxlord(*args)

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="SYNC_FAILED",
            )

        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Sync complete" if run else "Sync status",
        )


__all__ = ["TaxlordPlugin"]
