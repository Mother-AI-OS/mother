"""Document storage using SQLite with FTS5 for full-text search."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Document:
    """Represents a processed document."""

    doc_id: str
    filename: str
    doc_type: str
    content: str
    chunks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    entities: list[dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    file_hash: str = ""
    pages: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "doc_type": self.doc_type,
            "content_preview": self.content[:500] if self.content else "",
            "chunk_count": len(self.chunks),
            "entity_count": len(self.entities),
            "pages": self.pages,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SearchResult:
    """Search result with relevance score."""

    doc_id: str
    filename: str
    doc_type: str
    score: float
    content_preview: str
    chunk_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "doc_type": self.doc_type,
            "score": self.score,
            "content_preview": self.content_preview,
        }


class DocumentStore:
    """SQLite-based document storage with full-text search."""

    def __init__(self, db_path: Path | None = None):
        """Initialize document store.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.config/mother/datacraft.db
        """
        if db_path is None:
            db_path = Path.home() / ".config" / "mother" / "datacraft.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    file_hash TEXT,
                    pages INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    from_entity_id INTEGER NOT NULL,
                    relationship TEXT NOT NULL,
                    to_entity_id INTEGER NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
                )
            """)

            # Create FTS5 virtual table for full-text search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    content,
                    doc_id UNINDEXED,
                    chunk_index UNINDEXED,
                    content='chunks',
                    content_rowid='id'
                )
            """)

            # Triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                    INSERT INTO chunks_fts(rowid, content, doc_id, chunk_index)
                    VALUES (new.id, new.content, new.doc_id, new.chunk_index);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, content, doc_id, chunk_index)
                    VALUES('delete', old.id, old.content, old.doc_id, old.chunk_index);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, content, doc_id, chunk_index)
                    VALUES('delete', old.id, old.content, old.doc_id, old.chunk_index);
                    INSERT INTO chunks_fts(rowid, content, doc_id, chunk_index)
                    VALUES (new.id, new.content, new.doc_id, new.chunk_index);
                END
            """)

            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_doc_id ON entities(doc_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type)")

            conn.commit()

    def generate_doc_id(self, content: str, filename: str) -> str:
        """Generate a unique document ID based on content hash."""
        hash_input = f"{filename}:{content[:1000]}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:12]

    def store_document(self, doc: Document) -> str:
        """Store a document and its chunks.

        Args:
            doc: Document to store

        Returns:
            Document ID
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if document already exists
            existing = conn.execute(
                "SELECT doc_id FROM documents WHERE doc_id = ?",
                (doc.doc_id,),
            ).fetchone()

            if existing:
                # Update existing document
                conn.execute(
                    """
                    UPDATE documents SET
                        filename = ?, doc_type = ?, content = ?,
                        file_hash = ?, pages = ?, metadata = ?, created_at = ?
                    WHERE doc_id = ?
                    """,
                    (
                        doc.filename,
                        doc.doc_type,
                        doc.content,
                        doc.file_hash,
                        doc.pages,
                        json.dumps(doc.metadata),
                        doc.created_at.isoformat(),
                        doc.doc_id,
                    ),
                )
                # Delete old chunks and entities
                conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc.doc_id,))
                conn.execute("DELETE FROM entities WHERE doc_id = ?", (doc.doc_id,))
                conn.execute("DELETE FROM relationships WHERE doc_id = ?", (doc.doc_id,))
            else:
                # Insert new document
                conn.execute(
                    """
                    INSERT INTO documents (doc_id, filename, doc_type, content, file_hash, pages, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc.doc_id,
                        doc.filename,
                        doc.doc_type,
                        doc.content,
                        doc.file_hash,
                        doc.pages,
                        json.dumps(doc.metadata),
                        doc.created_at.isoformat(),
                    ),
                )

            # Insert chunks
            for i, chunk in enumerate(doc.chunks):
                conn.execute(
                    "INSERT INTO chunks (doc_id, chunk_index, content) VALUES (?, ?, ?)",
                    (doc.doc_id, i, chunk),
                )

            # Insert entities
            entity_ids = {}
            for i, entity in enumerate(doc.entities):
                cursor = conn.execute(
                    "INSERT INTO entities (doc_id, entity_type, value) VALUES (?, ?, ?)",
                    (doc.doc_id, entity.get("type", "unknown"), entity.get("value", "")),
                )
                entity_ids[i] = cursor.lastrowid

            conn.commit()

        return doc.doc_id

    def get_document(self, doc_id: str) -> Document | None:
        """Retrieve a document by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()

            if not row:
                return None

            # Get chunks
            chunks = conn.execute(
                "SELECT content FROM chunks WHERE doc_id = ? ORDER BY chunk_index",
                (doc_id,),
            ).fetchall()

            # Get entities
            entities = conn.execute(
                "SELECT entity_type, value FROM entities WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()

            return Document(
                doc_id=row["doc_id"],
                filename=row["filename"],
                doc_type=row["doc_type"],
                content=row["content"],
                chunks=[c["content"] for c in chunks],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                entities=[{"type": e["entity_type"], "value": e["value"]} for e in entities],
                created_at=datetime.fromisoformat(row["created_at"]),
                file_hash=row["file_hash"] or "",
                pages=row["pages"] or 0,
            )

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            # Cascading deletes handle chunks, entities, relationships
            conn.commit()
            return cursor.rowcount > 0

    def list_documents(self, doc_type: str | None = None) -> list[dict[str, Any]]:
        """List all documents."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if doc_type:
                rows = conn.execute(
                    """
                    SELECT d.*, COUNT(c.id) as chunk_count
                    FROM documents d
                    LEFT JOIN chunks c ON d.doc_id = c.doc_id
                    WHERE d.doc_type = ?
                    GROUP BY d.doc_id
                    ORDER BY d.created_at DESC
                    """,
                    (doc_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT d.*, COUNT(c.id) as chunk_count
                    FROM documents d
                    LEFT JOIN chunks c ON d.doc_id = c.doc_id
                    GROUP BY d.doc_id
                    ORDER BY d.created_at DESC
                    """,
                ).fetchall()

            return [
                {
                    "doc_id": row["doc_id"],
                    "filename": row["filename"],
                    "doc_type": row["doc_type"],
                    "chunks": row["chunk_count"],
                    "pages": row["pages"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def search(
        self,
        query: str,
        doc_type: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search documents using FTS5.

        Args:
            query: Search query
            doc_type: Optional document type filter
            limit: Maximum results

        Returns:
            List of search results with scores
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Format query for FTS5 - use OR between words for broader matching
            # Escape special characters and join with OR
            words = query.strip().split()
            if len(words) > 1:
                # Multiple words: search with OR to match any word
                fts_query = " OR ".join(f'"{w}"' for w in words if w)
            else:
                fts_query = f'"{query}"' if query else "*"

            # Use FTS5 for search with BM25 ranking
            if doc_type:
                rows = conn.execute(
                    """
                    SELECT
                        f.doc_id,
                        f.chunk_index,
                        f.content,
                        d.filename,
                        d.doc_type,
                        bm25(chunks_fts) as score
                    FROM chunks_fts f
                    JOIN documents d ON f.doc_id = d.doc_id
                    WHERE chunks_fts MATCH ? AND d.doc_type = ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (fts_query, doc_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        f.doc_id,
                        f.chunk_index,
                        f.content,
                        d.filename,
                        d.doc_type,
                        bm25(chunks_fts) as score
                    FROM chunks_fts f
                    JOIN documents d ON f.doc_id = d.doc_id
                    WHERE chunks_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()

            results = []
            for row in rows:
                # BM25 returns negative scores (more negative = better match)
                # Convert to 0-1 scale where 1 is best
                normalized_score = min(1.0, max(0.0, 1.0 + row["score"] / 10))

                results.append(
                    SearchResult(
                        doc_id=row["doc_id"],
                        filename=row["filename"],
                        doc_type=row["doc_type"],
                        score=normalized_score,
                        content_preview=row["content"][:300],
                        chunk_index=row["chunk_index"],
                    )
                )

            return results

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        with sqlite3.connect(self.db_path) as conn:
            doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            rel_count = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]

            # Document type breakdown
            type_counts = conn.execute("SELECT doc_type, COUNT(*) as count FROM documents GROUP BY doc_type").fetchall()

            return {
                "total_documents": doc_count,
                "total_chunks": chunk_count,
                "total_entities": entity_count,
                "total_relationships": rel_count,
                "by_type": {row[0]: row[1] for row in type_counts},
                "db_path": str(self.db_path),
                "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            }

    def get_graph(self, doc_id: str) -> dict[str, Any]:
        """Get knowledge graph for a document."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            entities = conn.execute(
                "SELECT id, entity_type, value FROM entities WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()

            relationships = conn.execute(
                """
                SELECT r.*, e1.value as from_value, e2.value as to_value
                FROM relationships r
                JOIN entities e1 ON r.from_entity_id = e1.id
                JOIN entities e2 ON r.to_entity_id = e2.id
                WHERE r.doc_id = ?
                """,
                (doc_id,),
            ).fetchall()

            return {
                "doc_id": doc_id,
                "entities": [{"id": e["id"], "type": e["entity_type"], "value": e["value"]} for e in entities],
                "relationships": [
                    {
                        "from": r["from_value"],
                        "relationship": r["relationship"],
                        "to": r["to_value"],
                    }
                    for r in relationships
                ],
            }
