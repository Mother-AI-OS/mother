"""Tests for the memory manager module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from mother.memory.manager import MemoryManager
from mother.memory.store import Memory


class TestMemoryManager:
    """Tests for MemoryManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a memory manager with mocked embeddings."""
        with patch("mother.memory.manager.MemoryStore") as mock_store_class:
            with patch("mother.memory.manager.EmbeddingGenerator") as mock_embeddings_class:
                # Setup mock store
                mock_store = MagicMock()
                mock_store_class.return_value = mock_store

                # Setup mock embeddings
                mock_embeddings = MagicMock()
                mock_embeddings.generate.return_value = [0.1, 0.2, 0.3]
                mock_embeddings_class.return_value = mock_embeddings

                mgr = MemoryManager(openai_api_key="test-key")
                mgr._mock_store = mock_store
                mgr._mock_embeddings = mock_embeddings
                return mgr

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager.store is not None
        assert manager.embeddings is not None

    def test_remember_basic(self, manager):
        """Test basic remember functionality."""
        manager._mock_store.add.return_value = 1

        memory_id = manager.remember(
            session_id="session-1",
            role="user",
            content="Hello world",
        )

        assert memory_id == 1
        manager._mock_store.add.assert_called_once()

    def test_remember_generates_embedding(self, manager):
        """Test remember generates embedding by default."""
        manager._mock_store.add.return_value = 1

        manager.remember(
            session_id="test",
            role="user",
            content="Test content",
        )

        manager._mock_embeddings.generate.assert_called_with("Test content")

    def test_remember_skip_embedding(self, manager):
        """Test remember can skip embedding generation."""
        manager._mock_store.add.return_value = 1

        manager.remember(
            session_id="test",
            role="user",
            content="Test",
            generate_embedding=False,
        )

        manager._mock_embeddings.generate.assert_not_called()

    def test_remember_with_tool_info(self, manager):
        """Test remember with tool name and args."""
        manager._mock_store.add.return_value = 1

        manager.remember(
            session_id="test",
            role="tool_result",
            content="Result",
            tool_name="filesystem",
            tool_args={"path": "/tmp"},
        )

        call_args = manager._mock_store.add.call_args[0][0]
        assert call_args.tool_name == "filesystem"
        assert call_args.tool_args == {"path": "/tmp"}

    def test_remember_with_metadata(self, manager):
        """Test remember with metadata."""
        manager._mock_store.add.return_value = 1

        manager.remember(
            session_id="test",
            role="assistant",
            content="Response",
            metadata={"tokens": 100},
        )

        call_args = manager._mock_store.add.call_args[0][0]
        assert call_args.metadata == {"tokens": 100}

    def test_remember_user_input(self, manager):
        """Test remember_user_input convenience method."""
        manager._mock_store.add.return_value = 1

        memory_id = manager.remember_user_input("session-1", "Hello")

        assert memory_id == 1
        call_args = manager._mock_store.add.call_args[0][0]
        assert call_args.role == "user"
        assert call_args.content == "Hello"

    def test_remember_assistant_response(self, manager):
        """Test remember_assistant_response convenience method."""
        manager._mock_store.add.return_value = 1

        memory_id = manager.remember_assistant_response("session-1", "Response", tool_calls=[{"name": "test"}])

        assert memory_id == 1
        call_args = manager._mock_store.add.call_args[0][0]
        assert call_args.role == "assistant"
        assert call_args.metadata == {"tool_calls": [{"name": "test"}]}

    def test_remember_assistant_response_no_tools(self, manager):
        """Test remember_assistant_response without tool calls."""
        manager._mock_store.add.return_value = 1

        manager.remember_assistant_response("session-1", "Response")

        call_args = manager._mock_store.add.call_args[0][0]
        assert call_args.metadata is None

    def test_remember_tool_result(self, manager):
        """Test remember_tool_result convenience method."""
        manager._mock_store.add.return_value = 1

        memory_id = manager.remember_tool_result(
            session_id="session-1",
            tool_name="filesystem",
            tool_args={"path": "/tmp"},
            result="Files listed",
            success=True,
        )

        assert memory_id == 1
        call_args = manager._mock_store.add.call_args[0][0]
        assert call_args.role == "tool_result"
        assert call_args.tool_name == "filesystem"
        assert call_args.metadata == {"success": True}

    def test_remember_tool_result_truncates_long_content(self, manager):
        """Test tool result content is truncated."""
        manager._mock_store.add.return_value = 1
        long_result = "x" * 5000

        manager.remember_tool_result(
            session_id="session-1",
            tool_name="test",
            tool_args={},
            result=long_result,
        )

        call_args = manager._mock_store.add.call_args[0][0]
        assert len(call_args.content) <= 2000

    def test_recall(self, manager):
        """Test recall method."""
        mock_memory = Memory(
            id=1,
            timestamp=datetime.now(),
            session_id="old-session",
            role="user",
            content="Past content",
            embedding=[0.1, 0.2, 0.3],
        )
        manager._mock_store.search_semantic.return_value = [(mock_memory, 0.85)]

        results = manager.recall("query", limit=5)

        assert len(results) == 1
        assert results[0]["similarity"] == 0.85
        assert results[0]["content"] == "Past content"

    def test_recall_no_embedding(self, manager):
        """Test recall when embedding generation fails."""
        manager._mock_embeddings.generate.return_value = None

        results = manager.recall("query")

        assert results == []

    def test_recall_with_exclude_session(self, manager):
        """Test recall excludes specified session."""
        manager._mock_store.search_semantic.return_value = []

        manager.recall("query", exclude_session="current-session")

        manager._mock_store.search_semantic.assert_called_once()
        call_kwargs = manager._mock_store.search_semantic.call_args[1]
        assert call_kwargs["exclude_session"] == "current-session"

    def test_get_context_for_query(self, manager):
        """Test get_context_for_query method."""
        mock_memory = Memory(
            id=1,
            timestamp=datetime.now(),
            session_id="past-session",
            role="user",
            content="Relevant past content",
            embedding=[0.1, 0.2, 0.3],
        )
        manager._mock_store.search_semantic.return_value = [(mock_memory, 0.8)]
        manager._mock_store.get_recent.return_value = []

        context = manager.get_context_for_query(
            query="test query",
            current_session_id="current-session",
        )

        assert "Relevant Past Context" in context
        assert "Relevant past content" in context

    def test_get_context_for_query_no_results(self, manager):
        """Test get_context_for_query with no relevant memories."""
        manager._mock_store.search_semantic.return_value = []
        manager._mock_store.get_recent.return_value = []

        context = manager.get_context_for_query(
            query="test query",
            current_session_id="current-session",
        )

        assert context == ""

    def test_get_context_for_query_with_recent(self, manager):
        """Test get_context_for_query includes recent memories."""
        manager._mock_store.search_semantic.return_value = []

        recent_memory = Memory(
            id=2,
            timestamp=datetime.now(),
            session_id="other-session",
            role="assistant",
            content="Recent activity",
            embedding=None,
        )
        manager._mock_store.get_recent.return_value = [recent_memory]

        context = manager.get_context_for_query(
            query="test",
            current_session_id="current",
            include_recent=True,
        )

        assert "Recent Activity" in context

    def test_get_context_for_query_excludes_current_session(self, manager):
        """Test recent memories exclude current session."""
        manager._mock_store.search_semantic.return_value = []

        # Memory from current session should be excluded
        current_memory = Memory(
            id=1,
            timestamp=datetime.now(),
            session_id="current",
            role="user",
            content="Current session content",
            embedding=None,
        )
        manager._mock_store.get_recent.return_value = [current_memory]

        context = manager.get_context_for_query(
            query="test",
            current_session_id="current",
            include_recent=True,
        )

        # Should not include current session content in recent
        assert "Current session content" not in context or "Recent Activity" not in context

    def test_get_session_summary(self, manager):
        """Test get_session_summary method."""
        memories = [
            Memory(
                id=1,
                timestamp=datetime.now(),
                session_id="session-1",
                role="user",
                content="Query 1",
                embedding=None,
            ),
            Memory(
                id=2,
                timestamp=datetime.now(),
                session_id="session-1",
                role="tool_result",
                content="Result",
                embedding=None,
                tool_name="filesystem",
            ),
        ]
        manager._mock_store.get_session_history.return_value = memories

        summary = manager.get_session_summary("session-1")

        assert summary is not None
        assert "1 queries" in summary
        assert "filesystem" in summary

    def test_get_session_summary_no_history(self, manager):
        """Test get_session_summary with no history."""
        manager._mock_store.get_session_history.return_value = []

        summary = manager.get_session_summary("nonexistent")

        assert summary is None

    def test_get_stats(self, manager):
        """Test get_stats method."""
        expected_stats = {
            "total_memories": 100,
            "total_sessions": 10,
            "memories_with_embeddings": 80,
        }
        manager._mock_store.get_stats.return_value = expected_stats

        stats = manager.get_stats()

        assert stats == expected_stats

    def test_search(self, manager):
        """Test search method."""
        mock_memories = [
            Memory(
                id=1,
                timestamp=datetime.now(),
                session_id="test",
                role="user",
                content="Search result",
                embedding=None,
            )
        ]
        manager._mock_store.search_text.return_value = mock_memories

        results = manager.search("query", limit=10)

        assert results == mock_memories
        manager._mock_store.search_text.assert_called_with("query", 10)
