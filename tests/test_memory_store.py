"""Tests for the memory store module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from mother.memory.store import Memory, MemoryStore


class TestMemory:
    """Tests for Memory dataclass."""

    def test_creation(self):
        """Test Memory creation."""
        memory = Memory(
            id=1,
            timestamp=datetime.now(),
            session_id="test-session",
            role="user",
            content="Hello world",
            embedding=None,
        )
        assert memory.id == 1
        assert memory.role == "user"
        assert memory.content == "Hello world"

    def test_creation_with_all_fields(self):
        """Test Memory creation with all fields."""
        now = datetime.now()
        memory = Memory(
            id=1,
            timestamp=now,
            session_id="session-123",
            role="tool_result",
            content="Result data",
            embedding=[0.1, 0.2, 0.3],
            tool_name="filesystem",
            tool_args={"path": "/tmp"},
            metadata={"success": True},
        )
        assert memory.tool_name == "filesystem"
        assert memory.tool_args == {"path": "/tmp"}
        assert memory.metadata == {"success": True}

    def test_to_dict(self):
        """Test to_dict method."""
        now = datetime.now()
        memory = Memory(
            id=1,
            timestamp=now,
            session_id="test",
            role="user",
            content="Test",
            embedding=None,
            tool_name="test_tool",
            tool_args={"key": "value"},
            metadata={"meta": "data"},
        )
        result = memory.to_dict()

        assert result["id"] == 1
        assert result["timestamp"] == now.isoformat()
        assert result["session_id"] == "test"
        assert result["role"] == "user"
        assert result["content"] == "Test"
        assert result["tool_name"] == "test_tool"
        assert result["tool_args"] == {"key": "value"}
        assert result["metadata"] == {"meta": "data"}

    def test_to_dict_with_none_fields(self):
        """Test to_dict with None optional fields."""
        memory = Memory(
            id=None,
            timestamp=datetime.now(),
            session_id="test",
            role="user",
            content="Test",
            embedding=None,
        )
        result = memory.to_dict()

        assert result["id"] is None
        assert result["tool_name"] is None
        assert result["tool_args"] is None
        assert result["metadata"] is None


class TestMemoryStore:
    """Tests for MemoryStore class."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary memory store."""
        db_path = tmp_path / "test_memory.db"
        return MemoryStore(db_path=db_path)

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory."""
        return Memory(
            id=None,
            timestamp=datetime.now(),
            session_id="test-session",
            role="user",
            content="Test content",
            embedding=[0.1, 0.2, 0.3],
        )

    def test_init_creates_db_path(self, tmp_path):
        """Test initialization creates database directory."""
        db_path = tmp_path / "subdir" / "memory.db"
        store = MemoryStore(db_path=db_path)
        assert db_path.parent.exists()

    def test_init_creates_tables(self, store):
        """Test initialization creates required tables."""
        import sqlite3

        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
            )
            assert cursor.fetchone() is not None

    def test_add_memory(self, store, sample_memory):
        """Test adding a memory."""
        memory_id = store.add(sample_memory)
        assert memory_id is not None
        assert memory_id > 0

    def test_add_memory_returns_id(self, store, sample_memory):
        """Test add returns incrementing IDs."""
        id1 = store.add(sample_memory)
        id2 = store.add(sample_memory)
        assert id2 > id1

    def test_get_memory(self, store, sample_memory):
        """Test getting a memory by ID."""
        memory_id = store.add(sample_memory)
        retrieved = store.get(memory_id)

        assert retrieved is not None
        assert retrieved.id == memory_id
        assert retrieved.content == sample_memory.content
        assert retrieved.session_id == sample_memory.session_id

    def test_get_memory_not_found(self, store):
        """Test getting non-existent memory."""
        result = store.get(99999)
        assert result is None

    def test_get_recent(self, store):
        """Test getting recent memories."""
        # Add multiple memories
        for i in range(5):
            memory = Memory(
                id=None,
                timestamp=datetime.now(),
                session_id="test",
                role="user",
                content=f"Content {i}",
                embedding=None,
            )
            store.add(memory)

        recent = store.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_recent_by_session(self, store):
        """Test getting recent memories filtered by session."""
        # Add memories to different sessions
        for session_id in ["session-1", "session-1", "session-2"]:
            memory = Memory(
                id=None,
                timestamp=datetime.now(),
                session_id=session_id,
                role="user",
                content="Test",
                embedding=None,
            )
            store.add(memory)

        recent = store.get_recent(limit=10, session_id="session-1")
        assert len(recent) == 2
        assert all(m.session_id == "session-1" for m in recent)

    def test_get_session_history(self, store):
        """Test getting session history."""
        # Add memories to a session
        for i in range(3):
            memory = Memory(
                id=None,
                timestamp=datetime.now(),
                session_id="test-session",
                role="user",
                content=f"Message {i}",
                embedding=None,
            )
            store.add(memory)

        history = store.get_session_history("test-session")
        assert len(history) == 3

    def test_get_session_history_chronological(self, store):
        """Test session history is in chronological order."""
        from datetime import timedelta

        base_time = datetime.now()

        for i in range(3):
            memory = Memory(
                id=None,
                timestamp=base_time + timedelta(seconds=i),
                session_id="test-session",
                role="user",
                content=f"Message {i}",
                embedding=None,
            )
            store.add(memory)

        history = store.get_session_history("test-session")
        # Should be in chronological order (ASC)
        for i, mem in enumerate(history):
            assert f"Message {i}" in mem.content

    def test_search_text(self, store):
        """Test text search."""
        # Add memories with different content
        contents = ["Hello world", "Goodbye world", "Hello friend"]
        for content in contents:
            memory = Memory(
                id=None,
                timestamp=datetime.now(),
                session_id="test",
                role="user",
                content=content,
                embedding=None,
            )
            store.add(memory)

        results = store.search_text("Hello")
        assert len(results) == 2

    def test_search_text_no_results(self, store):
        """Test text search with no matches."""
        memory = Memory(
            id=None,
            timestamp=datetime.now(),
            session_id="test",
            role="user",
            content="Test content",
            embedding=None,
        )
        store.add(memory)

        results = store.search_text("nonexistent")
        assert len(results) == 0

    def test_search_semantic(self, store):
        """Test semantic search with embeddings."""
        # Add memories with embeddings
        embeddings = [
            [1.0, 0.0, 0.0],  # Similar to query
            [0.9, 0.1, 0.0],  # Also similar
            [0.0, 1.0, 0.0],  # Different
        ]

        for i, emb in enumerate(embeddings):
            memory = Memory(
                id=None,
                timestamp=datetime.now(),
                session_id="test",
                role="user",
                content=f"Content {i}",
                embedding=emb,
            )
            store.add(memory)

        # Search with similar embedding
        query = [1.0, 0.0, 0.0]
        results = store.search_semantic(query, limit=2, min_similarity=0.5)

        assert len(results) >= 1
        # First result should be most similar
        memory, similarity = results[0]
        assert similarity > 0.9

    def test_search_semantic_exclude_session(self, store):
        """Test semantic search excluding a session."""
        embedding = [1.0, 0.0, 0.0]

        # Add memory to excluded session
        excluded = Memory(
            id=None,
            timestamp=datetime.now(),
            session_id="excluded-session",
            role="user",
            content="Excluded",
            embedding=embedding,
        )
        store.add(excluded)

        # Add memory to other session
        included = Memory(
            id=None,
            timestamp=datetime.now(),
            session_id="other-session",
            role="user",
            content="Included",
            embedding=embedding,
        )
        store.add(included)

        results = store.search_semantic(
            embedding, limit=10, min_similarity=0.5, exclude_session="excluded-session"
        )

        assert all(m.session_id != "excluded-session" for m, _ in results)

    def test_search_semantic_min_similarity(self, store):
        """Test semantic search respects min_similarity threshold."""
        # Add memory with orthogonal embedding
        memory = Memory(
            id=None,
            timestamp=datetime.now(),
            session_id="test",
            role="user",
            content="Test",
            embedding=[0.0, 1.0, 0.0],
        )
        store.add(memory)

        # Search with different direction
        query = [1.0, 0.0, 0.0]
        results = store.search_semantic(query, min_similarity=0.9)

        # Should not find anything due to high threshold
        assert len(results) == 0

    def test_get_stats(self, store):
        """Test getting store statistics."""
        # Add some memories
        for i in range(5):
            embedding = [0.1, 0.2, 0.3] if i < 3 else None
            memory = Memory(
                id=None,
                timestamp=datetime.now(),
                session_id=f"session-{i % 2}",
                role="user",
                content=f"Content {i}",
                embedding=embedding,
            )
            store.add(memory)

        stats = store.get_stats()

        assert stats["total_memories"] == 5
        assert stats["total_sessions"] == 2
        assert stats["memories_with_embeddings"] == 3

    def test_get_stats_empty_store(self, store):
        """Test stats on empty store."""
        stats = store.get_stats()

        assert stats["total_memories"] == 0
        assert stats["total_sessions"] == 0
        assert stats["memories_with_embeddings"] == 0

    def test_serialize_embedding(self, store):
        """Test embedding serialization."""
        embedding = [0.1, 0.2, 0.3]
        serialized = store._serialize_embedding(embedding)

        assert serialized is not None
        assert isinstance(serialized, bytes)

    def test_serialize_embedding_none(self, store):
        """Test serializing None embedding."""
        result = store._serialize_embedding(None)
        assert result is None

    def test_deserialize_embedding(self, store):
        """Test embedding deserialization."""
        original = [0.1, 0.2, 0.3]
        serialized = store._serialize_embedding(original)
        deserialized = store._deserialize_embedding(serialized)

        assert deserialized is not None
        np.testing.assert_array_almost_equal(deserialized, original, decimal=5)

    def test_deserialize_embedding_none(self, store):
        """Test deserializing None."""
        result = store._deserialize_embedding(None)
        assert result is None

    def test_row_to_memory(self, store, sample_memory):
        """Test converting database row to Memory."""
        memory_id = store.add(sample_memory)
        retrieved = store.get(memory_id)

        assert isinstance(retrieved, Memory)
        assert retrieved.id == memory_id

    def test_memory_with_tool_args(self, store):
        """Test storing memory with tool arguments."""
        memory = Memory(
            id=None,
            timestamp=datetime.now(),
            session_id="test",
            role="tool_result",
            content="Result",
            embedding=None,
            tool_name="filesystem",
            tool_args={"path": "/tmp", "recursive": True},
            metadata={"success": True, "count": 5},
        )

        memory_id = store.add(memory)
        retrieved = store.get(memory_id)

        assert retrieved.tool_name == "filesystem"
        assert retrieved.tool_args == {"path": "/tmp", "recursive": True}
        assert retrieved.metadata == {"success": True, "count": 5}
