"""FastAPI routes for the Mother Agent API."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from .schemas import (
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
from .auth import verify_api_key
from ..agent.core import MotherAgent
from ..tools.registry import ToolRegistry
from ..config.settings import get_settings
from .. import __version__


router = APIRouter()

# These will be initialized by the app
_registry: Optional[ToolRegistry] = None
_agent: Optional[MotherAgent] = None


def init_dependencies(registry: ToolRegistry, agent: MotherAgent) -> None:
    """Initialize global dependencies."""
    global _registry, _agent
    _registry = registry
    _agent = agent


def get_registry() -> ToolRegistry:
    """Get tool registry dependency."""
    if _registry is None:
        raise HTTPException(status_code=500, detail="Tool registry not initialized")
    return _registry


def get_agent() -> MotherAgent:
    """Get agent dependency."""
    if _agent is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    return _agent


@router.post("/command", response_model=CommandResponse)
async def execute_command(
    request: CommandRequest,
    _: str = Depends(verify_api_key),
    agent: MotherAgent = Depends(get_agent),
) -> CommandResponse:
    """
    Execute a natural language command.

    The agent will:
    1. Parse the command using Claude
    2. Determine which tools to use
    3. Execute the tools
    4. Return a natural language response

    Examples:
    - "Show me my 10 latest unread emails"
    - "Fetch new leads and show AI-related ones"
    - "Search for invoices from December"
    - "Send an email to john@example.com about the meeting"
    """
    try:
        result = await agent.process_command(
            user_input=request.command,
            session_id=request.session_id,
            pre_confirmed=request.pre_confirmed,
        )

        # Convert to response model
        tool_calls = [
            ToolCall(
                tool=tc["tool"],
                args=tc.get("args", {}),
                success=tc["success"],
                execution_time=tc["execution_time"],
            )
            for tc in result.tool_calls
        ]

        pending = None
        if result.pending_confirmation:
            pc = result.pending_confirmation
            pending = PendingConfirmationResponse(
                id=pc.id,
                tool_name=pc.tool_name,
                command=pc.command,
                args=pc.args,
                description=pc.description,
            )

        errors = [
            ErrorResponse(
                category=e.category.value,
                message=e.message,
                tool_name=e.tool_name,
                command=e.command,
                recoverable=e.recoverable,
                suggestion=e.suggestion,
            )
            for e in result.errors
        ]

        return CommandResponse(
            success=result.success,
            response=result.text,
            session_id=agent.get_session_id(),
            tool_calls=tool_calls,
            pending_confirmation=pending,
            errors=errors,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/command/{session_id}/confirm", response_model=CommandResponse)
async def confirm_action(
    session_id: str,
    request: ConfirmRequest,
    _: str = Depends(verify_api_key),
    agent: MotherAgent = Depends(get_agent),
) -> CommandResponse:
    """
    Confirm a pending destructive action.

    After receiving a response with pending_confirmation, call this endpoint
    with the confirmation_id to execute the action.
    """
    # Verify session matches
    if agent.get_session_id() != session_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID mismatch. The action may have expired.",
        )

    try:
        result = await agent.confirm_action(request.confirmation_id)

        errors = [
            ErrorResponse(
                category=e.category.value,
                message=e.message,
                tool_name=e.tool_name,
                command=e.command,
                recoverable=e.recoverable,
                suggestion=e.suggestion,
            )
            for e in result.errors
        ]

        return CommandResponse(
            success=result.success,
            response=result.text,
            session_id=session_id,
            errors=errors,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools", response_model=ToolListResponse)
async def list_tools(
    _: str = Depends(verify_api_key),
    registry: ToolRegistry = Depends(get_registry),
) -> ToolListResponse:
    """List all available tools and their commands."""
    tools_info = registry.list_tools()

    tools = [
        ToolInfo(
            name=name,
            description=info["description"],
            commands=info["commands"],
        )
        for name, info in tools_info.items()
    ]

    return ToolListResponse(tools=tools)


@router.get("/tools/{tool_name}", response_model=ToolDetailResponse)
async def get_tool_details(
    tool_name: str,
    _: str = Depends(verify_api_key),
    registry: ToolRegistry = Depends(get_registry),
) -> ToolDetailResponse:
    """Get detailed information about a specific tool."""
    details = registry.get_tool_details(tool_name)

    if not details:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found",
        )

    return ToolDetailResponse(
        name=details["name"],
        description=details["description"],
        commands=details["commands"],
    )


@router.post("/tools/{tool_name}/{command}", response_model=ToolExecuteResponse)
async def execute_tool_directly(
    tool_name: str,
    command: str,
    request: ToolExecuteRequest,
    _: str = Depends(verify_api_key),
    registry: ToolRegistry = Depends(get_registry),
) -> ToolExecuteResponse:
    """
    Execute a tool command directly without AI interpretation.

    Useful for:
    - Testing individual tools
    - Scripted automation
    - Debugging
    """
    wrapper = registry.get_wrapper(tool_name)
    if not wrapper:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found",
        )

    if command not in wrapper.get_commands():
        raise HTTPException(
            status_code=404,
            detail=f"Command '{command}' not found in tool '{tool_name}'",
        )

    result = wrapper.execute(command, request.args)

    return ToolExecuteResponse(
        success=result.success,
        exit_code=result.exit_code,
        output=result.parsed_data or result.stdout,
        error=result.error_message,
        execution_time=result.execution_time,
    )


@router.get("/status", response_model=StatusResponse)
async def get_status(
    registry: ToolRegistry = Depends(get_registry),
    agent: MotherAgent = Depends(get_agent),
) -> StatusResponse:
    """Get agent status and health check."""
    settings = get_settings()
    memory_stats = agent.get_memory_stats()

    return StatusResponse(
        status="healthy",
        version=__version__,
        available_tools=len(registry.wrappers),
        model=settings.claude_model,
        memory_stats=memory_stats,
    )


@router.get("/memory/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    _: str = Depends(verify_api_key),
    agent: MotherAgent = Depends(get_agent),
) -> MemoryStatsResponse:
    """Get memory statistics."""
    stats = agent.get_memory_stats()

    if not stats:
        raise HTTPException(status_code=404, detail="Memory not enabled")

    return MemoryStatsResponse(
        total_memories=stats.get("total_memories", 0),
        total_sessions=stats.get("total_sessions", 0),
        memories_with_embeddings=stats.get("memories_with_embeddings", 0),
    )


@router.post("/memory/search", response_model=MemorySearchResponse)
async def search_memory(
    request: MemorySearchRequest,
    _: str = Depends(verify_api_key),
    agent: MotherAgent = Depends(get_agent),
) -> MemorySearchResponse:
    """Search memories by semantic similarity."""
    results = agent.search_memory(request.query, limit=request.limit)

    items = [
        MemoryItem(
            content=r["content"],
            role=r["role"],
            timestamp=r["timestamp"],
            similarity=r.get("similarity"),
        )
        for r in results
    ]

    return MemorySearchResponse(
        results=items,
        total=len(items),
    )


# Planning mode endpoints

@router.post("/plan", response_model=PlanCommandResponse)
async def create_plan(
    request: PlanCommandRequest,
    _: str = Depends(verify_api_key),
    agent: MotherAgent = Depends(get_agent),
) -> PlanCommandResponse:
    """
    Create an execution plan for a multi-step task.

    Returns a plan with steps that can be reviewed before execution.
    Use POST /plan/{session_id}/execute to run the plan after approval.

    Examples:
    - "Merge all invoices from Downloads and email them to my accountant"
    - "Fetch new emails, categorize them, and summarize unread ones"
    - "Process all PDFs in Documents and add them to the knowledge base"
    """
    try:
        result = await agent.create_plan(
            user_input=request.command,
            session_id=request.session_id,
        )

        # Convert plan to response model
        plan_response = None
        if result.pending_plan:
            p = result.pending_plan
            steps = [
                PlanStepResponse(
                    order=s.order,
                    tool_name=s.tool_name,
                    command=s.command,
                    args=s.args,
                    description=s.description,
                    status=s.status.value,
                    depends_on=s.depends_on,
                )
                for s in p.steps
            ]
            plan_response = PlanResponse(
                id=p.id,
                goal=p.goal,
                steps=steps,
                status=p.status,
                created_at=p.created_at,
            )

        errors = [
            ErrorResponse(
                category=e.category.value,
                message=e.message,
                tool_name=e.tool_name,
                command=e.command,
                recoverable=e.recoverable,
                suggestion=e.suggestion,
            )
            for e in result.errors
        ]

        return PlanCommandResponse(
            success=result.success,
            response=result.text,
            session_id=agent.get_session_id(),
            plan=plan_response,
            errors=errors,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan/{session_id}/execute", response_model=PlanCommandResponse)
async def execute_plan(
    session_id: str,
    request: PlanApproveRequest,
    _: str = Depends(verify_api_key),
    agent: MotherAgent = Depends(get_agent),
) -> PlanCommandResponse:
    """
    Execute or cancel a pending plan.

    After creating a plan with POST /plan, use this endpoint to:
    - Execute it (approve: true)
    - Cancel it (approve: false)
    """
    # Verify session matches
    if agent.get_session_id() != session_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID mismatch. The plan may have expired.",
        )

    try:
        if request.approve:
            result = await agent.execute_plan()
        else:
            agent.state.pending_plan = None
            from ..agent.core import AgentResponse
            result = AgentResponse(text="Plan cancelled.", success=True)

        # Convert tool calls
        tool_calls = [
            ToolCall(
                tool=tc["tool"],
                args=tc.get("args", {}),
                success=tc["success"],
                execution_time=tc["execution_time"],
            )
            for tc in result.tool_calls
        ]

        errors = [
            ErrorResponse(
                category=e.category.value,
                message=e.message,
                tool_name=e.tool_name,
                command=e.command,
                recoverable=e.recoverable,
                suggestion=e.suggestion,
            )
            for e in result.errors
        ]

        return PlanCommandResponse(
            success=result.success,
            response=result.text,
            session_id=session_id,
            tool_calls=tool_calls,
            errors=errors,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
