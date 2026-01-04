"""Tests for API request/response schemas."""

import pytest
from pydantic import ValidationError

from mother.api.schemas import (
    CommandRequest,
    CommandResponse,
    ConfirmRequest,
    ErrorResponse,
    MemoryItem,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryStatsResponse,
    PendingConfirmationResponse,
    PlanApproveRequest,
    PlanCommandRequest,
    PlanCommandResponse,
    PlanResponse,
    PlanStepResponse,
    StatusResponse,
    ToolCall,
    ToolDetailResponse,
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolInfo,
    ToolListResponse,
)


class TestCommandRequest:
    """Tests for CommandRequest schema."""

    def test_minimal_request(self) -> None:
        """Test minimal request with just command."""
        request = CommandRequest(command="list files")
        assert request.command == "list files"
        assert request.session_id is None
        assert request.pre_confirmed is False

    def test_full_request(self) -> None:
        """Test request with all fields."""
        request = CommandRequest(
            command="delete file",
            session_id="session-123",
            pre_confirmed=True,
        )
        assert request.command == "delete file"
        assert request.session_id == "session-123"
        assert request.pre_confirmed is True

    def test_command_required(self) -> None:
        """Test that command is required."""
        with pytest.raises(ValidationError):
            CommandRequest()


class TestConfirmRequest:
    """Tests for ConfirmRequest schema."""

    def test_confirm_request(self) -> None:
        """Test confirmation request."""
        request = ConfirmRequest(confirmation_id="confirm-123")
        assert request.confirmation_id == "confirm-123"

    def test_id_required(self) -> None:
        """Test that confirmation_id is required."""
        with pytest.raises(ValidationError):
            ConfirmRequest()


class TestToolCall:
    """Tests for ToolCall schema."""

    def test_tool_call(self) -> None:
        """Test tool call schema."""
        call = ToolCall(
            tool="filesystem",
            args={"path": "/tmp"},
            success=True,
            execution_time=0.5,
        )
        assert call.tool == "filesystem"
        assert call.args == {"path": "/tmp"}
        assert call.success is True
        assert call.execution_time == 0.5

    def test_default_args(self) -> None:
        """Test default empty args."""
        call = ToolCall(tool="test", success=True, execution_time=0.1)
        assert call.args == {}


class TestPendingConfirmationResponse:
    """Tests for PendingConfirmationResponse schema."""

    def test_pending_confirmation(self) -> None:
        """Test pending confirmation response."""
        response = PendingConfirmationResponse(
            id="pending-123",
            tool_name="filesystem",
            command="delete",
            args={"path": "/tmp/file"},
            description="Delete file /tmp/file",
        )
        assert response.id == "pending-123"
        assert response.tool_name == "filesystem"
        assert response.command == "delete"


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_minimal_error(self) -> None:
        """Test minimal error response."""
        error = ErrorResponse(category="validation", message="Invalid input")
        assert error.category == "validation"
        assert error.message == "Invalid input"
        assert error.tool_name is None
        assert error.recoverable is True

    def test_full_error(self) -> None:
        """Test full error response."""
        error = ErrorResponse(
            category="execution",
            message="Command failed",
            tool_name="shell",
            command="rm -rf",
            recoverable=False,
            suggestion="Check permissions",
        )
        assert error.tool_name == "shell"
        assert error.recoverable is False
        assert error.suggestion == "Check permissions"


class TestCommandResponse:
    """Tests for CommandResponse schema."""

    def test_success_response(self) -> None:
        """Test successful command response."""
        response = CommandResponse(
            success=True,
            response="Files listed",
            session_id="session-123",
        )
        assert response.success is True
        assert response.response == "Files listed"
        assert response.tool_calls == []
        assert response.errors == []

    def test_response_with_tool_calls(self) -> None:
        """Test response with tool calls."""
        tool_call = ToolCall(tool="ls", success=True, execution_time=0.1)
        response = CommandResponse(
            success=True,
            response="Done",
            session_id="s1",
            tool_calls=[tool_call],
        )
        assert len(response.tool_calls) == 1

    def test_response_with_pending(self) -> None:
        """Test response with pending confirmation."""
        pending = PendingConfirmationResponse(
            id="p1",
            tool_name="shell",
            command="rm",
            args={},
            description="Delete",
        )
        response = CommandResponse(
            success=True,
            response="Pending",
            session_id="s1",
            pending_confirmation=pending,
        )
        assert response.pending_confirmation is not None


class TestToolInfo:
    """Tests for ToolInfo schema."""

    def test_tool_info(self) -> None:
        """Test tool info schema."""
        info = ToolInfo(
            name="filesystem",
            description="File operations",
            commands=["read", "write", "delete"],
        )
        assert info.name == "filesystem"
        assert len(info.commands) == 3


class TestToolListResponse:
    """Tests for ToolListResponse schema."""

    def test_tool_list(self) -> None:
        """Test tool list response."""
        tools = [
            ToolInfo(name="fs", description="Files", commands=["read"]),
            ToolInfo(name="shell", description="Shell", commands=["run"]),
        ]
        response = ToolListResponse(tools=tools)
        assert len(response.tools) == 2


class TestToolDetailResponse:
    """Tests for ToolDetailResponse schema."""

    def test_tool_detail(self) -> None:
        """Test tool detail response."""
        response = ToolDetailResponse(
            name="filesystem",
            description="File operations",
            commands={
                "read": {"params": ["path"]},
                "write": {"params": ["path", "content"]},
            },
        )
        assert response.name == "filesystem"
        assert "read" in response.commands


class TestToolExecuteRequest:
    """Tests for ToolExecuteRequest schema."""

    def test_execute_request(self) -> None:
        """Test tool execute request."""
        request = ToolExecuteRequest(args={"path": "/tmp"})
        assert request.args == {"path": "/tmp"}

    def test_default_args(self) -> None:
        """Test default empty args."""
        request = ToolExecuteRequest()
        assert request.args == {}


class TestToolExecuteResponse:
    """Tests for ToolExecuteResponse schema."""

    def test_success_response(self) -> None:
        """Test successful execution response."""
        response = ToolExecuteResponse(
            success=True,
            exit_code=0,
            output={"result": "done"},
            execution_time=0.5,
        )
        assert response.success is True
        assert response.exit_code == 0
        assert response.error is None

    def test_error_response(self) -> None:
        """Test error execution response."""
        response = ToolExecuteResponse(
            success=False,
            exit_code=1,
            output=None,
            error="Command failed",
            execution_time=0.1,
        )
        assert response.success is False
        assert response.error == "Command failed"


class TestStatusResponse:
    """Tests for StatusResponse schema."""

    def test_status_response(self) -> None:
        """Test status response."""
        response = StatusResponse(
            status="running",
            version="1.0.0",
            available_tools=5,
            model="claude-3",
        )
        assert response.status == "running"
        assert response.version == "1.0.0"
        assert response.memory_stats is None


class TestMemorySearchRequest:
    """Tests for MemorySearchRequest schema."""

    def test_search_request(self) -> None:
        """Test memory search request."""
        request = MemorySearchRequest(query="previous discussion")
        assert request.query == "previous discussion"
        assert request.limit == 10

    def test_custom_limit(self) -> None:
        """Test custom limit."""
        request = MemorySearchRequest(query="test", limit=5)
        assert request.limit == 5


class TestMemoryItem:
    """Tests for MemoryItem schema."""

    def test_memory_item(self) -> None:
        """Test memory item schema."""
        item = MemoryItem(
            content="Test message",
            role="user",
            timestamp="2024-01-01T00:00:00Z",
        )
        assert item.content == "Test message"
        assert item.similarity is None

    def test_with_similarity(self) -> None:
        """Test memory item with similarity."""
        item = MemoryItem(
            content="Test",
            role="assistant",
            timestamp="2024-01-01T00:00:00Z",
            similarity=0.95,
        )
        assert item.similarity == 0.95


class TestMemorySearchResponse:
    """Tests for MemorySearchResponse schema."""

    def test_search_response(self) -> None:
        """Test memory search response."""
        items = [
            MemoryItem(content="Test", role="user", timestamp="2024-01-01T00:00:00Z"),
        ]
        response = MemorySearchResponse(results=items, total=1)
        assert len(response.results) == 1
        assert response.total == 1


class TestMemoryStatsResponse:
    """Tests for MemoryStatsResponse schema."""

    def test_stats_response(self) -> None:
        """Test memory stats response."""
        response = MemoryStatsResponse(
            total_memories=100,
            total_sessions=10,
            memories_with_embeddings=80,
        )
        assert response.total_memories == 100


class TestPlanStepResponse:
    """Tests for PlanStepResponse schema."""

    def test_plan_step(self) -> None:
        """Test plan step schema."""
        step = PlanStepResponse(
            order=1,
            tool_name="filesystem",
            command="read",
            args={"path": "/tmp"},
            description="Read file",
            status="pending",
        )
        assert step.order == 1
        assert step.depends_on == []


class TestPlanResponse:
    """Tests for PlanResponse schema."""

    def test_plan_response(self) -> None:
        """Test plan response."""
        step = PlanStepResponse(
            order=1,
            tool_name="fs",
            command="read",
            args={},
            description="Read",
            status="pending",
        )
        response = PlanResponse(
            id="plan-123",
            goal="Read and process file",
            steps=[step],
            status="pending",
            created_at="2024-01-01T00:00:00Z",
        )
        assert response.id == "plan-123"
        assert len(response.steps) == 1


class TestPlanCommandRequest:
    """Tests for PlanCommandRequest schema."""

    def test_plan_request(self) -> None:
        """Test plan command request."""
        request = PlanCommandRequest(command="analyze logs")
        assert request.command == "analyze logs"
        assert request.session_id is None


class TestPlanCommandResponse:
    """Tests for PlanCommandResponse schema."""

    def test_plan_command_response(self) -> None:
        """Test plan command response."""
        response = PlanCommandResponse(
            success=True,
            response="Plan created",
            session_id="s1",
        )
        assert response.success is True
        assert response.plan is None
        assert response.tool_calls == []


class TestPlanApproveRequest:
    """Tests for PlanApproveRequest schema."""

    def test_approve_request(self) -> None:
        """Test plan approve request."""
        request = PlanApproveRequest(approve=True)
        assert request.approve is True

    def test_reject_request(self) -> None:
        """Test plan reject request."""
        request = PlanApproveRequest(approve=False)
        assert request.approve is False
