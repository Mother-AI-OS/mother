"""Tests for the API routes module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from mother.api.routes import (
    get_agent,
    get_registry,
    init_dependencies,
)
from mother.api.schemas import (
    CommandRequest,
    ConfirmRequest,
    MemorySearchRequest,
    PlanApproveRequest,
    PlanCommandRequest,
    ToolExecuteRequest,
)


class TestInitDependencies:
    """Tests for init_dependencies function."""

    def test_sets_global_dependencies(self):
        """Test init_dependencies sets global variables."""
        mock_registry = MagicMock()
        mock_agent = MagicMock()

        init_dependencies(mock_registry, mock_agent)

        # Should not raise
        from mother.api import routes

        assert routes._registry == mock_registry
        assert routes._agent == mock_agent


class TestGetRegistry:
    """Tests for get_registry dependency."""

    def test_returns_registry_when_initialized(self):
        """Test returns registry when set."""
        mock_registry = MagicMock()

        from mother.api import routes

        routes._registry = mock_registry

        result = get_registry()
        assert result == mock_registry

    def test_raises_when_not_initialized(self):
        """Test raises HTTPException when not initialized."""
        from mother.api import routes

        routes._registry = None

        with pytest.raises(HTTPException) as exc_info:
            get_registry()

        assert exc_info.value.status_code == 500
        assert "not initialized" in exc_info.value.detail


class TestGetAgent:
    """Tests for get_agent dependency."""

    def test_returns_agent_when_initialized(self):
        """Test returns agent when set."""
        mock_agent = MagicMock()

        from mother.api import routes

        routes._agent = mock_agent

        result = get_agent()
        assert result == mock_agent

    def test_raises_when_not_initialized(self):
        """Test raises HTTPException when not initialized."""
        from mother.api import routes

        routes._agent = None

        with pytest.raises(HTTPException) as exc_info:
            get_agent()

        assert exc_info.value.status_code == 500
        assert "not initialized" in exc_info.value.detail


class TestExecuteCommandEndpoint:
    """Tests for POST /command endpoint."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent."""
        agent = MagicMock()
        agent.get_session_id.return_value = "test-session"
        return agent

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_agent, mock_registry):
        """Test successful command execution."""
        from mother.api.routes import execute_command

        # Setup mock response
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.text = "Command executed"
        mock_result.tool_calls = []
        mock_result.pending_confirmation = None
        mock_result.errors = []

        mock_agent.process_command = AsyncMock(return_value=mock_result)

        request = CommandRequest(command="test command")

        with patch("mother.api.routes.get_agent", return_value=mock_agent):
            response = await execute_command(request, "test-key", mock_agent)

        assert response.success is True
        assert response.response == "Command executed"

    @pytest.mark.asyncio
    async def test_execute_command_with_tool_calls(self, mock_agent):
        """Test command with tool calls."""
        from mother.api.routes import execute_command

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.text = "Done"
        mock_result.tool_calls = [
            {
                "tool": "filesystem",
                "args": {"path": "/tmp"},
                "success": True,
                "execution_time": 0.5,
            }
        ]
        mock_result.pending_confirmation = None
        mock_result.errors = []

        mock_agent.process_command = AsyncMock(return_value=mock_result)

        request = CommandRequest(command="list files")

        response = await execute_command(request, "test-key", mock_agent)

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool == "filesystem"

    @pytest.mark.asyncio
    async def test_execute_command_with_pending_confirmation(self, mock_agent):
        """Test command with pending confirmation."""
        from mother.api.routes import execute_command

        mock_confirmation = MagicMock()
        mock_confirmation.id = "confirm-123"
        mock_confirmation.tool_name = "filesystem"
        mock_confirmation.command = "delete"
        mock_confirmation.args = {"path": "/tmp/file"}
        mock_confirmation.description = "Delete file"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.text = "Needs confirmation"
        mock_result.tool_calls = []
        mock_result.pending_confirmation = mock_confirmation
        mock_result.errors = []

        mock_agent.process_command = AsyncMock(return_value=mock_result)

        request = CommandRequest(command="delete file")

        response = await execute_command(request, "test-key", mock_agent)

        assert response.pending_confirmation is not None
        assert response.pending_confirmation.id == "confirm-123"

    @pytest.mark.asyncio
    async def test_execute_command_with_errors(self, mock_agent):
        """Test command with errors."""
        from mother.agent.errors import ErrorCategory
        from mother.api.routes import execute_command

        mock_error = MagicMock()
        mock_error.category = ErrorCategory.TOOL_EXECUTION
        mock_error.message = "Tool failed"
        mock_error.tool_name = "test"
        mock_error.command = "run"
        mock_error.recoverable = True
        mock_error.suggestion = "Try again"

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.text = "Failed"
        mock_result.tool_calls = []
        mock_result.pending_confirmation = None
        mock_result.errors = [mock_error]

        mock_agent.process_command = AsyncMock(return_value=mock_result)

        request = CommandRequest(command="fail")

        response = await execute_command(request, "test-key", mock_agent)

        assert response.success is False
        assert len(response.errors) == 1

    @pytest.mark.asyncio
    async def test_execute_command_exception(self, mock_agent):
        """Test command execution with exception."""
        from mother.api.routes import execute_command

        mock_agent.process_command = AsyncMock(side_effect=ValueError("Test error"))

        request = CommandRequest(command="error")

        with pytest.raises(HTTPException) as exc_info:
            await execute_command(request, "test-key", mock_agent)

        assert exc_info.value.status_code == 500


class TestConfirmActionEndpoint:
    """Tests for POST /command/{session_id}/confirm endpoint."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent."""
        agent = MagicMock()
        agent.get_session_id.return_value = "test-session"
        return agent

    @pytest.mark.asyncio
    async def test_confirm_action_success(self, mock_agent):
        """Test successful action confirmation."""
        from mother.api.routes import confirm_action

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.text = "Action confirmed"
        mock_result.errors = []

        mock_agent.confirm_action = AsyncMock(return_value=mock_result)

        request = ConfirmRequest(confirmation_id="confirm-123")

        response = await confirm_action("test-session", request, "test-key", mock_agent)

        assert response.success is True
        mock_agent.confirm_action.assert_called_once_with("confirm-123")

    @pytest.mark.asyncio
    async def test_confirm_action_session_mismatch(self, mock_agent):
        """Test session ID mismatch."""
        from mother.api.routes import confirm_action

        mock_agent.get_session_id.return_value = "different-session"

        request = ConfirmRequest(confirmation_id="confirm-123")

        with pytest.raises(HTTPException) as exc_info:
            await confirm_action("test-session", request, "test-key", mock_agent)

        assert exc_info.value.status_code == 400
        assert "mismatch" in exc_info.value.detail.lower()


class TestListToolsEndpoint:
    """Tests for GET /tools endpoint."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        registry = MagicMock()
        registry.list_tools.return_value = {
            "filesystem": {
                "description": "File operations",
                "commands": ["read", "write", "list"],
            }
        }
        return registry

    @pytest.mark.asyncio
    async def test_list_tools(self, mock_registry):
        """Test listing tools."""
        from mother.api.routes import list_tools

        response = await list_tools("test-key", mock_registry)

        assert len(response.tools) == 1
        assert response.tools[0].name == "filesystem"
        assert response.tools[0].description == "File operations"


class TestGetToolDetailsEndpoint:
    """Tests for GET /tools/{tool_name} endpoint."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        registry = MagicMock()
        registry.get_tool_details.return_value = {
            "name": "filesystem",
            "description": "File operations",
            "commands": {"read": {"description": "Read file"}},
        }
        return registry

    @pytest.mark.asyncio
    async def test_get_tool_details(self, mock_registry):
        """Test getting tool details."""
        from mother.api.routes import get_tool_details

        response = await get_tool_details("filesystem", "test-key", mock_registry)

        assert response.name == "filesystem"
        mock_registry.get_tool_details.assert_called_once_with("filesystem")

    @pytest.mark.asyncio
    async def test_get_tool_details_not_found(self, mock_registry):
        """Test getting non-existent tool."""
        from mother.api.routes import get_tool_details

        mock_registry.get_tool_details.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_tool_details("nonexistent", "test-key", mock_registry)

        assert exc_info.value.status_code == 404


class TestExecuteToolDirectlyEndpoint:
    """Tests for POST /tools/{tool_name}/{command} endpoint."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        registry = MagicMock()
        return registry

    @pytest.mark.asyncio
    async def test_execute_tool_directly(self, mock_registry):
        """Test direct tool execution."""
        from mother.api.routes import execute_tool_directly

        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = ["read"]
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exit_code = 0
        mock_result.parsed_data = {"content": "file data"}
        mock_result.stdout = ""
        mock_result.error_message = None
        mock_result.execution_time = 0.1
        mock_wrapper.execute.return_value = mock_result

        mock_registry.get_wrapper.return_value = mock_wrapper

        request = ToolExecuteRequest(args={"path": "/tmp/file"})

        response = await execute_tool_directly("filesystem", "read", request, "test-key", mock_registry)

        assert response.success is True
        mock_wrapper.execute.assert_called_once_with("read", {"path": "/tmp/file"})

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, mock_registry):
        """Test executing non-existent tool."""
        from mother.api.routes import execute_tool_directly

        mock_registry.get_wrapper.return_value = None

        request = ToolExecuteRequest(args={})

        with pytest.raises(HTTPException) as exc_info:
            await execute_tool_directly("nonexistent", "cmd", request, "test-key", mock_registry)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_command_not_found(self, mock_registry):
        """Test executing non-existent command."""
        from mother.api.routes import execute_tool_directly

        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = ["read", "write"]
        mock_registry.get_wrapper.return_value = mock_wrapper

        request = ToolExecuteRequest(args={})

        with pytest.raises(HTTPException) as exc_info:
            await execute_tool_directly("filesystem", "invalid", request, "test-key", mock_registry)

        assert exc_info.value.status_code == 404
        assert "Command" in exc_info.value.detail


class TestGetStatusEndpoint:
    """Tests for GET /status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting status."""
        from mother.api.routes import get_status

        mock_registry = MagicMock()
        mock_registry.wrappers = {"tool1": MagicMock(), "tool2": MagicMock()}

        mock_agent = MagicMock()
        mock_agent.get_memory_stats.return_value = {"total_memories": 100}

        with patch("mother.api.routes.get_settings") as mock_settings:
            mock_settings.return_value.claude_model = "claude-sonnet-4"
            response = await get_status(mock_registry, mock_agent)

        assert response.status == "healthy"
        assert response.available_tools == 2


class TestMemoryStatsEndpoint:
    """Tests for GET /memory/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_memory_stats(self):
        """Test getting memory stats."""
        from mother.api.routes import get_memory_stats

        mock_agent = MagicMock()
        mock_agent.get_memory_stats.return_value = {
            "total_memories": 100,
            "total_sessions": 10,
            "memories_with_embeddings": 80,
        }

        response = await get_memory_stats("test-key", mock_agent)

        assert response.total_memories == 100
        assert response.total_sessions == 10
        assert response.memories_with_embeddings == 80

    @pytest.mark.asyncio
    async def test_get_memory_stats_not_enabled(self):
        """Test memory stats when not enabled."""
        from mother.api.routes import get_memory_stats

        mock_agent = MagicMock()
        mock_agent.get_memory_stats.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_memory_stats("test-key", mock_agent)

        assert exc_info.value.status_code == 404


class TestSearchMemoryEndpoint:
    """Tests for POST /memory/search endpoint."""

    @pytest.mark.asyncio
    async def test_search_memory(self):
        """Test memory search."""
        from mother.api.routes import search_memory

        mock_agent = MagicMock()
        mock_agent.search_memory.return_value = [
            {
                "content": "Test memory",
                "role": "user",
                "timestamp": datetime.now().isoformat(),
                "similarity": 0.9,
            }
        ]

        request = MemorySearchRequest(query="test", limit=10)

        response = await search_memory(request, "test-key", mock_agent)

        assert response.total == 1
        assert response.results[0].content == "Test memory"


class TestCreatePlanEndpoint:
    """Tests for POST /plan endpoint."""

    @pytest.mark.asyncio
    async def test_create_plan(self):
        """Test plan creation."""
        from mother.api.routes import create_plan

        mock_agent = MagicMock()
        mock_agent.get_session_id.return_value = "test-session"

        # Create mock plan
        mock_step = MagicMock()
        mock_step.order = 1
        mock_step.tool_name = "filesystem"
        mock_step.command = "read"
        mock_step.args = {"path": "/tmp"}
        mock_step.description = "Read file"
        mock_step.status.value = "pending"
        mock_step.depends_on = []

        mock_plan = MagicMock()
        mock_plan.id = "plan-123"
        mock_plan.goal = "Read and process file"
        mock_plan.steps = [mock_step]
        mock_plan.status = "pending"
        mock_plan.created_at = datetime.now().isoformat()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.text = "Plan created"
        mock_result.pending_plan = mock_plan
        mock_result.errors = []

        mock_agent.create_plan = AsyncMock(return_value=mock_result)

        request = PlanCommandRequest(command="process file")

        response = await create_plan(request, "test-key", mock_agent)

        assert response.success is True
        assert response.plan is not None
        assert response.plan.id == "plan-123"


class TestExecutePlanEndpoint:
    """Tests for POST /plan/{session_id}/execute endpoint."""

    @pytest.mark.asyncio
    async def test_execute_plan_approved(self):
        """Test executing approved plan."""
        from mother.api.routes import execute_plan

        mock_agent = MagicMock()
        mock_agent.get_session_id.return_value = "test-session"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.text = "Plan executed"
        mock_result.tool_calls = []
        mock_result.errors = []

        mock_agent.execute_plan = AsyncMock(return_value=mock_result)

        request = PlanApproveRequest(approve=True)

        response = await execute_plan("test-session", request, "test-key", mock_agent)

        assert response.success is True
        mock_agent.execute_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_plan_cancelled(self):
        """Test cancelling plan."""
        from mother.api.routes import execute_plan

        mock_agent = MagicMock()
        mock_agent.get_session_id.return_value = "test-session"
        mock_agent.state = MagicMock()
        mock_agent.state.pending_plan = MagicMock()

        request = PlanApproveRequest(approve=False)

        response = await execute_plan("test-session", request, "test-key", mock_agent)

        assert response.success is True
        assert "cancelled" in response.response.lower()
        assert mock_agent.state.pending_plan is None

    @pytest.mark.asyncio
    async def test_execute_plan_session_mismatch(self):
        """Test session mismatch."""
        from mother.api.routes import execute_plan

        mock_agent = MagicMock()
        mock_agent.get_session_id.return_value = "different-session"

        request = PlanApproveRequest(approve=True)

        with pytest.raises(HTTPException) as exc_info:
            await execute_plan("test-session", request, "test-key", mock_agent)

        assert exc_info.value.status_code == 400
