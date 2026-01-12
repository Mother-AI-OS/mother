"""Claude-powered agent loop for CLI orchestration.

Supports both legacy ToolWrapper-based tools and the new plugin system.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..llm import LLMProvider
from ..llm import ToolCall as LLMToolCall
from ..llm.factory import get_provider_for_settings
from ..llm.providers.anthropic import AnthropicProvider
from ..memory import MemoryManager
from ..tools.base import ToolResult
from ..tools.registry import ToolRegistry
from .errors import AgentError, ErrorHandler

# Import plugin types for type checking
try:
    from ..plugins import PluginResult, ResultStatus

    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False
    PluginResult = None
    ResultStatus = None

logger = logging.getLogger("mother.agent")


class PlanStepStatus(Enum):
    """Status of a plan step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    id: str
    order: int
    tool_name: str
    command: str
    args: dict[str, Any]
    description: str
    depends_on: list[str] = field(default_factory=list)
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: Any | None = None
    error: str | None = None


@dataclass
class ExecutionPlan:
    """A plan for executing a multi-step task."""

    id: str
    goal: str
    steps: list[PlanStep]
    created_at: str = field(default_factory=lambda: __import__("datetime").datetime.now().isoformat())
    status: str = "pending"  # pending, approved, executing, completed, failed

    def to_display(self) -> str:
        """Format plan for user display."""
        lines = [
            "📋 **Execution Plan**",
            f"Goal: {self.goal}",
            "",
            "**Steps:**",
        ]
        for step in self.steps:
            status_icon = {
                PlanStepStatus.PENDING: "⏳",
                PlanStepStatus.IN_PROGRESS: "🔄",
                PlanStepStatus.COMPLETED: "✅",
                PlanStepStatus.FAILED: "❌",
                PlanStepStatus.SKIPPED: "⏭️",
            }.get(step.status, "⏳")

            lines.append(f"  {step.order}. {status_icon} {step.description}")
            lines.append(f"     Tool: `{step.tool_name}_{step.command}`")

        return "\n".join(lines)


@dataclass
class PendingConfirmation:
    """A pending action that requires user confirmation."""

    id: str
    tool_name: str
    command: str
    args: dict[str, Any]
    description: str


@dataclass
class AgentState:
    """Current state of the agent."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    pending_confirmation: PendingConfirmation | None = None
    confirmed_actions: set[str] = field(default_factory=set)
    pending_plan: ExecutionPlan | None = None
    current_plan: ExecutionPlan | None = None


@dataclass
class AgentResponse:
    """Response from the agent."""

    text: str
    success: bool = True
    tool_calls: list[dict] = field(default_factory=list)
    pending_confirmation: PendingConfirmation | None = None
    pending_plan: ExecutionPlan | None = None
    errors: list[AgentError] = field(default_factory=list)


class MotherAgent:
    """
    The 'mother' AI agent that orchestrates CLI tools.

    Uses Claude's tool_use to:
    1. Understand natural language commands
    2. Plan which tools to call
    3. Execute tools via subprocess
    4. Chain multi-step workflows
    5. Return final answer
    """

    # Base system prompt - tool list is appended dynamically
    SYSTEM_PROMPT_BASE = """You are Mother, an AI assistant that helps users through CLI tools and plugins.

{tool_descriptions}

Guidelines:
1. Always use the appropriate tool for the task
2. For destructive actions (send, reply, delete, write, etc.), confirmation may be required
3. Chain tools when needed (e.g., search then read, fetch then list)
4. Parse tool results and provide clear, concise summaries
5. If a tool fails, explain why and suggest alternatives
6. When listing items, summarize the key information

Be concise but informative. Focus on actionable information."""

    # Base planning prompt - tool list is appended dynamically
    PLANNING_PROMPT_BASE = """You are Mother in PLANNING MODE. Your job is to create an execution plan for a multi-step task.

{tool_descriptions}

IMPORTANT: You must respond with a JSON plan in this exact format:
{{
  "goal": "Brief description of what we're trying to achieve",
  "steps": [
    {{
      "order": 1,
      "tool_name": "tool_name",
      "command": "command_name",
      "args": {{"arg1": "value1"}},
      "description": "Human-readable description of this step",
      "depends_on": []
    }},
    {{
      "order": 2,
      "tool_name": "another_tool",
      "command": "command_name",
      "args": {{"arg1": "value1", "uses_result_from": 1}},
      "description": "Description mentioning it uses output from step 1",
      "depends_on": [1]
    }}
  ]
}}

Rules:
1. Break down the task into clear, sequential steps
2. Use "depends_on" to indicate which steps must complete first
3. Use "uses_result_from" in args to reference outputs from previous steps
4. Be specific about file paths, recipients, etc.
5. Include all necessary steps - don't skip anything
6. For destructive actions (send, delete), the execution phase will ask for confirmation

Respond ONLY with the JSON plan, no other text."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        model: str | None = None,
        max_iterations: int = 10,
        api_key: str | None = None,
        openai_api_key: str | None = None,
        enable_memory: bool = True,
        provider: LLMProvider | None = None,
        settings: Any | None = None,
    ):
        """Initialize the Mother agent.

        Args:
            tool_registry: Registry of available tools and plugins
            model: Model name (deprecated, use settings.llm_model or provider)
            max_iterations: Maximum tool-use loop iterations
            api_key: API key (deprecated, use settings or provider)
            openai_api_key: OpenAI API key for memory embeddings
            enable_memory: Enable persistent memory
            provider: Pre-configured LLM provider instance
            settings: Application settings for provider configuration
        """
        # Initialize LLM provider
        if provider:
            self.provider = provider
        elif settings:
            self.provider = get_provider_for_settings(settings)
        else:
            # Legacy fallback for backward compatibility
            import os
            self.provider = AnthropicProvider(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
                model=model or "claude-sonnet-4-20250514",
            )

        self.tool_registry = tool_registry
        self.max_iterations = max_iterations
        self.error_handler = ErrorHandler()
        self.state = AgentState()

        # Initialize persistent memory
        self.memory: MemoryManager | None = None
        if enable_memory:
            try:
                self.memory = MemoryManager(openai_api_key=openai_api_key)
                logger.info("Memory manager initialized with vector search")
            except Exception as e:
                logger.warning(f"Failed to initialize memory: {e}")

    def get_tools(self) -> list[dict]:
        """Generate tool definitions for Claude."""
        return self.tool_registry.get_all_anthropic_schemas()

    def _generate_tool_descriptions(self) -> str:
        """Generate dynamic tool descriptions from registry and plugins.

        Returns:
            Formatted string with all available tools and their capabilities
        """
        lines = ["Available tools:"]

        # Get all tools from registry (includes both legacy and plugins)
        all_tools = self.tool_registry.list_tools()

        # Group by source for better organization
        legacy_tools = {}
        plugin_tools = {}

        for name, info in all_tools.items():
            if info.get("source") == "plugin":
                plugin_tools[name] = info
            else:
                legacy_tools[name] = info

        # Add legacy tools
        if legacy_tools:
            for name, info in sorted(legacy_tools.items()):
                desc = info.get("description", "")
                commands = info.get("commands", [])
                if commands:
                    cmd_list = ", ".join(commands[:8])  # Limit to 8 commands
                    if len(commands) > 8:
                        cmd_list += f", ... (+{len(commands) - 8} more)"
                    lines.append(f"- **{name}**: {desc} ({cmd_list})")
                else:
                    lines.append(f"- **{name}**: {desc}")

        # Add plugin tools
        if plugin_tools:
            lines.append("")
            lines.append("Plugin capabilities:")
            for name, info in sorted(plugin_tools.items()):
                desc = info.get("description", "")
                commands = info.get("commands", [])
                version = info.get("version", "")
                version_str = f" v{version}" if version else ""
                if commands:
                    cmd_list = ", ".join(commands[:8])
                    if len(commands) > 8:
                        cmd_list += f", ... (+{len(commands) - 8} more)"
                    lines.append(f"- **{name}**{version_str}: {desc} ({cmd_list})")
                else:
                    lines.append(f"- **{name}**{version_str}: {desc}")

        return "\n".join(lines)

    def get_system_prompt(self) -> str:
        """Get the system prompt with dynamic tool descriptions.

        Returns:
            Complete system prompt with current tools/plugins
        """
        tool_descriptions = self._generate_tool_descriptions()
        return self.SYSTEM_PROMPT_BASE.format(tool_descriptions=tool_descriptions)

    def get_planning_prompt(self) -> str:
        """Get the planning prompt with dynamic tool descriptions.

        Returns:
            Complete planning prompt with current tools/plugins
        """
        tool_descriptions = self._generate_tool_descriptions()
        return self.PLANNING_PROMPT_BASE.format(tool_descriptions=tool_descriptions)

    async def process_command(
        self,
        user_input: str,
        session_id: str | None = None,
        pre_confirmed: bool = False,
    ) -> AgentResponse:
        """
        Process a natural language command through the agent loop.

        Args:
            user_input: The user's natural language command
            session_id: Optional session ID for context continuity
            pre_confirmed: If True, skip confirmation for destructive actions

        Returns:
            AgentResponse with the result
        """
        # Initialize or restore session
        if session_id and session_id == self.state.session_id:
            # Continue existing session
            pass
        else:
            # New session
            self.state = AgentState(session_id=session_id or str(uuid.uuid4()))

        if pre_confirmed:
            # Mark all pending confirmations as confirmed
            if self.state.pending_confirmation:
                self.state.confirmed_actions.add(self.state.pending_confirmation.id)

        # Retrieve relevant context from memory
        memory_context = ""
        if self.memory:
            try:
                memory_context = self.memory.get_context_for_query(
                    query=user_input,
                    current_session_id=self.state.session_id,
                    max_memories=5,
                )
                if memory_context:
                    logger.debug(f"Retrieved memory context: {len(memory_context)} chars")
            except Exception as e:
                logger.warning(f"Failed to retrieve memory context: {e}")

            # Store user input in memory
            try:
                self.memory.remember_user_input(self.state.session_id, user_input)
            except Exception as e:
                logger.warning(f"Failed to store user input: {e}")

        # Add user message (with memory context if available)
        if memory_context:
            user_content = f"{user_input}\n\n---\n{memory_context}"
        else:
            user_content = user_input
        self.state.messages.append({"role": "user", "content": user_content})

        tool_calls_made = []
        errors = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # Call LLM provider
            try:
                response = await self.provider.create_message(
                    messages=self.state.messages,
                    system_prompt=self.get_system_prompt(),
                    tools=self.get_tools(),
                )
            except Exception as e:
                return AgentResponse(
                    text=f"API error: {e}",
                    success=False,
                    errors=[self.error_handler.classify_error(str(e))],
                )

            # Process unified response
            text_response = response.text
            tool_uses = response.tool_calls

            # Build assistant content for message history
            assistant_content: list[dict[str, Any]] = []
            if text_response:
                assistant_content.append(
                    {
                        "type": "text",
                        "text": text_response,
                    }
                )
            for tool_call in tool_uses:
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": tool_call.arguments,
                    }
                )

            # Store assistant message
            self.state.messages.append(
                {
                    "role": "assistant",
                    "content": assistant_content,
                }
            )

            # If no tool calls, we're done
            if not tool_uses:
                # Store response in memory
                if self.memory and text_response:
                    try:
                        self.memory.remember_assistant_response(
                            self.state.session_id,
                            text_response,
                            tool_calls=tool_calls_made if tool_calls_made else None,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to store response: {e}")

                return AgentResponse(
                    text=text_response,
                    success=True,
                    tool_calls=tool_calls_made,
                    errors=errors,
                )

            # Execute tools
            tool_results = []
            for tool_call in tool_uses:
                # Check if this is a plugin capability first
                is_plugin = self.tool_registry.is_plugin_capability(tool_call.name)

                if is_plugin:
                    # Plugin execution path
                    tool_result = await self._execute_plugin_tool_unified(tool_call, tool_calls_made, pre_confirmed)
                    if tool_result is None:
                        # Pending confirmation
                        return AgentResponse(
                            text=f"This action requires confirmation:\n\n{self.state.pending_confirmation.description}\n\nPlease confirm to proceed.",
                            success=True,
                            tool_calls=tool_calls_made,
                            pending_confirmation=self.state.pending_confirmation,
                        )
                    tool_results.append(tool_result)
                    if tool_result.get("is_error"):
                        error = self.error_handler.classify_error(
                            tool_result.get("content", "Unknown error"),
                            tool_name=tool_call.name,
                        )
                        errors.append(error)
                    continue

                # Legacy tool execution path
                # Parse tool name
                wrapper_name, command = self.tool_registry.parse_tool_name(tool_call.name)

                if not wrapper_name or not command:
                    result_content = f"Unknown tool: {tool_call.name}"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": result_content,
                            "is_error": True,
                        }
                    )
                    continue

                wrapper = self.tool_registry.get_wrapper(wrapper_name)
                if not wrapper:
                    result_content = f"Tool not available: {wrapper_name}"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": result_content,
                            "is_error": True,
                        }
                    )
                    continue

                # Check confirmation requirement
                if wrapper.is_confirmation_required(command):
                    confirmation_id = f"{tool_call.id}"
                    if confirmation_id not in self.state.confirmed_actions and not pre_confirmed:
                        # Create pending confirmation
                        pending = PendingConfirmation(
                            id=confirmation_id,
                            tool_name=wrapper_name,
                            command=command,
                            args=tool_call.arguments,
                            description=self._describe_action(wrapper_name, command, tool_call.arguments),
                        )
                        self.state.pending_confirmation = pending

                        return AgentResponse(
                            text=f"This action requires confirmation:\n\n{pending.description}\n\nPlease confirm to proceed.",
                            success=True,
                            tool_calls=tool_calls_made,
                            pending_confirmation=pending,
                        )

                # Execute tool
                result = wrapper.execute(command, tool_call.arguments)

                tool_call_info = {
                    "tool": f"{wrapper_name}_{command}",
                    "args": tool_call.arguments,
                    "success": result.success,
                    "execution_time": result.execution_time,
                }
                tool_calls_made.append(tool_call_info)

                self.state.tool_results.append(result)

                # Store tool result in memory (summarized)
                if self.memory:
                    try:
                        result_summary = result.stdout[:1000] if result.stdout else str(result.parsed_data)[:1000]
                        self.memory.remember_tool_result(
                            self.state.session_id,
                            tool_name=f"{wrapper_name}_{command}",
                            tool_args=tool_call.arguments,
                            result=result_summary,
                            success=result.success,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to store tool result: {e}")

                # Format result for Claude
                if result.success:
                    if result.parsed_data:
                        result_content = json.dumps(result.parsed_data, indent=2, default=str)
                    else:
                        result_content = result.stdout
                else:
                    error = self.error_handler.classify_error(
                        result.error_message or result.stderr,
                        tool_name=wrapper_name,
                        command=command,
                    )
                    errors.append(error)
                    result_content = self.error_handler.format_for_claude(error)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": result_content,
                        "is_error": not result.success,
                    }
                )

            # Add tool results to conversation
            self.state.messages.append(
                {
                    "role": "user",
                    "content": tool_results,
                }
            )

            # Check if we hit end_turn
            if response.stop_reason == "end_turn":
                # Store response in memory
                if self.memory and text_response:
                    try:
                        self.memory.remember_assistant_response(
                            self.state.session_id,
                            text_response,
                            tool_calls=tool_calls_made if tool_calls_made else None,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to store response: {e}")

                return AgentResponse(
                    text=text_response,
                    success=True,
                    tool_calls=tool_calls_made,
                    errors=errors,
                )

        # Reached max iterations
        return AgentResponse(
            text="I reached the maximum number of steps. Please try a more specific request.",
            success=False,
            tool_calls=tool_calls_made,
            errors=errors,
        )

    async def confirm_action(self, confirmation_id: str) -> AgentResponse:
        """Confirm a pending action and execute it."""
        if not self.state.pending_confirmation:
            return AgentResponse(
                text="No pending action to confirm.",
                success=False,
            )

        if self.state.pending_confirmation.id != confirmation_id:
            return AgentResponse(
                text="Confirmation ID doesn't match pending action.",
                success=False,
            )

        # Mark as confirmed
        self.state.confirmed_actions.add(confirmation_id)
        pending = self.state.pending_confirmation
        self.state.pending_confirmation = None

        # Execute the confirmed action
        wrapper = self.tool_registry.get_wrapper(pending.tool_name)
        if not wrapper:
            return AgentResponse(
                text=f"Tool no longer available: {pending.tool_name}",
                success=False,
            )

        result = wrapper.execute(pending.command, pending.args)

        if result.success:
            response_text = "Action completed successfully.\n\n"
            if result.parsed_data:
                response_text += json.dumps(result.parsed_data, indent=2, default=str)
            else:
                response_text += result.stdout
            return AgentResponse(text=response_text, success=True)
        else:
            error = self.error_handler.classify_error(
                result.error_message or result.stderr,
                tool_name=pending.tool_name,
                command=pending.command,
            )
            return AgentResponse(
                text=self.error_handler.format_for_user(error),
                success=False,
                errors=[error],
            )

    def _describe_action(self, tool_name: str, command: str, args: dict[str, Any]) -> str:
        """Create a human-readable description of an action."""
        if tool_name == "mailcraft":
            if command == "send":
                to = args.get("to", [])
                subject = args.get("subject", "")
                return f"Send email to {', '.join(to)}\nSubject: {subject}"
            elif command == "reply":
                msg_id = args.get("message_id", "")
                return f"Reply to email #{msg_id}"
            elif command == "delete":
                msg_id = args.get("message_id", "")
                permanent = "permanently" if args.get("permanent") else "to trash"
                return f"Delete email #{msg_id} ({permanent})"

        return f"Execute {tool_name} {command} with args: {json.dumps(args)}"

    async def _execute_plugin_tool_unified(
        self,
        tool_call: LLMToolCall,
        tool_calls_made: list[dict],
        pre_confirmed: bool,
    ) -> dict | None:
        """Execute a plugin capability using unified ToolCall type.

        Args:
            tool_call: The unified ToolCall from LLM response
            tool_calls_made: List to append tool call info to
            pre_confirmed: If True, skip confirmation

        Returns:
            Tool result dict, or None if pending confirmation
        """
        if not PLUGINS_AVAILABLE:
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": "Plugin system not available",
                "is_error": True,
            }

        # Check confirmation requirement
        if self.tool_registry.requires_confirmation(tool_call.name):
            confirmation_id = f"{tool_call.id}"
            if confirmation_id not in self.state.confirmed_actions and not pre_confirmed:
                # Parse plugin/capability names for description
                plugin_name, capability = self.tool_registry.parse_tool_name(tool_call.name)
                pending = PendingConfirmation(
                    id=confirmation_id,
                    tool_name=plugin_name or tool_call.name,
                    command=capability or "",
                    args=tool_call.arguments,
                    description=self._describe_action(
                        plugin_name or tool_call.name,
                        capability or "",
                        tool_call.arguments,
                    ),
                )
                self.state.pending_confirmation = pending
                return None

        # Execute via plugin system
        try:
            result = await self.tool_registry.execute_plugin(
                tool_call.name,
                tool_call.arguments,
            )

            # Track the call
            plugin_name, capability = self.tool_registry.parse_tool_name(tool_call.name)
            tool_call_info = {
                "tool": tool_call.name,
                "args": tool_call.arguments,
                "success": result.success,
                "execution_time": result.execution_time,
                "source": "plugin",
            }
            tool_calls_made.append(tool_call_info)

            # Store in memory
            if self.memory:
                try:
                    result_summary = str(result.data)[:1000] if result.data else (result.raw_output or "")[:1000]
                    self.memory.remember_tool_result(
                        self.state.session_id,
                        tool_name=tool_call.name,
                        tool_args=tool_call.arguments,
                        result=result_summary,
                        success=result.success,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store plugin result in memory: {e}")

            # Check for pending confirmation response
            if PLUGINS_AVAILABLE and ResultStatus and result.status == ResultStatus.PENDING_CONFIRMATION:
                plugin_name, capability = self.tool_registry.parse_tool_name(tool_call.name)
                pending = PendingConfirmation(
                    id=f"{tool_call.id}",
                    tool_name=plugin_name or tool_call.name,
                    command=capability or "",
                    args=tool_call.arguments,
                    description=result.data.get("action", "Action requires confirmation")
                    if result.data
                    else "Action requires confirmation",
                )
                self.state.pending_confirmation = pending
                return None

            # Format result for Claude
            if result.success:
                if result.data:
                    result_content = json.dumps(result.data, indent=2, default=str)
                elif result.raw_output:
                    result_content = result.raw_output
                else:
                    result_content = "Success (no output)"
            else:
                result_content = result.error_message or "Unknown error"

            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": result_content,
                "is_error": not result.success,
            }

        except Exception as e:
            logger.error(f"Plugin execution failed: {e}")
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": f"Plugin execution failed: {str(e)}",
                "is_error": True,
            }

    def reset(self) -> None:
        """Reset agent state for new conversation."""
        self.state = AgentState()

    def get_session_id(self) -> str:
        """Get current session ID."""
        return self.state.session_id

    def get_memory_stats(self) -> dict | None:
        """Get memory statistics."""
        if self.memory:
            return self.memory.get_stats()
        return None

    def search_memory(self, query: str, limit: int = 10) -> list[dict]:
        """Search past memories."""
        if self.memory:
            return self.memory.recall(query, limit=limit)
        return []

    async def create_plan(
        self,
        user_input: str,
        session_id: str | None = None,
    ) -> AgentResponse:
        """
        Create an execution plan for a multi-step task without executing it.

        Args:
            user_input: The user's natural language command
            session_id: Optional session ID for context continuity

        Returns:
            AgentResponse with the plan for approval
        """
        # Initialize session
        if session_id and session_id == self.state.session_id:
            pass
        else:
            self.state = AgentState(session_id=session_id or str(uuid.uuid4()))

        # Call LLM provider with planning prompt
        try:
            response = await self.provider.create_message(
                messages=[{"role": "user", "content": user_input}],
                system_prompt=self.get_planning_prompt(),
                tools=None,  # No tools in planning mode
            )
        except Exception as e:
            return AgentResponse(
                text=f"API error during planning: {e}",
                success=False,
            )

        # Parse the plan from response
        plan_text = response.text

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = plan_text.strip()
            if json_text.startswith("```"):
                # Remove markdown code block
                lines = json_text.split("\n")
                json_text = "\n".join(lines[1:-1])

            plan_data = json.loads(json_text)

            # Create ExecutionPlan
            steps = []
            for step_data in plan_data.get("steps", []):
                step = PlanStep(
                    id=str(uuid.uuid4()),
                    order=step_data.get("order", len(steps) + 1),
                    tool_name=step_data.get("tool_name", ""),
                    command=step_data.get("command", ""),
                    args=step_data.get("args", {}),
                    description=step_data.get("description", ""),
                    depends_on=[str(d) for d in step_data.get("depends_on", [])],
                )
                steps.append(step)

            plan = ExecutionPlan(
                id=str(uuid.uuid4()),
                goal=plan_data.get("goal", user_input),
                steps=steps,
            )

            self.state.pending_plan = plan

            return AgentResponse(
                text=plan.to_display() + "\n\n**Reply 'yes' to execute this plan, or 'no' to cancel.**",
                success=True,
                pending_plan=plan,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}\nRaw response: {plan_text}")
            return AgentResponse(
                text=f"Failed to create plan. Claude's response:\n\n{plan_text}",
                success=False,
            )

    async def execute_plan(self, plan_id: str | None = None) -> AgentResponse:
        """
        Execute an approved plan step by step.

        Args:
            plan_id: Optional plan ID to execute (uses pending plan if not specified)

        Returns:
            AgentResponse with execution results
        """
        plan = self.state.pending_plan
        if not plan:
            return AgentResponse(
                text="No pending plan to execute.",
                success=False,
            )

        if plan_id and plan.id != plan_id:
            return AgentResponse(
                text="Plan ID doesn't match pending plan.",
                success=False,
            )

        # Move plan to current
        self.state.current_plan = plan
        self.state.pending_plan = None
        plan.status = "executing"

        tool_calls_made = []
        errors = []
        step_results = {}  # Store results by step order for dependencies

        # Execute steps in order
        for step in sorted(plan.steps, key=lambda s: s.order):
            step.status = PlanStepStatus.IN_PROGRESS
            logger.info(f"Executing step {step.order}: {step.description}")

            # Check dependencies
            for dep in step.depends_on:
                dep_order = int(dep)
                if dep_order in step_results and step_results[dep_order].get("failed"):
                    step.status = PlanStepStatus.SKIPPED
                    step.error = f"Skipped due to failed dependency (step {dep_order})"
                    continue

            # Resolve result references in args
            resolved_args = dict(step.args)
            if "uses_result_from" in resolved_args:
                ref_step = resolved_args.pop("uses_result_from")
                if ref_step in step_results:
                    # Inject the result path/data into appropriate arg
                    prev_result = step_results[ref_step]
                    if "output_path" in prev_result:
                        # For file operations, use the output path
                        if "document" in resolved_args or step.tool_name == "transmit":
                            resolved_args["document"] = prev_result["output_path"]
                        elif "files" in resolved_args:
                            resolved_args["files"] = [prev_result["output_path"]]

            # Get wrapper and execute
            wrapper = self.tool_registry.get_wrapper(step.tool_name)
            if not wrapper:
                step.status = PlanStepStatus.FAILED
                step.error = f"Tool not available: {step.tool_name}"
                step_results[step.order] = {"failed": True, "error": step.error}
                errors.append(self.error_handler.classify_error(step.error))
                continue

            # Check if confirmation required
            if wrapper.is_confirmation_required(step.command):
                # For now, auto-confirm in plan execution (plan approval = bulk confirm)
                pass

            # Execute
            result = wrapper.execute(step.command, resolved_args)

            tool_call_info = {
                "tool": f"{step.tool_name}_{step.command}",
                "args": resolved_args,
                "success": result.success,
                "execution_time": result.execution_time,
                "step": step.order,
            }
            tool_calls_made.append(tool_call_info)

            if result.success:
                step.status = PlanStepStatus.COMPLETED
                step.result = result.parsed_data or result.stdout
                step_results[step.order] = result.parsed_data or {"output": result.stdout}
            else:
                step.status = PlanStepStatus.FAILED
                step.error = result.error_message or result.stderr
                step_results[step.order] = {"failed": True, "error": step.error}
                error = self.error_handler.classify_error(step.error, tool_name=step.tool_name, command=step.command)
                errors.append(error)

        # Determine overall status
        failed_steps = [s for s in plan.steps if s.status == PlanStepStatus.FAILED]
        if failed_steps:
            plan.status = "completed_with_errors"
        else:
            plan.status = "completed"

        # Format result
        result_text = "**Plan Execution Complete**\n\n"
        result_text += plan.to_display()
        result_text += "\n\n**Results:**\n"

        for step in plan.steps:
            if step.status == PlanStepStatus.COMPLETED:
                result_text += f"  ✅ Step {step.order}: Success\n"
                if step.result:
                    result_summary = str(step.result)[:200]
                    result_text += f"     {result_summary}\n"
            elif step.status == PlanStepStatus.FAILED:
                result_text += f"  ❌ Step {step.order}: Failed - {step.error}\n"
            elif step.status == PlanStepStatus.SKIPPED:
                result_text += f"  ⏭️ Step {step.order}: Skipped - {step.error}\n"

        self.state.current_plan = None

        return AgentResponse(
            text=result_text,
            success=len(failed_steps) == 0,
            tool_calls=tool_calls_made,
            errors=errors,
        )

    async def process_with_planning(
        self,
        user_input: str,
        session_id: str | None = None,
    ) -> AgentResponse:
        """
        Process a command with explicit planning phase.

        First creates a plan, then waits for approval before executing.
        Use this for complex multi-step tasks.

        Args:
            user_input: The user's natural language command
            session_id: Optional session ID

        Returns:
            AgentResponse with either a plan (pending approval) or execution results
        """
        # If we have a pending plan and user says yes, execute it
        if self.state.pending_plan:
            if user_input.lower().strip() in ("yes", "y", "approve", "execute", "go"):
                return await self.execute_plan()
            elif user_input.lower().strip() in ("no", "n", "cancel", "abort"):
                self.state.pending_plan = None
                return AgentResponse(
                    text="Plan cancelled.",
                    success=True,
                )
            else:
                # Treat as new request
                self.state.pending_plan = None

        # Create a new plan
        return await self.create_plan(user_input, session_id)
