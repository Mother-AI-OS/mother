"""acnjxn (Action Jackson) plugin for Mother AI OS.

Provides AI-enhanced task management capabilities:
- Task queries (focus, top, list, inbox, search, status)
- Soul/values introspection (soul, goals, clients)
- AI analysis (weigh, conflict, ask)
- Task mutations (add, complete)
- Sync and ingestion status
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
    """Create the acnjxn plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="acnjxn",
            version="1.0.0",
            description="AI-enhanced task management with value alignment and Google Tasks sync",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Focus - show #1 priority task
            CapabilitySpec(
                name="focus",
                description="Show the #1 priority task right now.",
                parameters=[],
            ),
            # Top priorities
            CapabilitySpec(
                name="top",
                description="Show top N priority tasks ranked by computed score.",
                parameters=[
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Number of tasks to show (default: 5)",
                        required=False,
                        default=5,
                    ),
                ],
            ),
            # List tasks
            CapabilitySpec(
                name="list",
                description="List tasks with optional filters by area, status, or overdue.",
                parameters=[
                    ParameterSpec(
                        name="area",
                        type=ParameterType.STRING,
                        description="Filter by life area (e.g. personal, family, health, finance, hucke_sanker, cleary, lawkraft, morpheus_mark, clients)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="Filter by status: inbox, todo, in_progress, waiting, completed",
                        required=False,
                    ),
                    ParameterSpec(
                        name="overdue",
                        type=ParameterType.BOOLEAN,
                        description="Show only overdue tasks",
                        required=False,
                        default=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum tasks to show (default: 20)",
                        required=False,
                        default=20,
                    ),
                ],
            ),
            # Inbox
            CapabilitySpec(
                name="inbox",
                description="Show unprocessed inbox tasks.",
                parameters=[
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum tasks to show (default: 20)",
                        required=False,
                        default=20,
                    ),
                ],
            ),
            # Search
            CapabilitySpec(
                name="search",
                description="Full-text search across all tasks by title and description.",
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
            # Status
            CapabilitySpec(
                name="status",
                description="Show task statistics and system status (counts, areas, overdue).",
                parameters=[],
            ),
            # Soul
            CapabilitySpec(
                name="soul",
                description="Show core values, life purpose, and guiding principles.",
                parameters=[],
            ),
            # Goals
            CapabilitySpec(
                name="goals",
                description="Show life goals with progress tracking.",
                parameters=[
                    ParameterSpec(
                        name="show_all",
                        type=ParameterType.BOOLEAN,
                        description="Include completed goals (default: active only)",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Clients
            CapabilitySpec(
                name="clients",
                description="List known clients for task auto-detection.",
                parameters=[],
            ),
            # Sync status
            CapabilitySpec(
                name="sync_status",
                description="Show Google Tasks sync status and statistics.",
                parameters=[],
            ),
            # Ingest stats
            CapabilitySpec(
                name="ingest_stats",
                description="Show email ingestion statistics.",
                parameters=[],
            ),
            # Ingest recent
            CapabilitySpec(
                name="ingest_recent",
                description="Show recently processed emails with task creation status.",
                parameters=[
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Number of recent ingests to show (default: 20)",
                        required=False,
                        default=20,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Filter by email account",
                        required=False,
                    ),
                ],
            ),
            # Weigh activity
            CapabilitySpec(
                name="weigh",
                description="Evaluate an activity's alignment with values and vision before committing.",
                parameters=[
                    ParameterSpec(
                        name="activity",
                        type=ParameterType.STRING,
                        description="Activity or task to evaluate",
                        required=True,
                    ),
                    ParameterSpec(
                        name="area",
                        type=ParameterType.STRING,
                        description="Life area context (auto-detected if not specified)",
                        required=False,
                    ),
                ],
            ),
            # Conflict check
            CapabilitySpec(
                name="conflict",
                description="Check if an activity conflicts with goals or values.",
                parameters=[
                    ParameterSpec(
                        name="activity",
                        type=ParameterType.STRING,
                        description="Activity to check for conflicts",
                        required=True,
                    ),
                ],
            ),
            # Ask AI
            CapabilitySpec(
                name="ask",
                description="Ask the AI advisor a question with full life context.",
                parameters=[
                    ParameterSpec(
                        name="question",
                        type=ParameterType.STRING,
                        description="Question to ask",
                        required=True,
                    ),
                ],
            ),
            # Add task
            CapabilitySpec(
                name="add",
                description="Add a new task with smart inference and value alignment.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="title",
                        type=ParameterType.STRING,
                        description="Task title/description",
                        required=True,
                    ),
                    ParameterSpec(
                        name="area",
                        type=ParameterType.STRING,
                        description="Life area (auto-detected if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="due",
                        type=ParameterType.STRING,
                        description="Due date (YYYY-MM-DD or +Nd for N days from now)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="priority",
                        type=ParameterType.STRING,
                        description="Priority: critical, high, normal, low, someday",
                        required=False,
                    ),
                    ParameterSpec(
                        name="client",
                        type=ParameterType.STRING,
                        description="Client name",
                        required=False,
                    ),
                    ParameterSpec(
                        name="notes",
                        type=ParameterType.STRING,
                        description="Additional notes",
                        required=False,
                    ),
                ],
            ),
            # Complete task
            CapabilitySpec(
                name="complete",
                description="Mark a task as completed.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="task_id",
                        type=ParameterType.STRING,
                        description="Task ID to complete",
                        required=True,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.acnjxn",
                **{"class": "AcnjxnPlugin"},
            ),
        ),
        permissions=[
            "network:https",
        ],
    )


class AcnjxnPlugin(PluginBase):
    """AI-enhanced task management plugin."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the acnjxn plugin."""
        super().__init__(_create_manifest(), config)
        self._bin = self._find_binary()
        self._config = config or {}

    def _find_binary(self) -> str | None:
        """Find acnjxn CLI binary."""
        locations = [
            Path.home() / ".local" / "bin" / "acnjxn",
            Path.home() / "projects" / "acnjxn" / ".venv" / "bin" / "acnjxn",
            shutil.which("acnjxn"),
        ]
        for loc in locations:
            if loc and Path(str(loc)).exists():
                return str(loc)
        return None

    def _is_configured(self) -> bool:
        """Check if acnjxn is configured."""
        return self._bin is not None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute an acnjxn capability."""
        handlers = {
            "focus": self._focus,
            "top": self._top,
            "list": self._list,
            "inbox": self._inbox,
            "search": self._search,
            "status": self._status,
            "soul": self._soul,
            "goals": self._goals,
            "clients": self._clients,
            "sync_status": self._sync_status,
            "ingest_stats": self._ingest_stats,
            "ingest_recent": self._ingest_recent,
            "weigh": self._weigh,
            "conflict": self._conflict,
            "ask": self._ask,
            "add": self._add,
            "complete": self._complete,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        if not self._is_configured():
            return PluginResult.error_result(
                "acnjxn CLI is not installed. Install acnjxn or check path.",
                code="NOT_CONFIGURED",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"acnjxn operation failed: {e}",
                code="ACNJXN_ERROR",
            )

    async def _run_cli(self, *args: str, timeout: int = 120) -> tuple[str, str, int]:
        """Run acnjxn CLI command."""
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

    # ── Read-only / Query handlers ──────────────────────────────────────

    async def _focus(self) -> PluginResult:
        """Show the #1 priority task."""
        stdout, stderr, code = await self._run_cli("focus", "--brief")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="FOCUS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Current focus task",
        )

    async def _top(self, limit: int = 5) -> PluginResult:
        """Show top priority tasks."""
        stdout, stderr, code = await self._run_cli("top", "-n", str(limit))
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="TOP_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Top {limit} priorities",
        )

    async def _list(
        self,
        area: str | None = None,
        status: str | None = None,
        overdue: bool = False,
        limit: int = 20,
    ) -> PluginResult:
        """List tasks with filters."""
        args = ["list"]
        if area:
            args.extend(["--area", area])
        if status:
            args.extend(["--status", status])
        if overdue:
            args.append("--overdue")
        args.extend(["-n", str(limit)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Task list",
        )

    async def _inbox(self, limit: int = 20) -> PluginResult:
        """Show unprocessed inbox tasks."""
        stdout, stderr, code = await self._run_cli("inbox", "-n", str(limit))
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="INBOX_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Inbox tasks",
        )

    async def _search(self, query: str, limit: int = 10) -> PluginResult:
        """Search tasks."""
        stdout, stderr, code = await self._run_cli("search", query, "-n", str(limit))
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SEARCH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Search results for: {query}",
        )

    async def _status(self) -> PluginResult:
        """Show task statistics."""
        stdout, stderr, code = await self._run_cli("status")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="STATUS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Task statistics",
        )

    async def _soul(self) -> PluginResult:
        """Show values, purpose, principles."""
        stdout, stderr, code = await self._run_cli("soul")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SOUL_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Soul configuration",
        )

    async def _goals(self, show_all: bool = False) -> PluginResult:
        """Show life goals."""
        args = ["goals"]
        if show_all:
            args.append("--all")

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="GOALS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Life goals",
        )

    async def _clients(self) -> PluginResult:
        """List known clients."""
        stdout, stderr, code = await self._run_cli("clients", "--list")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="CLIENTS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Known clients",
        )

    async def _sync_status(self) -> PluginResult:
        """Show Google Tasks sync status."""
        stdout, stderr, code = await self._run_cli("sync", "status")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SYNC_STATUS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Sync status",
        )

    async def _ingest_stats(self) -> PluginResult:
        """Show email ingestion statistics."""
        stdout, stderr, code = await self._run_cli("ingest", "stats")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="INGEST_STATS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Ingestion statistics",
        )

    async def _ingest_recent(
        self,
        limit: int = 20,
        account: str | None = None,
    ) -> PluginResult:
        """Show recently processed emails."""
        args = ["ingest", "recent", "-n", str(limit)]
        if account:
            args.extend(["-a", account])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="INGEST_RECENT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Recent email ingestions",
        )

    # ── AI-powered analysis handlers ────────────────────────────────────

    async def _weigh(
        self,
        activity: str,
        area: str | None = None,
    ) -> PluginResult:
        """Evaluate activity alignment."""
        args = ["weigh", activity, "--no-action"]
        if area:
            args.extend(["--area", area])

        stdout, stderr, code = await self._run_cli(*args, timeout=60)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="WEIGH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Evaluation: {activity}",
        )

    async def _conflict(self, activity: str) -> PluginResult:
        """Check for goal/value conflicts."""
        stdout, stderr, code = await self._run_cli("conflict", activity, timeout=60)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="CONFLICT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Conflict analysis: {activity}",
        )

    async def _ask(self, question: str) -> PluginResult:
        """AI advice with full life context."""
        stdout, stderr, code = await self._run_cli("ask", question, timeout=60)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="ASK_FAILED")
        return PluginResult.success_result(
            data={"answer": stdout.strip()},
            message="AI advisor response",
        )

    # ── Write operation handlers ────────────────────────────────────────

    async def _add(
        self,
        title: str,
        area: str | None = None,
        due: str | None = None,
        priority: str | None = None,
        client: str | None = None,
        notes: str | None = None,
    ) -> PluginResult:
        """Add a new task."""
        args = ["add", title, "--quick", "--no-eval"]
        if area:
            args.extend(["--area", area])
        if due:
            args.extend(["--due", due])
        if priority:
            args.extend(["--priority", priority])
        if client:
            args.extend(["--client", client])
        if notes:
            args.extend(["--notes", notes])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="ADD_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Added task: {title}",
        )

    async def _complete(self, task_id: str) -> PluginResult:
        """Mark a task as completed."""
        stdout, stderr, code = await self._run_cli("complete", task_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="COMPLETE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Completed task: {task_id}",
        )


__all__ = ["AcnjxnPlugin"]
