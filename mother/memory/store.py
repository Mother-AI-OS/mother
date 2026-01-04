"""Persistent memory storage using SQLite with vector embeddings."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np


@dataclass
class Memory:
    """A single memory/observation."""

    id: int | None
    timestamp: datetime
    session_id: str
    role: str  # 'user', 'assistant', 'tool_result'
    content: str
    embedding: list[float] | None
    tool_name: str | None = None
    tool_args: dict | None = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "metadata": self.metadata,
        }


class MemoryStore:
    """SQLite-based memory store with vector search capabilities."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".local" / "share" / "mother" / "memory.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    tool_name TEXT,
                    tool_args TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_session
                ON memories(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_timestamp
                ON memories(timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_role
                ON memories(role)
            """)

            conn.commit()

    def add(self, memory: Memory) -> int:
        """Add a memory to the store. Returns the memory ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO memories
                (timestamp, session_id, role, content, embedding, tool_name, tool_args, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.timestamp.isoformat(),
                    memory.session_id,
                    memory.role,
                    memory.content,
                    self._serialize_embedding(memory.embedding),
                    memory.tool_name,
                    json.dumps(memory.tool_args) if memory.tool_args else None,
                    json.dumps(memory.metadata) if memory.metadata else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get(self, memory_id: int) -> Memory | None:
        """Get a specific memory by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_memory(row)
        return None

    def get_recent(self, limit: int = 20, session_id: str | None = None) -> list[Memory]:
        """Get recent memories, optionally filtered by session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if session_id:
                cursor = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM memories
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            return [self._row_to_memory(row) for row in cursor.fetchall()]

    def search_semantic(
        self,
        query_embedding: list[float],
        limit: int = 10,
        min_similarity: float = 0.5,
        exclude_session: str | None = None,
    ) -> list[tuple[Memory, float]]:
        """
        Search memories by semantic similarity.

        Returns list of (memory, similarity_score) tuples.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get all memories with embeddings
            if exclude_session:
                cursor = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE embedding IS NOT NULL
                    AND session_id != ?
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    """,
                    (exclude_session,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE embedding IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    """
                )

            results = []
            query_vec = np.array(query_embedding)

            for row in cursor.fetchall():
                embedding = self._deserialize_embedding(row["embedding"])
                if embedding is not None:
                    # Cosine similarity
                    memory_vec = np.array(embedding)
                    similarity = np.dot(query_vec, memory_vec) / (
                        np.linalg.norm(query_vec) * np.linalg.norm(memory_vec)
                    )

                    if similarity >= min_similarity:
                        results.append((self._row_to_memory(row), float(similarity)))

            # Sort by similarity descending
            results.sort(key=lambda x: x[1], reverse=True)

            return results[:limit]

    def search_text(self, query: str, limit: int = 20) -> list[Memory]:
        """Simple text search in content."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM memories
                WHERE content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f"%{query}%", limit),
            )

            return [self._row_to_memory(row) for row in cursor.fetchall()]

    def get_session_history(self, session_id: str) -> list[Memory]:
        """Get all memories for a session in chronological order."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM memories
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            )

            return [self._row_to_memory(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """Get memory store statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM memories")
            total = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(DISTINCT session_id) FROM memories")
            sessions = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL")
            with_embeddings = cursor.fetchone()[0]

            return {
                "total_memories": total,
                "total_sessions": sessions,
                "memories_with_embeddings": with_embeddings,
            }

    def _serialize_embedding(self, embedding: list[float] | None) -> bytes | None:
        """Serialize embedding to bytes for storage."""
        if embedding is None:
            return None
        return np.array(embedding, dtype=np.float32).tobytes()

    def _deserialize_embedding(self, data: bytes | None) -> list[float] | None:
        """Deserialize embedding from bytes."""
        if data is None:
            return None
        return np.frombuffer(data, dtype=np.float32).tolist()

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert database row to Memory object."""
        return Memory(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            embedding=self._deserialize_embedding(row["embedding"]),
            tool_name=row["tool_name"],
            tool_args=json.loads(row["tool_args"]) if row["tool_args"] else None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )
