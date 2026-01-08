"""Task storage using SQLite."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(str, Enum):
    """Task status."""

    INBOX = "inbox"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    SOMEDAY = "someday"

    @property
    def score(self) -> int:
        """Get numeric score for priority."""
        return {
            TaskPriority.CRITICAL: 100,
            TaskPriority.HIGH: 75,
            TaskPriority.NORMAL: 50,
            TaskPriority.LOW: 25,
            TaskPriority.SOMEDAY: 10,
        }[self]


@dataclass
class Task:
    """Represents a task."""

    task_id: str
    title: str
    status: TaskStatus = TaskStatus.INBOX
    priority: TaskPriority = TaskPriority.NORMAL
    area: str = ""
    project: str = ""
    due_date: datetime | None = None
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "area": self.area,
            "project": self.project,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "notes": self.notes,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_overdue": self.is_overdue,
        }

    def summary(self) -> dict[str, Any]:
        """Get a brief summary of the task."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "area": self.area,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_overdue": self.is_overdue,
        }

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date:
            return False
        if self.status == TaskStatus.COMPLETED:
            return False
        return datetime.now() > self.due_date

    @property
    def urgency_score(self) -> float:
        """Calculate urgency score based on due date."""
        if not self.due_date:
            return 0

        now = datetime.now()
        if self.due_date < now:
            # Overdue - high urgency
            days_overdue = (now - self.due_date).days
            return min(100, 80 + days_overdue * 5)

        days_until = (self.due_date - now).days
        if days_until == 0:
            return 70  # Due today
        elif days_until == 1:
            return 60  # Due tomorrow
        elif days_until <= 7:
            return 50  # Due this week
        elif days_until <= 30:
            return 30  # Due this month
        else:
            return 10  # Far future

    @property
    def total_score(self) -> float:
        """Calculate total priority score for ranking."""
        priority_score = self.priority.score
        urgency = self.urgency_score

        # Weighted combination
        return priority_score * 0.6 + urgency * 0.4


class TaskStore:
    """SQLite-based task storage."""

    def __init__(self, db_path: Path | None = None):
        """Initialize task store.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.config/mother/tasks.db
        """
        if db_path is None:
            db_path = Path.home() / ".config" / "mother" / "tasks.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'inbox',
                    priority TEXT NOT NULL DEFAULT 'normal',
                    area TEXT,
                    project TEXT,
                    due_date TEXT,
                    notes TEXT,
                    tags TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_area ON tasks(area)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)")

            # FTS for search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
                    title,
                    notes,
                    task_id UNINDEXED,
                    content='tasks',
                    content_rowid='rowid'
                )
            """)

            # Triggers for FTS
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
                    INSERT INTO tasks_fts(rowid, title, notes, task_id)
                    VALUES (new.rowid, new.title, new.notes, new.task_id);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
                    INSERT INTO tasks_fts(tasks_fts, rowid, title, notes, task_id)
                    VALUES('delete', old.rowid, old.title, old.notes, old.task_id);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE ON tasks BEGIN
                    INSERT INTO tasks_fts(tasks_fts, rowid, title, notes, task_id)
                    VALUES('delete', old.rowid, old.title, old.notes, old.task_id);
                    INSERT INTO tasks_fts(rowid, title, notes, task_id)
                    VALUES (new.rowid, new.title, new.notes, new.task_id);
                END
            """)

            conn.commit()

    def generate_task_id(self) -> str:
        """Generate a unique task ID."""
        return str(uuid.uuid4())[:8]

    def add_task(self, task: Task) -> str:
        """Add a new task.

        Args:
            task: Task to add

        Returns:
            Task ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    task_id, title, status, priority, area, project,
                    due_date, notes, tags, created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.title,
                    task.status.value,
                    task.priority.value,
                    task.area,
                    task.project,
                    task.due_date.isoformat() if task.due_date else None,
                    task.notes,
                    json.dumps(task.tags),
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else None,
                ),
            )
            conn.commit()

        return task.task_id

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()

            if not row:
                return None

            return self._row_to_task(row)

    def update_task(self, task: Task) -> bool:
        """Update an existing task."""
        task.updated_at = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE tasks SET
                    title = ?, status = ?, priority = ?, area = ?, project = ?,
                    due_date = ?, notes = ?, tags = ?, updated_at = ?, completed_at = ?
                WHERE task_id = ?
                """,
                (
                    task.title,
                    task.status.value,
                    task.priority.value,
                    task.area,
                    task.project,
                    task.due_date.isoformat() if task.due_date else None,
                    task.notes,
                    json.dumps(task.tags),
                    task.updated_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.task_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        now = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE tasks SET status = ?, completed_at = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TaskStatus.COMPLETED.value, now.isoformat(), now.isoformat(), task_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        area: str | None = None,
        priority: TaskPriority | None = None,
        overdue_only: bool = False,
        include_completed: bool = False,
        limit: int = 50,
    ) -> list[Task]:
        """List tasks with optional filters."""
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        elif not include_completed:
            conditions.append("status != ?")
            params.append(TaskStatus.COMPLETED.value)

        if area:
            conditions.append("area = ?")
            params.append(area)

        if priority:
            conditions.append("priority = ?")
            params.append(priority.value)

        if overdue_only:
            conditions.append("due_date < ? AND status != ?")
            params.append(datetime.now().isoformat())
            params.append(TaskStatus.COMPLETED.value)

        query = "SELECT * FROM tasks"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_top_tasks(self, limit: int = 5) -> list[Task]:
        """Get top priority tasks sorted by score."""
        # Get all active tasks
        tasks = self.list_tasks(include_completed=False, limit=100)

        # Sort by total score (priority + urgency)
        tasks.sort(key=lambda t: t.total_score, reverse=True)

        return tasks[:limit]

    def get_focus_task(self) -> Task | None:
        """Get the single most important task to focus on."""
        top_tasks = self.get_top_tasks(limit=1)
        return top_tasks[0] if top_tasks else None

    def search_tasks(self, query: str, limit: int = 10) -> list[Task]:
        """Search tasks by title or notes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Format query for FTS5
            words = query.strip().split()
            if len(words) > 1:
                fts_query = " OR ".join(f'"{w}"' for w in words if w)
            else:
                fts_query = f'"{query}"' if query else "*"

            rows = conn.execute(
                """
                SELECT t.* FROM tasks t
                JOIN tasks_fts f ON t.task_id = f.task_id
                WHERE tasks_fts MATCH ?
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()

            return [self._row_to_task(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        """Get task statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

            status_counts = conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall()

            priority_counts = conn.execute(
                "SELECT priority, COUNT(*) FROM tasks WHERE status != 'completed' GROUP BY priority"
            ).fetchall()

            overdue = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND status != ?",
                (datetime.now().isoformat(), TaskStatus.COMPLETED.value),
            ).fetchone()[0]

            due_today = conn.execute(
                """
                SELECT COUNT(*) FROM tasks
                WHERE date(due_date) = date('now') AND status != ?
                """,
                (TaskStatus.COMPLETED.value,),
            ).fetchone()[0]

            due_this_week = conn.execute(
                """
                SELECT COUNT(*) FROM tasks
                WHERE due_date BETWEEN ? AND ? AND status != ?
                """,
                (
                    datetime.now().isoformat(),
                    (datetime.now() + timedelta(days=7)).isoformat(),
                    TaskStatus.COMPLETED.value,
                ),
            ).fetchone()[0]

            # Area breakdown
            area_counts = conn.execute(
                "SELECT area, COUNT(*) FROM tasks WHERE status != 'completed' AND area != '' GROUP BY area"
            ).fetchall()

            return {
                "total": total,
                "by_status": {row[0]: row[1] for row in status_counts},
                "by_priority": {row[0]: row[1] for row in priority_counts},
                "by_area": {row[0]: row[1] for row in area_counts},
                "overdue": overdue,
                "due_today": due_today,
                "due_this_week": due_this_week,
            }

    def get_areas(self) -> list[str]:
        """Get list of all areas."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT DISTINCT area FROM tasks WHERE area != '' ORDER BY area").fetchall()
            return [row[0] for row in rows]

    def get_projects(self) -> list[str]:
        """Get list of all projects."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT DISTINCT project FROM tasks WHERE project != '' ORDER BY project").fetchall()
            return [row[0] for row in rows]

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert database row to Task object."""
        return Task(
            task_id=row["task_id"],
            title=row["title"],
            status=TaskStatus(row["status"]),
            priority=TaskPriority(row["priority"]),
            area=row["area"] or "",
            project=row["project"] or "",
            due_date=datetime.fromisoformat(row["due_date"]) if row["due_date"] else None,
            notes=row["notes"] or "",
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )


def parse_due_date(due_str: str) -> datetime | None:
    """Parse due date string.

    Supports:
    - ISO format: YYYY-MM-DD
    - Relative: +Nd (N days from now)
    - Named: today, tomorrow
    """
    if not due_str:
        return None

    due_str = due_str.strip().lower()

    if due_str == "today":
        return datetime.now().replace(hour=23, minute=59, second=59)
    elif due_str == "tomorrow":
        return (datetime.now() + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    elif due_str.startswith("+") and due_str.endswith("d"):
        try:
            days = int(due_str[1:-1])
            return (datetime.now() + timedelta(days=days)).replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    # Try ISO format
    try:
        return datetime.fromisoformat(due_str)
    except ValueError:
        pass

    # Try date only
    try:
        return datetime.strptime(due_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError:
        pass

    return None
