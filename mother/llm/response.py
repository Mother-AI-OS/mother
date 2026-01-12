"""Unified response types for LLM providers."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """Unified representation of a tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class ToolResult:
    """Result to send back to LLM after tool execution."""

    tool_call_id: str
    content: str
    is_error: bool = False
