"""Pydantic schemas for API requests and responses."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    """Request to execute a natural language command."""

    command: str = Field(..., description="Natural language command to execute")
    session_id: Optional[str] = Field(
        None, description="Session ID for context continuity"
    )
    pre_confirmed: bool = Field(
        False, description="Pre-confirm destructive actions (use with caution)"
    )


class ConfirmRequest(BaseModel):
    """Request to confirm a pending action."""

    confirmation_id: str = Field(..., description="ID of the action to confirm")


class ToolCall(BaseModel):
    """Information about a tool call made by the agent."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    success: bool
    execution_time: float


class PendingConfirmationResponse(BaseModel):
    """A pending action requiring confirmation."""

    id: str
    tool_name: str
    command: str
    args: dict[str, Any]
    description: str


class ErrorResponse(BaseModel):
    """Error information."""

    category: str
    message: str
    tool_name: Optional[str] = None
    command: Optional[str] = None
    recoverable: bool = True
    suggestion: Optional[str] = None


class CommandResponse(BaseModel):
    """Response from command execution."""

    success: bool
    response: str
    session_id: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    pending_confirmation: Optional[PendingConfirmationResponse] = None
    errors: list[ErrorResponse] = Field(default_factory=list)


class ToolInfo(BaseModel):
    """Information about an available tool."""

    name: str
    description: str
    commands: list[str]


class ToolListResponse(BaseModel):
    """Response listing available tools."""

    tools: list[ToolInfo]


class ToolDetailResponse(BaseModel):
    """Detailed information about a tool."""

    name: str
    description: str
    commands: dict[str, dict[str, Any]]


class ToolExecuteRequest(BaseModel):
    """Request to execute a tool directly."""

    args: dict[str, Any] = Field(default_factory=dict)


class ToolExecuteResponse(BaseModel):
    """Response from direct tool execution."""

    success: bool
    exit_code: int
    output: Any
    error: Optional[str] = None
    execution_time: float


class StatusResponse(BaseModel):
    """Agent status response."""

    status: str
    version: str
    available_tools: int
    model: str
    memory_stats: Optional[dict] = None


class MemorySearchRequest(BaseModel):
    """Request to search memory."""

    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Maximum results")


class MemoryItem(BaseModel):
    """A single memory item."""

    content: str
    role: str
    timestamp: str
    similarity: Optional[float] = None


class MemorySearchResponse(BaseModel):
    """Response from memory search."""

    results: list[MemoryItem]
    total: int


class MemoryStatsResponse(BaseModel):
    """Memory statistics."""

    total_memories: int
    total_sessions: int
    memories_with_embeddings: int


# Planning mode schemas

class PlanStepResponse(BaseModel):
    """A single step in an execution plan."""

    order: int
    tool_name: str
    command: str
    args: dict[str, Any]
    description: str
    status: str
    depends_on: list[str] = Field(default_factory=list)


class PlanResponse(BaseModel):
    """An execution plan for a multi-step task."""

    id: str
    goal: str
    steps: list[PlanStepResponse]
    status: str
    created_at: str


class PlanCommandRequest(BaseModel):
    """Request to create or execute a plan."""

    command: str = Field(..., description="Natural language command to plan")
    session_id: Optional[str] = Field(
        None, description="Session ID for context continuity"
    )


class PlanCommandResponse(BaseModel):
    """Response from plan creation or execution."""

    success: bool
    response: str
    session_id: str
    plan: Optional[PlanResponse] = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    errors: list[ErrorResponse] = Field(default_factory=list)


class PlanApproveRequest(BaseModel):
    """Request to approve and execute a pending plan."""

    approve: bool = Field(..., description="True to execute, False to cancel")
