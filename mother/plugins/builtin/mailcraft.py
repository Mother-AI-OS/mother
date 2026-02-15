"""MailCraft plugin for Mother AI OS.

Provides AI-powered email management capabilities:
- AI categorization and triage
- Spam/newsletter cleanup
- Semantic search
- Batch operations
- Rule learning from user behavior
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
    """Create the mailcraft plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="mailcraft",
            version="1.0.0",
            description="AI-powered email management with categorization, triage, and cleanup",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Fetch emails
            CapabilitySpec(
                name="fetch",
                description="Sync emails from IMAP servers into the local database.",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Email account to fetch (default: all accounts)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder to fetch (default: INBOX)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum emails to fetch",
                        required=False,
                    ),
                ],
            ),
            # List emails
            CapabilitySpec(
                name="list",
                description="List emails from the local database with optional filters.",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Filter by account",
                        required=False,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder to list (default: INBOX)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum emails to show (default: 20)",
                        required=False,
                        default=20,
                    ),
                    ParameterSpec(
                        name="unread",
                        type=ParameterType.BOOLEAN,
                        description="Show only unread emails",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Search emails
            CapabilitySpec(
                name="search",
                description="Full-text search across emails by subject or sender.",
                parameters=[
                    ParameterSpec(
                        name="query",
                        type=ParameterType.STRING,
                        description="Search query",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Filter by account",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum results (default: 20)",
                        required=False,
                        default=20,
                    ),
                ],
            ),
            # Read email
            CapabilitySpec(
                name="read",
                description="Read the full content of a single email message.",
                parameters=[
                    ParameterSpec(
                        name="message_id",
                        type=ParameterType.STRING,
                        description="Email message ID to read",
                        required=True,
                    ),
                ],
            ),
            # Send email
            CapabilitySpec(
                name="send",
                description="Send an email with optional attachments.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="to",
                        type=ParameterType.STRING,
                        description="Recipient email address",
                        required=True,
                    ),
                    ParameterSpec(
                        name="subject",
                        type=ParameterType.STRING,
                        description="Email subject",
                        required=True,
                    ),
                    ParameterSpec(
                        name="body",
                        type=ParameterType.STRING,
                        description="Email body text",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Sending account",
                        required=False,
                    ),
                    ParameterSpec(
                        name="attachments",
                        type=ParameterType.STRING,
                        description="Comma-separated file paths to attach",
                        required=False,
                    ),
                    ParameterSpec(
                        name="cc",
                        type=ParameterType.STRING,
                        description="CC recipients (comma-separated)",
                        required=False,
                    ),
                ],
            ),
            # AI categorize
            CapabilitySpec(
                name="categorize",
                description="Categorize emails using AI (spam, newsletter, client, legal, etc.).",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account to categorize",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum emails to categorize",
                        required=False,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder to categorize (default: INBOX)",
                        required=False,
                    ),
                ],
            ),
            # Cleanup
            CapabilitySpec(
                name="cleanup",
                description="Full AI cleanup: categorize all emails, then delete spam and newsletters.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account to clean up",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview deletions without executing",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Clean spam
            CapabilitySpec(
                name="clean_spam",
                description="Detect and remove spam/marketing emails using AI analysis.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account to clean",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview deletions without executing",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Batch delete
            CapabilitySpec(
                name="batch_delete",
                description="Bulk delete emails matching a sender pattern.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="pattern",
                        type=ParameterType.STRING,
                        description="Sender email or domain pattern to match",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account to delete from",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview deletions without executing",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Learn from trash
            CapabilitySpec(
                name="learn_from_trash",
                description="Analyze Trash folder to extract categorization rules from deletion patterns.",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account to analyze",
                        required=False,
                    ),
                    ParameterSpec(
                        name="min_count",
                        type=ParameterType.INTEGER,
                        description="Minimum occurrences to create a rule (default: 3)",
                        required=False,
                        default=3,
                    ),
                ],
            ),
            # Semantic search
            CapabilitySpec(
                name="semantic_search",
                description="Search emails using AI semantic similarity (meaning-based, not keyword).",
                parameters=[
                    ParameterSpec(
                        name="query",
                        type=ParameterType.STRING,
                        description="Natural language search query",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Filter by account",
                        required=False,
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
            # Stats
            CapabilitySpec(
                name="stats",
                description="Show email statistics (counts by account, folder, category).",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Filter by account",
                        required=False,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.mailcraft",
                **{"class": "MailcraftPlugin"},
            ),
        ),
        permissions=[
            "network:https",
            "filesystem:read",
        ],
    )


class MailcraftPlugin(PluginBase):
    """AI-powered email management plugin."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the mailcraft plugin."""
        super().__init__(_create_manifest(), config)
        self._bin = self._find_binary()
        self._config = config or {}

    def _find_binary(self) -> str | None:
        """Find mailcraft CLI binary."""
        locations = [
            Path.home() / ".local" / "bin" / "mailcraft",
            Path.home() / "projects" / "mailcraft" / ".venv" / "bin" / "mailcraft",
            shutil.which("mailcraft"),
        ]
        for loc in locations:
            if loc and Path(str(loc)).exists():
                return str(loc)
        return None

    def _is_configured(self) -> bool:
        """Check if mailcraft is configured."""
        return self._bin is not None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a mailcraft capability."""
        handlers = {
            "fetch": self._fetch,
            "list": self._list,
            "search": self._search,
            "read": self._read,
            "send": self._send,
            "categorize": self._categorize,
            "cleanup": self._cleanup,
            "clean_spam": self._clean_spam,
            "batch_delete": self._batch_delete,
            "learn_from_trash": self._learn_from_trash,
            "semantic_search": self._semantic_search,
            "stats": self._stats,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        if not self._is_configured():
            return PluginResult.error_result(
                "MailCraft CLI is not installed. Install mailcraft or set path in config.",
                code="NOT_CONFIGURED",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"MailCraft operation failed: {e}",
                code="MAILCRAFT_ERROR",
            )

    async def _run_cli(self, *args: str, timeout: int = 120) -> tuple[str, str, int]:
        """Run mailcraft CLI command."""
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

    async def _fetch(
        self,
        account: str | None = None,
        folder: str | None = None,
        limit: int | None = None,
    ) -> PluginResult:
        """Fetch emails from IMAP servers."""
        args = ["fetch"]
        if account:
            args.extend(["--account", account])
        if folder:
            args.extend(["--folder", folder])
        if limit is not None:
            args.extend(["--limit", str(limit)])

        stdout, stderr, code = await self._run_cli(*args, timeout=180)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="FETCH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Emails fetched",
        )

    async def _list(
        self,
        account: str | None = None,
        folder: str | None = None,
        limit: int = 20,
        unread: bool = False,
    ) -> PluginResult:
        """List emails."""
        args = ["list", "--limit", str(limit)]
        if account:
            args.extend(["--account", account])
        if folder:
            args.extend(["--folder", folder])
        if unread:
            args.append("--unread")

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Email list",
        )

    async def _search(
        self,
        query: str,
        account: str | None = None,
        limit: int = 20,
    ) -> PluginResult:
        """Search emails."""
        args = ["search", query, "--limit", str(limit)]
        if account:
            args.extend(["--account", account])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SEARCH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Search results for: {query}",
        )

    async def _read(self, message_id: str) -> PluginResult:
        """Read a single email."""
        stdout, stderr, code = await self._run_cli("read", message_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="READ_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Email {message_id}",
        )

    async def _send(
        self,
        to: str,
        subject: str,
        body: str,
        account: str | None = None,
        attachments: str | None = None,
        cc: str | None = None,
    ) -> PluginResult:
        """Send an email."""
        args = ["send", "--to", to, "--subject", subject, "--body", body]
        if account:
            args.extend(["--account", account])
        if attachments:
            for path in attachments.split(","):
                args.extend(["--attachment", path.strip()])
        if cc:
            args.extend(["--cc", cc])

        stdout, stderr, code = await self._run_cli(*args, timeout=60)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SEND_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Email sent to {to}",
        )

    async def _categorize(
        self,
        account: str | None = None,
        limit: int | None = None,
        folder: str | None = None,
    ) -> PluginResult:
        """AI email categorization."""
        args = ["categorize"]
        if account:
            args.extend(["--account", account])
        if limit is not None:
            args.extend(["--limit", str(limit)])
        if folder:
            args.extend(["--folder", folder])

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="CATEGORIZE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Categorization complete",
        )

    async def _cleanup(
        self,
        account: str | None = None,
        dry_run: bool = False,
    ) -> PluginResult:
        """Full AI cleanup."""
        args = ["cleanup"]
        if account:
            args.extend(["--account", account])
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="CLEANUP_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Cleanup complete",
        )

    async def _clean_spam(
        self,
        account: str | None = None,
        dry_run: bool = False,
    ) -> PluginResult:
        """AI spam detection and removal."""
        args = ["clean-spam"]
        if account:
            args.extend(["--account", account])
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="CLEAN_SPAM_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Spam cleanup complete",
        )

    async def _batch_delete(
        self,
        pattern: str,
        account: str | None = None,
        dry_run: bool = False,
    ) -> PluginResult:
        """Batch delete by sender pattern."""
        args = ["batch-delete", "--pattern", pattern]
        if account:
            args.extend(["--account", account])
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=120)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="BATCH_DELETE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Batch delete for pattern: {pattern}",
        )

    async def _learn_from_trash(
        self,
        account: str | None = None,
        min_count: int = 3,
    ) -> PluginResult:
        """Learn categorization rules from trash."""
        args = ["learn-from-trash", "--min-count", str(min_count)]
        if account:
            args.extend(["--account", account])

        stdout, stderr, code = await self._run_cli(*args, timeout=120)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="LEARN_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Learned rules from trash",
        )

    async def _semantic_search(
        self,
        query: str,
        account: str | None = None,
        limit: int = 10,
    ) -> PluginResult:
        """Semantic similarity search."""
        args = ["semantic-search", query, "--limit", str(limit)]
        if account:
            args.extend(["--account", account])

        stdout, stderr, code = await self._run_cli(*args, timeout=60)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SEMANTIC_SEARCH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Semantic search results for: {query}",
        )

    async def _stats(self, account: str | None = None) -> PluginResult:
        """Email statistics."""
        args = ["stats"]
        if account:
            args.extend(["--account", account])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="STATS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Email statistics",
        )


__all__ = ["MailcraftPlugin"]
