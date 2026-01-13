"""Tests for the session persistence module."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from mother.agent.session import Session, SessionStore


class TestSession:
    """Tests for Session dataclass."""

    def test_creation(self):
        """Test session creation."""
        now = datetime.now()
        session = Session(
            id="session-1",
            created_at=now,
            updated_at=now,
        )

        assert session.id == "session-1"
        assert session.created_at == now
        assert session.updated_at == now
        assert session.messages == []
        assert session.metadata == {}
        assert session.summary is None
        assert session.status == "active"

    def test_with_messages(self):
        """Test session with messages."""
        now = datetime.now()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        session = Session(
            id="session-1",
            created_at=now,
            updated_at=now,
            messages=messages,
        )

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime.now()
        session = Session(
            id="session-1",
            created_at=now,
            updated_at=now,
            messages=[{"role": "user", "content": "Test"}],
            metadata={"key": "value"},
            summary="Test session",
            status="completed",
        )

        result = session.to_dict()

        assert result["id"] == "session-1"
        assert result["created_at"] == now.isoformat()
        assert result["messages"] == [{"role": "user", "content": "Test"}]
        assert result["metadata"] == {"key": "value"}
        assert result["summary"] == "Test session"
        assert result["status"] == "completed"

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        now = datetime.now()
        data = {
            "id": "session-1",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "messages": [{"role": "user", "content": "Test"}],
            "metadata": {"key": "value"},
            "summary": "Test session",
            "status": "completed",
        }

        session = Session.from_dict(data)

        assert session.id == "session-1"
        assert session.messages == [{"role": "user", "content": "Test"}]
        assert session.metadata == {"key": "value"}
        assert session.summary == "Test session"
        assert session.status == "completed"


class TestSessionStore:
    """Tests for SessionStore."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_sessions.db"
            yield db_path

    def test_initialization(self, temp_db):
        """Test session store initialization."""
        store = SessionStore(db_path=temp_db)

        assert store.db_path == temp_db
        assert temp_db.exists()

    def test_save_and_get(self, temp_db):
        """Test saving and retrieving a session."""
        store = SessionStore(db_path=temp_db)
        now = datetime.now()

        session = Session(
            id="test-session",
            created_at=now,
            updated_at=now,
            messages=[{"role": "user", "content": "Hello"}],
            metadata={"tool_count": 5},
        )

        store.save(session)
        retrieved = store.get("test-session")

        assert retrieved is not None
        assert retrieved.id == "test-session"
        assert len(retrieved.messages) == 1
        assert retrieved.metadata == {"tool_count": 5}

    def test_get_nonexistent(self, temp_db):
        """Test getting a nonexistent session."""
        store = SessionStore(db_path=temp_db)

        result = store.get("nonexistent")

        assert result is None

    def test_update_session(self, temp_db):
        """Test updating an existing session."""
        store = SessionStore(db_path=temp_db)
        now = datetime.now()

        # Create initial session
        session = Session(
            id="test-session",
            created_at=now,
            updated_at=now,
            messages=[{"role": "user", "content": "Hello"}],
        )
        store.save(session)

        # Update with more messages
        session.messages.append({"role": "assistant", "content": "Hi!"})
        store.save(session)

        retrieved = store.get("test-session")
        assert len(retrieved.messages) == 2

    def test_get_recent(self, temp_db):
        """Test getting recent sessions."""
        store = SessionStore(db_path=temp_db)

        # Create multiple sessions
        for i in range(5):
            now = datetime.now()
            session = Session(
                id=f"session-{i}",
                created_at=now,
                updated_at=now,
            )
            store.save(session)

        recent = store.get_recent(limit=3)

        assert len(recent) == 3

    def test_get_recent_by_status(self, temp_db):
        """Test getting recent sessions by status."""
        store = SessionStore(db_path=temp_db)

        # Create sessions with different statuses
        now = datetime.now()
        for i, status in enumerate(["active", "active", "completed", "active"]):
            session = Session(
                id=f"session-{i}",
                created_at=now,
                updated_at=now,
                status=status,
            )
            store.save(session)

        active_sessions = store.get_recent(limit=10, status="active")
        completed_sessions = store.get_recent(limit=10, status="completed")

        assert len(active_sessions) == 3
        assert len(completed_sessions) == 1

    def test_delete(self, temp_db):
        """Test deleting a session."""
        store = SessionStore(db_path=temp_db)
        now = datetime.now()

        session = Session(
            id="to-delete",
            created_at=now,
            updated_at=now,
        )
        store.save(session)

        # Verify it exists
        assert store.get("to-delete") is not None

        # Delete it
        result = store.delete("to-delete")
        assert result is True

        # Verify it's gone
        assert store.get("to-delete") is None

    def test_delete_nonexistent(self, temp_db):
        """Test deleting a nonexistent session."""
        store = SessionStore(db_path=temp_db)

        result = store.delete("nonexistent")

        assert result is False

    def test_get_stats(self, temp_db):
        """Test getting session statistics."""
        store = SessionStore(db_path=temp_db)

        # Create some sessions
        now = datetime.now()
        for i in range(3):
            session = Session(
                id=f"session-{i}",
                created_at=now,
                updated_at=now,
                messages=[{"role": "user", "content": f"Message {i}"}] * (i + 1),
                status="active" if i < 2 else "completed",
            )
            store.save(session)

        stats = store.get_stats()

        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 2
        assert stats["avg_messages_per_session"] > 0

    def test_empty_stats(self, temp_db):
        """Test statistics on empty store."""
        store = SessionStore(db_path=temp_db)

        stats = store.get_stats()

        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0

    def test_session_with_complex_metadata(self, temp_db):
        """Test session with complex metadata."""
        store = SessionStore(db_path=temp_db)
        now = datetime.now()

        session = Session(
            id="complex-session",
            created_at=now,
            updated_at=now,
            metadata={
                "cognitive": {
                    "current_goal": "Test goal",
                    "sub_goals": ["sub1", "sub2"],
                    "confidence": "high",
                },
                "tool_count": 10,
                "nested": {"deep": {"value": True}},
            },
        )
        store.save(session)

        retrieved = store.get("complex-session")

        assert retrieved.metadata["cognitive"]["current_goal"] == "Test goal"
        assert retrieved.metadata["cognitive"]["sub_goals"] == ["sub1", "sub2"]
        assert retrieved.metadata["nested"]["deep"]["value"] is True

    def test_concurrent_access(self, temp_db):
        """Test that multiple saves don't corrupt data."""
        store = SessionStore(db_path=temp_db)
        now = datetime.now()

        # Save same session multiple times
        session = Session(
            id="concurrent-session",
            created_at=now,
            updated_at=now,
            messages=[],
        )

        for i in range(10):
            session.messages.append({"role": "user", "content": f"Message {i}"})
            store.save(session)

        retrieved = store.get("concurrent-session")
        assert len(retrieved.messages) == 10
