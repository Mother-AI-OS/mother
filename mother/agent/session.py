"""Persistent session storage for Mother agent.

Sessions survive server restarts and can be resumed with full context.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("mother.session")


@dataclass
class Session:
    """A persistent session with full message history."""

    id: str
    created_at: datetime
    updated_at: datetime
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None
    status: str = "active"  # active, completed, abandoned

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": self.messages,
            "metadata": self.metadata,
            "summary": self.summary,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=data.get("messages", []),
            metadata=data.get("metadata", {}),
            summary=data.get("summary"),
            status=data.get("status", "active"),
        )


class SessionStore:
    """SQLite-based persistent session storage."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".local" / "share" / "mother" / "sessions.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    metadata TEXT,
                    summary TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)

            # Index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated
                ON sessions(updated_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_status
                ON sessions(status)
            """)

            conn.commit()
        logger.info(f"Session store initialized: {self.db_path}")

    def save(self, session: Session) -> None:
        """Save or update a session."""
        session.updated_at = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (id, created_at, updated_at, messages, metadata, summary, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    json.dumps(session.messages),
                    json.dumps(session.metadata),
                    session.summary,
                    session.status,
                ),
            )
            conn.commit()
        logger.debug(f"Saved session {session.id} with {len(session.messages)} messages")

    def get(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = cursor.fetchone()

            if row:
                return Session(
                    id=row["id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    messages=json.loads(row["messages"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    summary=row["summary"],
                    status=row["status"],
                )
        return None

    def get_recent(self, limit: int = 10, status: str | None = None) -> list[Session]:
        """Get recent sessions."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if status:
                cursor = conn.execute(
                    """
                    SELECT * FROM sessions
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (status, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM sessions
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            return [
                Session(
                    id=row["id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    messages=json.loads(row["messages"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    summary=row["summary"],
                    status=row["status"],
                )
                for row in cursor.fetchall()
            ]

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_stats(self) -> dict[str, Any]:
        """Get session store statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            total = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM sessions WHERE status = 'active'")
            active = cursor.fetchone()[0]

            cursor = conn.execute("SELECT AVG(json_array_length(messages)) FROM sessions")
            avg_messages = cursor.fetchone()[0] or 0

            return {
                "total_sessions": total,
                "active_sessions": active,
                "avg_messages_per_session": round(avg_messages, 1),
            }
