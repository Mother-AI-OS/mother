"""Built-in tasks plugin for Mother AI OS.

Provides task management capabilities: add, list, complete, search, prioritize.
"""

from __future__ import annotations

from datetime import datetime
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
from .storage import Task, TaskPriority, TaskStatus, TaskStore, parse_due_date


def _create_manifest() -> PluginManifest:
    """Create the tasks plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="tasks",
            version="1.0.0",
            description="Task management for Mother AI OS: add, list, complete, search, prioritize",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Focus - get the most important task
            CapabilitySpec(
                name="focus",
                description="Get THE single most important task to focus on right now, based on priority and urgency.",
                parameters=[],
            ),
            # Top - get top priority tasks
            CapabilitySpec(
                name="top",
                description="Get top priority tasks ranked by importance and urgency.",
                parameters=[
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Number of tasks to return (default: 5)",
                        required=False,
                        default=5,
                    ),
                ],
            ),
            # Add task
            CapabilitySpec(
                name="add",
                description="Add a new task with optional priority, area, project, and due date.",
                parameters=[
                    ParameterSpec(
                        name="title",
                        type=ParameterType.STRING,
                        description="Task title/description",
                        required=True,
                    ),
                    ParameterSpec(
                        name="priority",
                        type=ParameterType.STRING,
                        description="Priority: critical, high, normal, low, someday (default: normal)",
                        required=False,
                        default="normal",
                    ),
                    ParameterSpec(
                        name="area",
                        type=ParameterType.STRING,
                        description="Life area or category (e.g., work, personal, health)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="project",
                        type=ParameterType.STRING,
                        description="Project name",
                        required=False,
                    ),
                    ParameterSpec(
                        name="due",
                        type=ParameterType.STRING,
                        description="Due date: YYYY-MM-DD, +Nd for N days, 'today', 'tomorrow'",
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
            # List tasks
            CapabilitySpec(
                name="list",
                description="List tasks with optional filters.",
                parameters=[
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="Filter by status: inbox, todo, in_progress, waiting, completed",
                        required=False,
                    ),
                    ParameterSpec(
                        name="area",
                        type=ParameterType.STRING,
                        description="Filter by area",
                        required=False,
                    ),
                    ParameterSpec(
                        name="priority",
                        type=ParameterType.STRING,
                        description="Filter by priority",
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
                        description="Maximum tasks to return (default: 20)",
                        required=False,
                        default=20,
                    ),
                ],
            ),
            # Complete task
            CapabilitySpec(
                name="complete",
                description="Mark a task as completed.",
                parameters=[
                    ParameterSpec(
                        name="task_id",
                        type=ParameterType.STRING,
                        description="Task ID to complete",
                        required=True,
                    ),
                ],
            ),
            # Update task
            CapabilitySpec(
                name="update",
                description="Update an existing task.",
                parameters=[
                    ParameterSpec(
                        name="task_id",
                        type=ParameterType.STRING,
                        description="Task ID to update",
                        required=True,
                    ),
                    ParameterSpec(
                        name="title",
                        type=ParameterType.STRING,
                        description="New title",
                        required=False,
                    ),
                    ParameterSpec(
                        name="priority",
                        type=ParameterType.STRING,
                        description="New priority",
                        required=False,
                    ),
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="New status",
                        required=False,
                    ),
                    ParameterSpec(
                        name="area",
                        type=ParameterType.STRING,
                        description="New area",
                        required=False,
                    ),
                    ParameterSpec(
                        name="due",
                        type=ParameterType.STRING,
                        description="New due date",
                        required=False,
                    ),
                    ParameterSpec(
                        name="notes",
                        type=ParameterType.STRING,
                        description="New notes",
                        required=False,
                    ),
                ],
            ),
            # Delete task
            CapabilitySpec(
                name="delete",
                description="Delete a task.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="task_id",
                        type=ParameterType.STRING,
                        description="Task ID to delete",
                        required=True,
                    ),
                ],
            ),
            # Get task
            CapabilitySpec(
                name="get",
                description="Get details of a specific task.",
                parameters=[
                    ParameterSpec(
                        name="task_id",
                        type=ParameterType.STRING,
                        description="Task ID",
                        required=True,
                    ),
                ],
            ),
            # Search tasks
            CapabilitySpec(
                name="search",
                description="Search tasks by title or notes.",
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
            # Stats
            CapabilitySpec(
                name="stats",
                description="Get task statistics and overview.",
                parameters=[],
            ),
            # Areas
            CapabilitySpec(
                name="areas",
                description="List all task areas/categories.",
                parameters=[],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.tasks",
                **{"class": "TasksPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "filesystem:write",
        ],
    )


class TasksPlugin(PluginBase):
    """Built-in plugin for task management."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the tasks plugin."""
        super().__init__(_create_manifest(), config)

        # Initialize task store
        db_path = None
        if config and "db_path" in config:
            db_path = Path(config["db_path"])
        self._store = TaskStore(db_path)

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a tasks capability."""
        handlers = {
            "focus": self._focus,
            "top": self._top,
            "add": self._add,
            "list": self._list,
            "complete": self._complete,
            "update": self._update,
            "delete": self._delete,
            "get": self._get,
            "search": self._search,
            "stats": self._stats,
            "areas": self._areas,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            return await handler(**params)
        except ValueError as e:
            return PluginResult.error_result(
                str(e),
                code="INVALID_INPUT",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Task operation failed: {e}",
                code="TASK_ERROR",
            )

    async def _focus(self) -> PluginResult:
        """Get the single most important task."""
        task = self._store.get_focus_task()

        if not task:
            return PluginResult.success_result(
                data={"has_task": False, "task": None},
                message="No active tasks. You're all caught up!",
            )

        return PluginResult.success_result(
            data={
                "has_task": True,
                "task": task.to_dict(),
                "score": task.total_score,
            },
            message=f"Focus on: {task.title}",
        )

    async def _top(self, limit: int = 5) -> PluginResult:
        """Get top priority tasks."""
        tasks = self._store.get_top_tasks(limit=limit)

        return PluginResult.success_result(
            data={
                "tasks": [t.to_dict() for t in tasks],
                "count": len(tasks),
            },
            message=f"Top {len(tasks)} priority tasks",
        )

    async def _add(
        self,
        title: str,
        priority: str = "normal",
        area: str = "",
        project: str = "",
        due: str = "",
        notes: str = "",
    ) -> PluginResult:
        """Add a new task."""
        # Validate priority
        try:
            task_priority = TaskPriority(priority.lower())
        except ValueError:
            return PluginResult.error_result(
                f"Invalid priority: {priority}. Must be one of: critical, high, normal, low, someday",
                code="INVALID_INPUT",
            )

        # Parse due date
        due_date = parse_due_date(due) if due else None

        # Create task
        task = Task(
            task_id=self._store.generate_task_id(),
            title=title,
            priority=task_priority,
            area=area,
            project=project,
            due_date=due_date,
            notes=notes,
            status=TaskStatus.TODO,
        )

        task_id = self._store.add_task(task)

        return PluginResult.success_result(
            data=task.to_dict(),
            message=f"Added task: {title} [{task_id}]",
        )

    async def _list(
        self,
        status: str | None = None,
        area: str | None = None,
        priority: str | None = None,
        overdue: bool = False,
        limit: int = 20,
    ) -> PluginResult:
        """List tasks with filters."""
        # Parse status
        task_status = None
        if status:
            try:
                task_status = TaskStatus(status.lower())
            except ValueError:
                return PluginResult.error_result(
                    f"Invalid status: {status}",
                    code="INVALID_INPUT",
                )

        # Parse priority
        task_priority = None
        if priority:
            try:
                task_priority = TaskPriority(priority.lower())
            except ValueError:
                return PluginResult.error_result(
                    f"Invalid priority: {priority}",
                    code="INVALID_INPUT",
                )

        tasks = self._store.list_tasks(
            status=task_status,
            area=area,
            priority=task_priority,
            overdue_only=overdue,
            limit=limit,
        )

        return PluginResult.success_result(
            data={
                "tasks": [t.summary() for t in tasks],
                "count": len(tasks),
            },
            message=f"Found {len(tasks)} task(s)",
        )

    async def _complete(self, task_id: str) -> PluginResult:
        """Mark a task as completed."""
        task = self._store.get_task(task_id)

        if not task:
            return PluginResult.error_result(
                f"Task not found: {task_id}",
                code="NOT_FOUND",
            )

        success = self._store.complete_task(task_id)

        if success:
            return PluginResult.success_result(
                data={"task_id": task_id, "title": task.title},
                message=f"Completed: {task.title}",
            )
        else:
            return PluginResult.error_result(
                "Failed to complete task",
                code="UPDATE_FAILED",
            )

    async def _update(
        self,
        task_id: str,
        title: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        area: str | None = None,
        due: str | None = None,
        notes: str | None = None,
    ) -> PluginResult:
        """Update a task."""
        task = self._store.get_task(task_id)

        if not task:
            return PluginResult.error_result(
                f"Task not found: {task_id}",
                code="NOT_FOUND",
            )

        # Update fields
        if title is not None:
            task.title = title
        if priority is not None:
            try:
                task.priority = TaskPriority(priority.lower())
            except ValueError:
                return PluginResult.error_result(
                    f"Invalid priority: {priority}",
                    code="INVALID_INPUT",
                )
        if status is not None:
            try:
                task.status = TaskStatus(status.lower())
                if task.status == TaskStatus.COMPLETED and not task.completed_at:
                    task.completed_at = datetime.now()
            except ValueError:
                return PluginResult.error_result(
                    f"Invalid status: {status}",
                    code="INVALID_INPUT",
                )
        if area is not None:
            task.area = area
        if due is not None:
            task.due_date = parse_due_date(due)
        if notes is not None:
            task.notes = notes

        success = self._store.update_task(task)

        if success:
            return PluginResult.success_result(
                data=task.to_dict(),
                message=f"Updated task: {task.title}",
            )
        else:
            return PluginResult.error_result(
                "Failed to update task",
                code="UPDATE_FAILED",
            )

    async def _delete(self, task_id: str) -> PluginResult:
        """Delete a task."""
        task = self._store.get_task(task_id)

        if not task:
            return PluginResult.error_result(
                f"Task not found: {task_id}",
                code="NOT_FOUND",
            )

        success = self._store.delete_task(task_id)

        if success:
            return PluginResult.success_result(
                data={"task_id": task_id, "title": task.title},
                message=f"Deleted task: {task.title}",
            )
        else:
            return PluginResult.error_result(
                "Failed to delete task",
                code="DELETE_FAILED",
            )

    async def _get(self, task_id: str) -> PluginResult:
        """Get task details."""
        task = self._store.get_task(task_id)

        if not task:
            return PluginResult.error_result(
                f"Task not found: {task_id}",
                code="NOT_FOUND",
            )

        return PluginResult.success_result(
            data=task.to_dict(),
            message=f"Task: {task.title}",
        )

    async def _search(self, query: str, limit: int = 10) -> PluginResult:
        """Search tasks."""
        tasks = self._store.search_tasks(query, limit=limit)

        return PluginResult.success_result(
            data={
                "query": query,
                "tasks": [t.summary() for t in tasks],
                "count": len(tasks),
            },
            message=f"Found {len(tasks)} task(s) matching '{query}'",
        )

    async def _stats(self) -> PluginResult:
        """Get task statistics."""
        stats = self._store.get_stats()

        # Calculate active count
        active = stats.get("total", 0) - stats.get("by_status", {}).get("completed", 0)

        return PluginResult.success_result(
            data=stats,
            message=f"Tasks: {active} active, {stats.get('overdue', 0)} overdue, {stats.get('due_today', 0)} due today",
        )

    async def _areas(self) -> PluginResult:
        """List all areas."""
        areas = self._store.get_areas()

        return PluginResult.success_result(
            data={"areas": areas, "count": len(areas)},
            message=f"Found {len(areas)} area(s)",
        )


__all__ = ["TasksPlugin"]
