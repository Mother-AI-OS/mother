"""Tests for the agent core module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mother.agent.core import (
    AgentResponse,
    AgentState,
    ExecutionPlan,
    PendingConfirmation,
    PlanStep,
    PlanStepStatus,
)


class TestPlanStepStatus:
    """Tests for PlanStepStatus enum."""

    def test_pending_status(self):
        """Test pending status value."""
        assert PlanStepStatus.PENDING.value == "pending"

    def test_in_progress_status(self):
        """Test in_progress status value."""
        assert PlanStepStatus.IN_PROGRESS.value == "in_progress"

    def test_completed_status(self):
        """Test completed status value."""
        assert PlanStepStatus.COMPLETED.value == "completed"

    def test_failed_status(self):
        """Test failed status value."""
        assert PlanStepStatus.FAILED.value == "failed"

    def test_skipped_status(self):
        """Test skipped status value."""
        assert PlanStepStatus.SKIPPED.value == "skipped"


class TestPlanStep:
    """Tests for PlanStep dataclass."""

    def test_basic_creation(self):
        """Test creating a basic plan step."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="filesystem",
            command="list",
            args={"path": "/tmp"},
            description="List files in /tmp",
        )

        assert step.id == "step-1"
        assert step.order == 1
        assert step.tool_name == "filesystem"
        assert step.command == "list"
        assert step.args == {"path": "/tmp"}
        assert step.description == "List files in /tmp"

    def test_default_values(self):
        """Test default values for optional fields."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Test",
        )

        assert step.depends_on == []
        assert step.status == PlanStepStatus.PENDING
        assert step.result is None
        assert step.error is None

    def test_with_dependencies(self):
        """Test step with dependencies."""
        step = PlanStep(
            id="step-2",
            order=2,
            tool_name="web",
            command="fetch",
            args={"url": "https://example.com"},
            description="Fetch URL",
            depends_on=["step-1"],
        )

        assert step.depends_on == ["step-1"]

    def test_with_result(self):
        """Test step with result."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Test",
            status=PlanStepStatus.COMPLETED,
            result={"output": "success"},
        )

        assert step.status == PlanStepStatus.COMPLETED
        assert step.result == {"output": "success"}

    def test_with_error(self):
        """Test step with error."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Test",
            status=PlanStepStatus.FAILED,
            error="Something went wrong",
        )

        assert step.status == PlanStepStatus.FAILED
        assert step.error == "Something went wrong"


class TestExecutionPlan:
    """Tests for ExecutionPlan dataclass."""

    def test_basic_creation(self):
        """Test creating an execution plan."""
        step1 = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Step 1",
        )

        plan = ExecutionPlan(
            id="plan-1",
            goal="Complete test task",
            steps=[step1],
        )

        assert plan.id == "plan-1"
        assert plan.goal == "Complete test task"
        assert len(plan.steps) == 1

    def test_default_values(self):
        """Test default values."""
        plan = ExecutionPlan(
            id="plan-1",
            goal="Test",
            steps=[],
        )

        assert plan.status == "pending"
        # created_at should be an ISO format string
        assert isinstance(plan.created_at, str)

    def test_multiple_steps(self):
        """Test plan with multiple steps."""
        steps = [
            PlanStep(
                id=f"step-{i}",
                order=i,
                tool_name="test",
                command="run",
                args={},
                description=f"Step {i}",
            )
            for i in range(1, 4)
        ]

        plan = ExecutionPlan(
            id="plan-1",
            goal="Multi-step task",
            steps=steps,
        )

        assert len(plan.steps) == 3
        assert plan.steps[0].order == 1
        assert plan.steps[2].order == 3

    def test_to_display_pending(self):
        """Test plan display with pending steps."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="filesystem",
            command="list",
            args={"path": "/tmp"},
            description="List files",
            status=PlanStepStatus.PENDING,
        )

        plan = ExecutionPlan(
            id="plan-1",
            goal="List directory contents",
            steps=[step],
        )

        display = plan.to_display()

        assert "Execution Plan" in display
        assert "List directory contents" in display
        assert "List files" in display
        assert "filesystem_list" in display

    def test_to_display_completed(self):
        """Test plan display with completed steps."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Run test",
            status=PlanStepStatus.COMPLETED,
        )

        plan = ExecutionPlan(
            id="plan-1",
            goal="Run tests",
            steps=[step],
        )

        display = plan.to_display()
        # Should have checkmark for completed
        assert "Run test" in display

    def test_to_display_failed(self):
        """Test plan display with failed steps."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Failing step",
            status=PlanStepStatus.FAILED,
        )

        plan = ExecutionPlan(
            id="plan-1",
            goal="Will fail",
            steps=[step],
        )

        display = plan.to_display()
        assert "Failing step" in display

    def test_to_display_in_progress(self):
        """Test plan display with in progress steps."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Running step",
            status=PlanStepStatus.IN_PROGRESS,
        )

        plan = ExecutionPlan(
            id="plan-1",
            goal="In progress",
            steps=[step],
        )

        display = plan.to_display()
        assert "Running step" in display

    def test_to_display_skipped(self):
        """Test plan display with skipped steps."""
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Skipped step",
            status=PlanStepStatus.SKIPPED,
        )

        plan = ExecutionPlan(
            id="plan-1",
            goal="With skipped",
            steps=[step],
        )

        display = plan.to_display()
        assert "Skipped step" in display


class TestPendingConfirmation:
    """Tests for PendingConfirmation dataclass."""

    def test_creation(self):
        """Test creating a pending confirmation."""
        confirm = PendingConfirmation(
            id="confirm-1",
            tool_name="filesystem",
            command="delete",
            args={"path": "/tmp/test.txt"},
            description="Delete file",
        )

        assert confirm.id == "confirm-1"
        assert confirm.tool_name == "filesystem"
        assert confirm.command == "delete"
        assert confirm.args == {"path": "/tmp/test.txt"}
        assert confirm.description == "Delete file"


class TestAgentState:
    """Tests for AgentState dataclass."""

    def test_default_creation(self):
        """Test creating state with defaults."""
        state = AgentState()

        assert state.session_id is not None
        assert isinstance(state.session_id, str)
        assert state.messages == []
        assert state.tool_results == []
        assert state.pending_confirmation is None
        assert state.confirmed_actions == set()
        assert state.pending_plan is None
        assert state.current_plan is None

    def test_custom_session_id(self):
        """Test creating state with custom session ID."""
        state = AgentState(session_id="custom-123")
        assert state.session_id == "custom-123"

    def test_add_messages(self):
        """Test adding messages to state."""
        state = AgentState()
        state.messages.append({"role": "user", "content": "Hello"})
        state.messages.append({"role": "assistant", "content": "Hi!"})

        assert len(state.messages) == 2
        assert state.messages[0]["role"] == "user"
        assert state.messages[1]["role"] == "assistant"

    def test_confirmed_actions(self):
        """Test adding confirmed actions."""
        state = AgentState()
        state.confirmed_actions.add("action-1")
        state.confirmed_actions.add("action-2")

        assert "action-1" in state.confirmed_actions
        assert "action-2" in state.confirmed_actions
        assert len(state.confirmed_actions) == 2


class TestAgentResponse:
    """Tests for AgentResponse dataclass."""

    def test_basic_creation(self):
        """Test creating a basic response."""
        response = AgentResponse(text="Hello, world!")

        assert response.text == "Hello, world!"
        assert response.success is True
        assert response.tool_calls == []
        assert response.pending_confirmation is None
        assert response.pending_plan is None
        assert response.errors == []

    def test_with_tool_calls(self):
        """Test response with tool calls."""
        response = AgentResponse(
            text="Executed tool",
            tool_calls=[{"name": "test", "args": {}}],
        )

        assert len(response.tool_calls) == 1

    def test_with_pending_confirmation(self):
        """Test response with pending confirmation."""
        confirm = PendingConfirmation(
            id="c1",
            tool_name="test",
            command="delete",
            args={},
            description="Delete item",
        )

        response = AgentResponse(
            text="Please confirm",
            pending_confirmation=confirm,
        )

        assert response.pending_confirmation is not None
        assert response.pending_confirmation.id == "c1"

    def test_with_errors(self):
        """Test response with errors."""
        from mother.agent.errors import AgentError, ErrorCategory

        error = AgentError(category=ErrorCategory.INTERNAL, message="Something failed")
        response = AgentResponse(
            text="Error occurred",
            success=False,
            errors=[error],
        )

        assert response.success is False
        assert len(response.errors) == 1


class TestMotherAgentInit:
    """Tests for MotherAgent initialization."""

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_init_basic(self, mock_anthropic):
        """Test basic initialization."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        assert agent.tool_registry is mock_registry
        assert agent.model == "claude-sonnet-4-20250514"
        assert agent.max_iterations == 10
        assert agent.memory is None

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_init_custom_model(self, mock_anthropic):
        """Test initialization with custom model."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            model="claude-3-opus-20240229",
            max_iterations=5,
            enable_memory=False,
        )

        assert agent.model == "claude-3-opus-20240229"
        assert agent.max_iterations == 5

    @patch("mother.agent.core.anthropic.Anthropic")
    @patch("mother.agent.core.MemoryManager")
    def test_init_with_memory(self, mock_memory_manager, mock_anthropic):
        """Test initialization with memory enabled."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_memory_manager.return_value = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=True,
            openai_api_key="test-key",
        )

        assert agent.memory is not None

    @patch("mother.agent.core.anthropic.Anthropic")
    @patch("mother.agent.core.MemoryManager")
    def test_init_memory_failure(self, mock_memory_manager, mock_anthropic):
        """Test initialization when memory fails."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_memory_manager.side_effect = Exception("Memory init failed")

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=True,
        )

        # Should continue without memory
        assert agent.memory is None


class TestMotherAgentTools:
    """Tests for MotherAgent tool-related methods."""

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_get_tools(self, mock_anthropic):
        """Test get_tools method."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = [
            {"name": "tool1", "description": "Test tool 1"},
            {"name": "tool2", "description": "Test tool 2"},
        ]

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        tools = agent.get_tools()

        assert len(tools) == 2
        mock_registry.get_all_anthropic_schemas.assert_called_once()

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_generate_tool_descriptions_empty(self, mock_anthropic):
        """Test tool descriptions with no tools."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._generate_tool_descriptions()

        assert "Available tools:" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_generate_tool_descriptions_legacy(self, mock_anthropic):
        """Test tool descriptions with legacy tools."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {
            "filesystem": {
                "description": "File operations",
                "commands": ["list", "read", "write"],
                "source": "legacy",
            }
        }

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._generate_tool_descriptions()

        assert "filesystem" in desc
        assert "File operations" in desc
        assert "list" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_generate_tool_descriptions_plugin(self, mock_anthropic):
        """Test tool descriptions with plugin tools."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {
            "web": {
                "description": "Web operations",
                "commands": ["fetch", "post"],
                "source": "plugin",
                "version": "1.0.0",
            }
        }

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._generate_tool_descriptions()

        assert "Plugin capabilities" in desc
        assert "web" in desc
        assert "v1.0.0" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_generate_tool_descriptions_many_commands(self, mock_anthropic):
        """Test tool descriptions with many commands (truncation)."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {
            "multi": {
                "description": "Many commands",
                "commands": [f"cmd{i}" for i in range(15)],  # 15 commands
                "source": "legacy",
            }
        }

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._generate_tool_descriptions()

        # Should truncate to 8 and show "+7 more"
        assert "+7 more" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_get_system_prompt(self, mock_anthropic):
        """Test get_system_prompt method."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        prompt = agent.get_system_prompt()

        assert "Mother" in prompt
        assert "Guidelines" in prompt
        assert "Available tools" in prompt

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_get_planning_prompt(self, mock_anthropic):
        """Test get_planning_prompt method."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        prompt = agent.get_planning_prompt()

        assert "PLANNING MODE" in prompt
        assert "JSON plan" in prompt
        assert "Available tools" in prompt

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_generate_tool_descriptions_no_commands_legacy(self, mock_anthropic):
        """Test tool descriptions with no commands (legacy)."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {
            "simple": {
                "description": "Simple tool",
                "commands": [],
                "source": "legacy",
            }
        }

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._generate_tool_descriptions()

        assert "simple" in desc
        assert "Simple tool" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_generate_tool_descriptions_no_commands_plugin(self, mock_anthropic):
        """Test tool descriptions with no commands (plugin)."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {
            "minimal": {
                "description": "Minimal plugin",
                "commands": [],
                "source": "plugin",
                "version": "0.1.0",
            }
        }

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._generate_tool_descriptions()

        assert "Plugin capabilities" in desc
        assert "minimal" in desc
        assert "v0.1.0" in desc


class TestMotherAgentState:
    """Tests for MotherAgent state management methods."""

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_reset(self, mock_anthropic):
        """Test reset method clears state."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        # Modify state
        original_session = agent.state.session_id
        agent.state.messages.append({"role": "user", "content": "test"})
        agent.state.confirmed_actions.add("action-1")

        # Reset
        agent.reset()

        assert agent.state.session_id != original_session
        assert agent.state.messages == []
        assert agent.state.confirmed_actions == set()

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_get_session_id(self, mock_anthropic):
        """Test get_session_id method."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        session_id = agent.get_session_id()

        assert session_id == agent.state.session_id
        assert isinstance(session_id, str)


class TestMotherAgentMemory:
    """Tests for MotherAgent memory-related methods."""

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_get_memory_stats_no_memory(self, mock_anthropic):
        """Test get_memory_stats when memory is disabled."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        stats = agent.get_memory_stats()

        assert stats is None

    @patch("mother.agent.core.anthropic.Anthropic")
    @patch("mother.agent.core.MemoryManager")
    def test_get_memory_stats_with_memory(self, mock_memory_manager, mock_anthropic):
        """Test get_memory_stats when memory is enabled."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_memory = MagicMock()
        mock_memory.get_stats.return_value = {"total": 100, "sessions": 5}
        mock_memory_manager.return_value = mock_memory

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=True,
        )

        stats = agent.get_memory_stats()

        assert stats == {"total": 100, "sessions": 5}
        mock_memory.get_stats.assert_called_once()

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_search_memory_no_memory(self, mock_anthropic):
        """Test search_memory when memory is disabled."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        results = agent.search_memory("test query")

        assert results == []

    @patch("mother.agent.core.anthropic.Anthropic")
    @patch("mother.agent.core.MemoryManager")
    def test_search_memory_with_memory(self, mock_memory_manager, mock_anthropic):
        """Test search_memory when memory is enabled."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_memory = MagicMock()
        mock_memory.recall.return_value = [{"content": "result 1"}, {"content": "result 2"}]
        mock_memory_manager.return_value = mock_memory

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=True,
        )

        results = agent.search_memory("test query", limit=5)

        assert len(results) == 2
        mock_memory.recall.assert_called_once_with("test query", limit=5)


class TestMotherAgentDescribeAction:
    """Tests for MotherAgent._describe_action method."""

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_describe_action_mailcraft_send(self, mock_anthropic):
        """Test describe_action for mailcraft send."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._describe_action(
            "mailcraft",
            "send",
            {"to": ["user@example.com"], "subject": "Test Subject"},
        )

        assert "Send email to user@example.com" in desc
        assert "Test Subject" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_describe_action_mailcraft_reply(self, mock_anthropic):
        """Test describe_action for mailcraft reply."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._describe_action("mailcraft", "reply", {"message_id": "12345"})

        assert "Reply to email #12345" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_describe_action_mailcraft_delete(self, mock_anthropic):
        """Test describe_action for mailcraft delete."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._describe_action("mailcraft", "delete", {"message_id": "12345", "permanent": True})

        assert "Delete email #12345" in desc
        assert "permanently" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_describe_action_mailcraft_delete_to_trash(self, mock_anthropic):
        """Test describe_action for mailcraft delete to trash."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._describe_action("mailcraft", "delete", {"message_id": "12345", "permanent": False})

        assert "Delete email #12345" in desc
        assert "to trash" in desc

    @patch("mother.agent.core.anthropic.Anthropic")
    def test_describe_action_generic(self, mock_anthropic):
        """Test describe_action for generic tool."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        desc = agent._describe_action("filesystem", "delete", {"path": "/tmp/test.txt"})

        assert "Execute filesystem delete" in desc
        assert "/tmp/test.txt" in desc


class TestMotherAgentConfirmAction:
    """Tests for MotherAgent.confirm_action method."""

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_confirm_action_no_pending(self, mock_anthropic):
        """Test confirm_action with no pending confirmation."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.confirm_action("some-id")

        assert response.success is False
        assert "No pending action" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_confirm_action_wrong_id(self, mock_anthropic):
        """Test confirm_action with wrong confirmation ID."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        # Set a pending confirmation
        agent.state.pending_confirmation = PendingConfirmation(
            id="correct-id",
            tool_name="test",
            command="delete",
            args={},
            description="Test action",
        )

        response = await agent.confirm_action("wrong-id")

        assert response.success is False
        assert "doesn't match" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_confirm_action_tool_not_available(self, mock_anthropic):
        """Test confirm_action when tool is no longer available."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.get_wrapper.return_value = None

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        agent.state.pending_confirmation = PendingConfirmation(
            id="confirm-1",
            tool_name="missing_tool",
            command="run",
            args={},
            description="Test action",
        )

        response = await agent.confirm_action("confirm-1")

        assert response.success is False
        assert "no longer available" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_confirm_action_success(self, mock_anthropic):
        """Test confirm_action success path."""
        from mother.agent.core import MotherAgent
        from mother.tools.base import ToolResult

        mock_registry = MagicMock()
        mock_wrapper = MagicMock()
        mock_wrapper.execute.return_value = ToolResult(
            success=True,
            stdout="Action completed",
            stderr="",
            exit_code=0,
            parsed_data={"result": "success"},
        )
        mock_registry.get_wrapper.return_value = mock_wrapper

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        agent.state.pending_confirmation = PendingConfirmation(
            id="confirm-1",
            tool_name="test_tool",
            command="run",
            args={"param": "value"},
            description="Test action",
        )

        response = await agent.confirm_action("confirm-1")

        assert response.success is True
        assert "completed successfully" in response.text
        assert agent.state.pending_confirmation is None
        assert "confirm-1" in agent.state.confirmed_actions

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_confirm_action_failure(self, mock_anthropic):
        """Test confirm_action failure path."""
        from mother.agent.core import MotherAgent
        from mother.tools.base import ToolResult

        mock_registry = MagicMock()
        mock_wrapper = MagicMock()
        mock_wrapper.execute.return_value = ToolResult(
            success=False,
            stdout="",
            stderr="Command failed",
            exit_code=1,
            error_message="Something went wrong",
        )
        mock_registry.get_wrapper.return_value = mock_wrapper

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        agent.state.pending_confirmation = PendingConfirmation(
            id="confirm-1",
            tool_name="test_tool",
            command="run",
            args={},
            description="Test action",
        )

        response = await agent.confirm_action("confirm-1")

        assert response.success is False
        assert len(response.errors) > 0


class TestMotherAgentProcessCommand:
    """Tests for MotherAgent.process_command method."""

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_command_api_error(self, mock_anthropic):
        """Test process_command handles API errors."""
        import anthropic

        from mother.agent.core import MotherAgent

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="Rate limit exceeded",
            request=MagicMock(),
            body=None,
        )
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = []
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.process_command("Hello")

        assert response.success is False
        assert "API error" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_command_text_only_response(self, mock_anthropic):
        """Test process_command with text-only response (no tool calls)."""
        from mother.agent.core import MotherAgent

        # Create a mock response with text content
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello! How can I help you?"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = []
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.process_command("Hello")

        assert response.success is True
        assert "Hello! How can I help you?" in response.text
        assert response.tool_calls == []

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_command_with_tool_call_unknown_tool(self, mock_anthropic):
        """Test process_command with unknown tool call."""
        from mother.agent.core import MotherAgent

        # First response: tool call
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool-1"
        mock_tool_block.name = "unknown_tool_command"
        mock_tool_block.input = {}

        mock_response1 = MagicMock()
        mock_response1.content = [mock_tool_block]
        mock_response1.stop_reason = "tool_use"

        # Second response: final text
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Tool not found."

        mock_response2 = MagicMock()
        mock_response2.content = [mock_text_block]
        mock_response2.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_response1, mock_response2]
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = []
        mock_registry.list_tools.return_value = {}
        mock_registry.is_plugin_capability.return_value = False
        mock_registry.parse_tool_name.return_value = (None, None)

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.process_command("Do something")

        assert response.success is True

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_command_max_iterations(self, mock_anthropic):
        """Test process_command reaches max iterations."""
        from mother.agent.core import MotherAgent

        # Always return a tool call to keep looping
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool-1"
        mock_tool_block.name = "test_command"
        mock_tool_block.input = {}

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = []
        mock_registry.list_tools.return_value = {}
        mock_registry.is_plugin_capability.return_value = False
        mock_registry.parse_tool_name.return_value = ("test", "command")
        mock_registry.get_wrapper.return_value = None

        agent = MotherAgent(
            tool_registry=mock_registry,
            max_iterations=3,
            enable_memory=False,
        )

        response = await agent.process_command("Loop forever")

        assert response.success is False
        assert "maximum number of steps" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_command_with_session_id(self, mock_anthropic):
        """Test process_command with session ID."""
        from mother.agent.core import MotherAgent

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Response"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = []
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.process_command("Hello", session_id="custom-session")

        assert response.success is True
        assert agent.state.session_id == "custom-session"

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_command_with_legacy_tool(self, mock_anthropic):
        """Test process_command with legacy tool execution."""
        from mother.agent.core import MotherAgent
        from mother.tools.base import ToolResult

        # First response: tool call
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool-1"
        mock_tool_block.name = "filesystem_list"
        mock_tool_block.input = {"path": "/tmp"}

        mock_response1 = MagicMock()
        mock_response1.content = [mock_tool_block]
        mock_response1.stop_reason = "tool_use"

        # Second response: final text
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Listed files successfully."

        mock_response2 = MagicMock()
        mock_response2.content = [mock_text_block]
        mock_response2.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_response1, mock_response2]
        mock_anthropic.return_value = mock_client

        mock_wrapper = MagicMock()
        mock_wrapper.is_confirmation_required.return_value = False
        mock_wrapper.execute.return_value = ToolResult(
            success=True,
            stdout="file1.txt\nfile2.txt",
            stderr="",
            exit_code=0,
            parsed_data=None,
        )

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = []
        mock_registry.list_tools.return_value = {}
        mock_registry.is_plugin_capability.return_value = False
        mock_registry.parse_tool_name.return_value = ("filesystem", "list")
        mock_registry.get_wrapper.return_value = mock_wrapper

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.process_command("List files")

        assert response.success is True
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["tool"] == "filesystem_list"

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_command_tool_requires_confirmation(self, mock_anthropic):
        """Test process_command when tool requires confirmation."""
        from mother.agent.core import MotherAgent

        # Tool call that requires confirmation
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool-1"
        mock_tool_block.name = "filesystem_delete"
        mock_tool_block.input = {"path": "/tmp/file.txt"}

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        mock_wrapper = MagicMock()
        mock_wrapper.is_confirmation_required.return_value = True

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = []
        mock_registry.list_tools.return_value = {}
        mock_registry.is_plugin_capability.return_value = False
        mock_registry.parse_tool_name.return_value = ("filesystem", "delete")
        mock_registry.get_wrapper.return_value = mock_wrapper

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.process_command("Delete file")

        assert response.success is True
        assert response.pending_confirmation is not None
        assert "requires confirmation" in response.text


class TestMotherAgentCreatePlan:
    """Tests for MotherAgent.create_plan method."""

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_create_plan_api_error(self, mock_anthropic):
        """Test create_plan handles API errors."""
        import anthropic

        from mother.agent.core import MotherAgent

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="Service unavailable",
            request=MagicMock(),
            body=None,
        )
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.create_plan("Create a plan")

        assert response.success is False
        assert "API error" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_create_plan_invalid_json(self, mock_anthropic):
        """Test create_plan with invalid JSON response."""
        from mother.agent.core import MotherAgent

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "This is not valid JSON"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.create_plan("Create a plan")

        assert response.success is False
        assert "Failed to create plan" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_create_plan_success(self, mock_anthropic):
        """Test create_plan with valid JSON response."""
        import json

        from mother.agent.core import MotherAgent

        plan_json = json.dumps(
            {
                "goal": "List and read files",
                "steps": [
                    {
                        "order": 1,
                        "tool_name": "filesystem",
                        "command": "list",
                        "args": {"path": "/tmp"},
                        "description": "List files in /tmp",
                        "depends_on": [],
                    },
                    {
                        "order": 2,
                        "tool_name": "filesystem",
                        "command": "read",
                        "args": {"path": "/tmp/file.txt"},
                        "description": "Read the file",
                        "depends_on": [1],
                    },
                ],
            }
        )

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = plan_json

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.create_plan("List and read files")

        assert response.success is True
        assert response.pending_plan is not None
        assert response.pending_plan.goal == "List and read files"
        assert len(response.pending_plan.steps) == 2
        assert agent.state.pending_plan is not None

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_create_plan_with_markdown_code_block(self, mock_anthropic):
        """Test create_plan with JSON in markdown code block."""
        import json

        from mother.agent.core import MotherAgent

        plan_json = json.dumps(
            {
                "goal": "Simple task",
                "steps": [
                    {
                        "order": 1,
                        "tool_name": "test",
                        "command": "run",
                        "args": {},
                        "description": "Run test",
                        "depends_on": [],
                    }
                ],
            }
        )

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = f"```json\n{plan_json}\n```"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.create_plan("Run test")

        assert response.success is True
        assert response.pending_plan is not None


class TestMotherAgentExecutePlan:
    """Tests for MotherAgent.execute_plan method."""

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plan_no_pending(self, mock_anthropic):
        """Test execute_plan with no pending plan."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.execute_plan()

        assert response.success is False
        assert "No pending plan" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plan_wrong_id(self, mock_anthropic):
        """Test execute_plan with wrong plan ID."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        agent.state.pending_plan = ExecutionPlan(
            id="correct-id",
            goal="Test",
            steps=[],
        )

        response = await agent.execute_plan(plan_id="wrong-id")

        assert response.success is False
        assert "doesn't match" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plan_success(self, mock_anthropic):
        """Test execute_plan success."""
        from mother.agent.core import MotherAgent
        from mother.tools.base import ToolResult

        mock_wrapper = MagicMock()
        mock_wrapper.is_confirmation_required.return_value = False
        mock_wrapper.execute.return_value = ToolResult(
            success=True,
            stdout="Done",
            stderr="",
            exit_code=0,
            parsed_data={"result": "success"},
        )

        mock_registry = MagicMock()
        mock_registry.get_wrapper.return_value = mock_wrapper

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Run test",
        )

        agent.state.pending_plan = ExecutionPlan(
            id="plan-1",
            goal="Test plan",
            steps=[step],
        )

        response = await agent.execute_plan()

        assert response.success is True
        assert "Plan Execution Complete" in response.text
        assert agent.state.pending_plan is None
        assert agent.state.current_plan is None

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plan_tool_not_found(self, mock_anthropic):
        """Test execute_plan when tool not found."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.get_wrapper.return_value = None

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="missing",
            command="run",
            args={},
            description="Run missing tool",
        )

        agent.state.pending_plan = ExecutionPlan(
            id="plan-1",
            goal="Test plan",
            steps=[step],
        )

        response = await agent.execute_plan()

        assert response.success is False
        assert len(response.errors) > 0

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plan_with_dependencies(self, mock_anthropic):
        """Test execute_plan with step dependencies."""
        from mother.agent.core import MotherAgent
        from mother.tools.base import ToolResult

        mock_wrapper = MagicMock()
        mock_wrapper.is_confirmation_required.return_value = False
        mock_wrapper.execute.return_value = ToolResult(
            success=True,
            stdout="Done",
            stderr="",
            exit_code=0,
            parsed_data={"output_path": "/tmp/result.txt"},
        )

        mock_registry = MagicMock()
        mock_registry.get_wrapper.return_value = mock_wrapper

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        steps = [
            PlanStep(
                id="step-1",
                order=1,
                tool_name="test",
                command="create",
                args={},
                description="Create file",
            ),
            PlanStep(
                id="step-2",
                order=2,
                tool_name="transmit",
                command="send",
                args={"uses_result_from": 1, "document": "placeholder"},
                description="Send file",
                depends_on=["1"],
            ),
        ]

        agent.state.pending_plan = ExecutionPlan(
            id="plan-1",
            goal="Create and send",
            steps=steps,
        )

        response = await agent.execute_plan()

        assert response.success is True
        # The second call should have used the result from step 1
        assert mock_wrapper.execute.call_count == 2


class TestMotherAgentProcessWithPlanning:
    """Tests for MotherAgent.process_with_planning method."""

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_with_planning_approve_pending(self, mock_anthropic):
        """Test process_with_planning approves pending plan with 'yes'."""
        from mother.agent.core import MotherAgent
        from mother.tools.base import ToolResult

        mock_wrapper = MagicMock()
        mock_wrapper.is_confirmation_required.return_value = False
        mock_wrapper.execute.return_value = ToolResult(
            success=True,
            stdout="Done",
            stderr="",
            exit_code=0,
        )

        mock_registry = MagicMock()
        mock_registry.get_wrapper.return_value = mock_wrapper

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        # Set up pending plan
        step = PlanStep(
            id="step-1",
            order=1,
            tool_name="test",
            command="run",
            args={},
            description="Run test",
        )

        agent.state.pending_plan = ExecutionPlan(
            id="plan-1",
            goal="Test",
            steps=[step],
        )

        response = await agent.process_with_planning("yes")

        assert response.success is True
        assert "Plan Execution Complete" in response.text

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_with_planning_cancel_pending(self, mock_anthropic):
        """Test process_with_planning cancels pending plan with 'no'."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        agent.state.pending_plan = ExecutionPlan(
            id="plan-1",
            goal="Test",
            steps=[],
        )

        response = await agent.process_with_planning("no")

        assert response.success is True
        assert "cancelled" in response.text
        assert agent.state.pending_plan is None

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_with_planning_new_request(self, mock_anthropic):
        """Test process_with_planning creates new plan."""
        import json

        from mother.agent.core import MotherAgent

        plan_json = json.dumps(
            {
                "goal": "New task",
                "steps": [
                    {
                        "order": 1,
                        "tool_name": "test",
                        "command": "run",
                        "args": {},
                        "description": "Step 1",
                        "depends_on": [],
                    }
                ],
            }
        )

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = plan_json

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = {}

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.process_with_planning("Do something new")

        assert response.success is True
        assert response.pending_plan is not None


class TestMotherAgentPluginExecution:
    """Tests for MotherAgent._execute_plugin_tool method."""

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    @patch("mother.agent.core.PLUGINS_AVAILABLE", False)
    async def test_execute_plugin_tool_plugins_not_available(self, mock_anthropic):
        """Test _execute_plugin_tool when plugins not available."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool-1"
        mock_tool_use.name = "plugin_capability"
        mock_tool_use.input = {}

        result = await agent._execute_plugin_tool(mock_tool_use, [], False)

        assert result is not None
        assert result["is_error"] is True
        assert "not available" in result["content"]

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plugin_tool_requires_confirmation(self, mock_anthropic):
        """Test _execute_plugin_tool when confirmation required."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.requires_confirmation.return_value = True
        mock_registry.parse_tool_name.return_value = ("plugin", "action")

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool-1"
        mock_tool_use.name = "plugin_action"
        mock_tool_use.input = {"param": "value"}

        result = await agent._execute_plugin_tool(mock_tool_use, [], False)

        # Should return None (pending confirmation)
        assert result is None
        assert agent.state.pending_confirmation is not None
        assert agent.state.pending_confirmation.id == "tool-1"

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plugin_tool_success(self, mock_anthropic):
        """Test _execute_plugin_tool success path."""
        from mother.agent.core import MotherAgent
        from mother.plugins import PluginResult, ResultStatus

        mock_plugin_result = PluginResult(
            success=True,
            status=ResultStatus.SUCCESS,
            data={"result": "success"},
        )

        mock_registry = MagicMock()
        mock_registry.requires_confirmation.return_value = False
        mock_registry.parse_tool_name.return_value = ("plugin", "action")
        mock_registry.execute_plugin = AsyncMock(return_value=mock_plugin_result)

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool-1"
        mock_tool_use.name = "plugin_action"
        mock_tool_use.input = {}

        tool_calls = []
        result = await agent._execute_plugin_tool(mock_tool_use, tool_calls, False)

        assert result is not None
        assert result["is_error"] is False
        assert len(tool_calls) == 1
        assert tool_calls[0]["source"] == "plugin"

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plugin_tool_error(self, mock_anthropic):
        """Test _execute_plugin_tool error path."""
        from mother.agent.core import MotherAgent
        from mother.plugins import PluginResult, ResultStatus

        mock_plugin_result = PluginResult(
            success=False,
            status=ResultStatus.ERROR,
            error_message="Plugin failed",
        )

        mock_registry = MagicMock()
        mock_registry.requires_confirmation.return_value = False
        mock_registry.parse_tool_name.return_value = ("plugin", "action")
        mock_registry.execute_plugin = AsyncMock(return_value=mock_plugin_result)

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool-1"
        mock_tool_use.name = "plugin_action"
        mock_tool_use.input = {}

        result = await agent._execute_plugin_tool(mock_tool_use, [], False)

        assert result is not None
        assert result["is_error"] is True
        assert "Plugin failed" in result["content"]

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plugin_tool_exception(self, mock_anthropic):
        """Test _execute_plugin_tool handles exceptions."""
        from mother.agent.core import MotherAgent

        mock_registry = MagicMock()
        mock_registry.requires_confirmation.return_value = False
        mock_registry.execute_plugin = AsyncMock(side_effect=Exception("Unexpected error"))

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool-1"
        mock_tool_use.name = "plugin_action"
        mock_tool_use.input = {}

        result = await agent._execute_plugin_tool(mock_tool_use, [], False)

        assert result is not None
        assert result["is_error"] is True
        assert "execution failed" in result["content"]

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_execute_plugin_tool_pending_confirmation_result(self, mock_anthropic):
        """Test _execute_plugin_tool when plugin returns pending confirmation."""
        from mother.agent.core import MotherAgent
        from mother.plugins import PluginResult, ResultStatus

        mock_plugin_result = PluginResult(
            success=True,
            status=ResultStatus.PENDING_CONFIRMATION,
            data={"action": "Delete all files"},
        )

        mock_registry = MagicMock()
        mock_registry.requires_confirmation.return_value = False
        mock_registry.parse_tool_name.return_value = ("plugin", "dangerous_action")
        mock_registry.execute_plugin = AsyncMock(return_value=mock_plugin_result)

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        mock_tool_use = MagicMock()
        mock_tool_use.id = "tool-1"
        mock_tool_use.name = "plugin_dangerous_action"
        mock_tool_use.input = {}

        result = await agent._execute_plugin_tool(mock_tool_use, [], False)

        # Should return None (pending confirmation from result)
        assert result is None
        assert agent.state.pending_confirmation is not None

    @pytest.mark.asyncio
    @patch("mother.agent.core.anthropic.Anthropic")
    async def test_process_command_with_plugin_tool(self, mock_anthropic):
        """Test process_command with plugin tool execution."""
        from mother.agent.core import MotherAgent
        from mother.plugins import PluginResult, ResultStatus

        # First response: tool call
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool-1"
        mock_tool_block.name = "web_fetch"
        mock_tool_block.input = {"url": "https://example.com"}

        mock_response1 = MagicMock()
        mock_response1.content = [mock_tool_block]
        mock_response1.stop_reason = "tool_use"

        # Second response: final text
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Fetched the page successfully."

        mock_response2 = MagicMock()
        mock_response2.content = [mock_text_block]
        mock_response2.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_response1, mock_response2]
        mock_anthropic.return_value = mock_client

        mock_plugin_result = PluginResult(
            success=True,
            status=ResultStatus.SUCCESS,
            data={"content": "Page content"},
        )

        mock_registry = MagicMock()
        mock_registry.get_all_anthropic_schemas.return_value = []
        mock_registry.list_tools.return_value = {}
        mock_registry.is_plugin_capability.return_value = True
        mock_registry.requires_confirmation.return_value = False
        mock_registry.parse_tool_name.return_value = ("web", "fetch")
        mock_registry.execute_plugin = AsyncMock(return_value=mock_plugin_result)

        agent = MotherAgent(
            tool_registry=mock_registry,
            enable_memory=False,
        )

        response = await agent.process_command("Fetch example.com")

        assert response.success is True
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["source"] == "plugin"
