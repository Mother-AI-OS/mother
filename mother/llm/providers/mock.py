"""Mock LLM provider for deterministic testing.

This provider returns pre-configured responses based on prompt patterns,
enabling offline testing without real API calls.

Environment variables:
    MOTHER_MOCK_LLM=1 or AI_PROVIDER=mock

Usage:
    export AI_PROVIDER=mock
    export MOCK_API_KEY=test-key  # Any non-empty value works
    mother serve
"""

import re
import uuid
from typing import Any

from ..base import LLMProvider, ProviderType
from ..response import LLMResponse, ToolCall


# Prompt patterns mapped to tool calls
# Pattern: (regex, tool_name, arguments_template)
# Tool names use format: plugin_command (e.g., shell_run_command)
MOCK_TOOL_MAPPINGS: list[tuple[str, str, dict[str, Any]]] = [
    # Shell operations (available in safe mode, but execution blocked by policy)
    (r"(run|execute|shell).*(command|script|bash)", "shell_run_command", {
        "command": "echo 'Hello from mock'"
    }),
    (r"(get|show|check).*(env|environment)", "shell_get_env", {
        "name": "HOME"
    }),
    (r"(hostname|host name|machine name)", "shell_hostname", {}),
    (r"(whoami|who am i|current user)", "shell_whoami", {}),

    # Email operations (available but requires confirmation/policy check)
    (r"(send|compose).*(email|mail)", "email_send_message", {
        "to": "test@example.com",
        "subject": "Test email",
        "body": "Test body"
    }),
    (r"(list|show|check).*(email|mail|inbox)", "email_list_messages", {
        "folder": "INBOX",
        "limit": 10
    }),
    (r"(read|open).*(email|mail|message)", "email_read_message", {
        "message_id": "1"
    }),

    # Tor operations (high-risk, blocked by policy)
    (r"(tor|darknet|onion).*(browse|fetch|access)", "tor_tor_fetch", {
        "url": "http://example.onion"
    }),

    # Demo plugin operations (safe, for testing)
    (r"(hello|greet|hi)", "demo_hello", {}),
    (r"(calculate|compute|math).*(add|sum|\+)", "demo_calculate", {
        "operation": "add",
        "a": 5,
        "b": 3
    }),
    (r"(echo|repeat|say)", "demo_echo", {
        "message": "Test message from mock"
    }),

    # Transmit operations
    (r"(transmit|send).*(document|file).*(email|fax|post)", "transmit_email", {
        "to": "test@example.com",
        "document": "./workspace/test.pdf"
    }),

    # Generic fallback patterns
    (r"(delete|remove).*(file|document|message)", "email_delete_message", {
        "message_id": "1"
    }),
    (r"(fetch|get|download|http).*(url|web|http)", "tor_tor_fetch", {
        "url": "https://example.com"
    }),
]

# Default response when no pattern matches
DEFAULT_RESPONSE = LLMResponse(
    text="I understand your request, but I don't have a specific tool to handle it in mock mode. Available operations: create/read/delete files, run commands, fetch URLs, manage tasks.",
    tool_calls=[],
    stop_reason="end_turn",
    usage={"input_tokens": 50, "output_tokens": 30}
)


class MockProvider(LLMProvider):
    """Mock LLM provider for deterministic offline testing.

    Returns pre-configured tool calls based on prompt pattern matching.
    No actual API calls are made.
    """

    @property
    def provider_type(self) -> ProviderType:
        """Return provider type (uses Anthropic format for compatibility)."""
        return ProviderType.ANTHROPIC

    def __init__(self, api_key: str, model: str, **kwargs):
        """Initialize mock provider."""
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._call_count = 0

    def _initialize_client(self) -> None:
        """Initialize mock client (no-op)."""
        self._client = None  # No actual client needed

    async def create_message(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Create a mock response based on prompt patterns.

        Args:
            messages: Conversation messages
            system_prompt: System prompt (ignored in mock)
            tools: Available tools (used for validation)
            max_tokens: Max tokens (ignored in mock)
            **kwargs: Additional arguments (ignored)

        Returns:
            LLMResponse with deterministic tool calls or text
        """
        self._call_count += 1

        # Extract the last user message
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    user_message = content.lower()
                elif isinstance(content, list):
                    # Handle content blocks
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            user_message = block.get("text", "").lower()
                            break
                break

        # Check if this is a tool result message (conversation continuation)
        if messages and messages[-1].get("role") == "user":
            content = messages[-1].get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        # Tool result received, return completion
                        return LLMResponse(
                            text="I've completed the requested operation successfully.",
                            tool_calls=[],
                            stop_reason="end_turn",
                            usage={"input_tokens": 20, "output_tokens": 10}
                        )

        # Match prompt against patterns
        available_tools = {t["name"] for t in (tools or [])} if tools else set()

        for pattern, tool_name, args in MOCK_TOOL_MAPPINGS:
            if re.search(pattern, user_message):
                # Check if the tool is available
                if not available_tools or tool_name in available_tools:
                    tool_call = ToolCall(
                        id=f"mock_call_{uuid.uuid4().hex[:8]}",
                        name=tool_name,
                        arguments=args.copy()
                    )
                    return LLMResponse(
                        text=None,
                        tool_calls=[tool_call],
                        stop_reason="tool_use",
                        usage={"input_tokens": 30, "output_tokens": 20}
                    )

        # No matching pattern - return default text response
        return DEFAULT_RESPONSE

    def convert_tool_schema(self, anthropic_schema: dict[str, Any]) -> dict[str, Any]:
        """Convert Anthropic tool schema (no-op, native format)."""
        return anthropic_schema

    def format_tool_result(self, tool_result: Any) -> dict[str, Any]:
        """Format tool result for mock provider."""
        return {
            "type": "tool_result",
            "tool_use_id": tool_result.tool_call_id,
            "content": tool_result.content if isinstance(tool_result.content, str) else str(tool_result.content),
            "is_error": tool_result.is_error,
        }

    @property
    def call_count(self) -> int:
        """Return number of create_message calls (for testing)."""
        return getattr(self, "_call_count", 0)
