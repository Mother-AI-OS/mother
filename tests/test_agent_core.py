"""Tests for the agent core module."""

from unittest.mock import MagicMock, patch

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
