"""Google Docs plugin for Mother AI OS.

Provides Google Docs template management and document creation.
Uses the gcp-draft CLI for Google API integration.
"""

from __future__ import annotations

import asyncio
import re
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
    """Create the Google Docs plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="google-docs",
            version="1.0.0",
            description="Google Docs template management and document creation",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # List recent documents
            CapabilitySpec(
                name="list",
                description="List recent Google Docs documents created with this tool.",
                parameters=[
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum number of documents to return",
                        required=False,
                        default=10,
                    ),
                ],
            ),
            # Get document info
            CapabilitySpec(
                name="get",
                description="Get information about a specific document by URL or ID.",
                parameters=[
                    ParameterSpec(
                        name="doc_id",
                        type=ParameterType.STRING,
                        description="Document ID or full URL",
                        required=True,
                    ),
                ],
            ),
            # Send document
            CapabilitySpec(
                name="send",
                description="Send a document via email, fax, post, or beA.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="doc_id",
                        type=ParameterType.STRING,
                        description="Document ID or URL to send",
                        required=True,
                    ),
                    ParameterSpec(
                        name="via",
                        type=ParameterType.STRING,
                        description="Transmission channel: email, fax, post, bea",
                        required=True,
                    ),
                    ParameterSpec(
                        name="to",
                        type=ParameterType.STRING,
                        description="Recipient name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="address",
                        type=ParameterType.STRING,
                        description="Recipient address (email, fax number, postal address, or SAFE-ID)",
                        required=True,
                    ),
                ],
            ),
            # Status/help
            CapabilitySpec(
                name="status",
                description="Check Google Docs integration status.",
                parameters=[],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.google.docs",
                **{"class": "GoogleDocsPlugin"},
            ),
        ),
        permissions=[
            "network:https",
        ],
    )


class GoogleDocsPlugin(PluginBase):
    """Google Docs template management plugin."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Google Docs plugin."""
        super().__init__(_create_manifest(), config)

        # Find gcp-draft CLI
        self._gcp_draft_bin = self._find_gcp_draft()
        self._config = config or {}

    def _find_gcp_draft(self) -> str | None:
        """Find gcp-draft CLI binary."""
        locations = [
            Path.home() / ".local" / "bin" / "gcp-draft",
            shutil.which("gcp-draft"),
        ]

        for loc in locations:
            if loc and Path(str(loc)).exists():
                return str(loc)

        return None

    def _is_configured(self) -> bool:
        """Check if gcp-draft is configured."""
        return self._gcp_draft_bin is not None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a Google Docs capability."""
        handlers = {
            "list": self._list,
            "get": self._get,
            "send": self._send,
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
                "Google Docs integration not configured. Install gcp-draft CLI.",
                code="NOT_CONFIGURED",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"Google Docs operation failed: {e}",
                code="GDOCS_ERROR",
            )

    async def _run_gcp_draft(self, *args: str, timeout: int = 30) -> tuple[str, str, int]:
        """Run gcp-draft CLI command."""
        cmd = [self._gcp_draft_bin, *args]

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

    def _parse_document_list(self, output: str) -> list[dict[str, Any]]:
        """Parse document list output."""
        documents = []
        lines = output.strip().split("\n")

        current_title = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip header lines
            if line.startswith("===") or line.startswith("---"):
                continue

            # Check for URL
            if "docs.google.com" in line:
                # Extract document ID from URL
                doc_id_match = re.search(r"/d/([a-zA-Z0-9_-]+)", line)
                doc_id = doc_id_match.group(1) if doc_id_match else None

                documents.append({
                    "title": current_title or "Untitled",
                    "url": line,
                    "doc_id": doc_id,
                })
                current_title = None
            elif line and not line.lower().startswith(("recent", "documents")):
                # This is likely a title
                current_title = line

        return documents

    async def _list(self, limit: int = 10) -> PluginResult:
        """List recent documents."""
        stdout, stderr, code = await self._run_gcp_draft("list")

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="LIST_FAILED",
            )

        documents = self._parse_document_list(stdout)

        # Apply limit
        if limit and len(documents) > limit:
            documents = documents[:limit]

        return PluginResult.success_result(
            data={
                "documents": documents,
                "count": len(documents),
            },
            message=f"Found {len(documents)} recent document(s)",
        )

    async def _get(self, doc_id: str) -> PluginResult:
        """Get document information."""
        # First list all documents and find the matching one
        stdout, stderr, code = await self._run_gcp_draft("list")

        if code != 0:
            return PluginResult.error_result(
                stderr or stdout,
                code="GET_FAILED",
            )

        documents = self._parse_document_list(stdout)

        # Search for matching document
        for doc in documents:
            if doc.get("doc_id") == doc_id or doc_id in doc.get("url", ""):
                return PluginResult.success_result(
                    data=doc,
                    message=f"Document: {doc.get('title', 'Untitled')}",
                )

        return PluginResult.error_result(
            f"Document not found: {doc_id}",
            code="NOT_FOUND",
        )

    async def _send(
        self,
        doc_id: str,
        via: str,
        to: str,
        address: str,
    ) -> PluginResult:
        """Send a document."""
        # Validate channel
        valid_channels = ["email", "fax", "post", "bea"]
        if via.lower() not in valid_channels:
            return PluginResult.error_result(
                f"Invalid channel: {via}. Must be one of: {', '.join(valid_channels)}",
                code="INVALID_INPUT",
            )

        # The send command is interactive, so we need to use --non-interactive
        # or construct the full command
        stdout, stderr, code = await self._run_gcp_draft(
            "send",
            doc_id,
            "--via", via.lower(),
            "--to", to,
            "--address", address,
            "--no-confirm",
            timeout=60,
        )

        if code != 0:
            # Check if it's because the command doesn't support these flags
            if "unknown flag" in stderr.lower() or "error" in stderr.lower():
                return PluginResult.error_result(
                    "Document sending requires interactive mode. "
                    "Use the transmit plugin or run gcp-draft directly.",
                    code="INTERACTIVE_REQUIRED",
                )
            return PluginResult.error_result(
                stderr or stdout,
                code="SEND_FAILED",
            )

        return PluginResult.success_result(
            data={
                "doc_id": doc_id,
                "channel": via,
                "recipient": to,
            },
            message=f"Document sent via {via} to {to}",
        )

    async def _status(self) -> PluginResult:
        """Check integration status."""
        stdout, stderr, code = await self._run_gcp_draft("help")

        configured = code == 0 and "Usage" in stdout

        return PluginResult.success_result(
            data={
                "configured": configured,
                "gcp_draft_path": self._gcp_draft_bin,
                "help": stdout.strip() if configured else None,
            },
            message="Google Docs integration " + ("active" if configured else "not configured"),
        )


__all__ = ["GoogleDocsPlugin"]
