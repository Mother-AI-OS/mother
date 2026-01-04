"""Error handling for the Mother Agent."""

import re
from dataclasses import dataclass
from enum import Enum


class ErrorCategory(Enum):
    """Categories of errors for appropriate handling."""

    TOOL_NOT_FOUND = "tool_not_found"
    COMMAND_NOT_FOUND = "command_not_found"
    TOOL_EXECUTION = "tool_execution"
    TOOL_TIMEOUT = "tool_timeout"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    NETWORK = "network"
    PARSE_ERROR = "parse_error"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    MISSING_PARAMETER = "missing_parameter"
    INTERNAL = "internal"


@dataclass
class AgentError:
    """Structured error information."""

    category: ErrorCategory
    message: str
    tool_name: str | None = None
    command: str | None = None
    recoverable: bool = True
    suggestion: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "message": self.message,
            "tool_name": self.tool_name,
            "command": self.command,
            "recoverable": self.recoverable,
            "suggestion": self.suggestion,
        }


class ErrorHandler:
    """Handles errors from tool execution."""

    # Pattern -> (category, base_message, recoverable)
    ERROR_PATTERNS = {
        r"password|credential|auth|login": (
            ErrorCategory.AUTHENTICATION,
            "Authentication failed",
            True,
        ),
        r"permission denied|access denied|forbidden": (
            ErrorCategory.PERMISSION,
            "Permission denied",
            False,
        ),
        r"timeout|timed out": (
            ErrorCategory.TOOL_TIMEOUT,
            "Operation timed out",
            True,
        ),
        r"connection|network|unreachable|refused": (
            ErrorCategory.NETWORK,
            "Network connection failed",
            True,
        ),
        r"not found|does not exist|no such": (
            ErrorCategory.TOOL_NOT_FOUND,
            "Resource not found",
            True,
        ),
        r"rate limit|too many requests|throttl": (
            ErrorCategory.RATE_LIMIT,
            "Rate limit exceeded",
            True,
        ),
        r"missing|required|must provide": (
            ErrorCategory.MISSING_PARAMETER,
            "Missing required parameter",
            True,
        ),
        r"invalid|malformed|parse error": (
            ErrorCategory.PARSE_ERROR,
            "Invalid input format",
            True,
        ),
    }

    RECOVERY_SUGGESTIONS = {
        ErrorCategory.AUTHENTICATION: (
            "Check that MAILCRAFT_PASSWORD or other credentials are set correctly in the environment or .env file."
        ),
        ErrorCategory.PERMISSION: (
            "Verify file permissions and folder access. You may need to run with elevated privileges or fix ownership."
        ),
        ErrorCategory.TOOL_TIMEOUT: (
            "The operation took too long. Try with a smaller limit, narrower date range, or different parameters."
        ),
        ErrorCategory.NETWORK: (
            "Check your network connection. The remote server may be temporarily unavailable - try again in a moment."
        ),
        ErrorCategory.TOOL_NOT_FOUND: (
            "The requested resource doesn't exist. Verify the ID or path is correct, "
            "or try listing available items first."
        ),
        ErrorCategory.RATE_LIMIT: ("You've made too many requests. Wait a few minutes before retrying."),
        ErrorCategory.MISSING_PARAMETER: (
            "A required parameter is missing. Check the command syntax and provide all required values."
        ),
        ErrorCategory.PARSE_ERROR: ("The input format is invalid. Check the expected format for this command."),
        ErrorCategory.COMMAND_NOT_FOUND: (
            "This command doesn't exist for this tool. Use a different command or check available commands."
        ),
    }

    def classify_error(
        self,
        error_text: str,
        tool_name: str | None = None,
        command: str | None = None,
    ) -> AgentError:
        """Classify an error and provide recovery suggestion."""
        error_lower = error_text.lower()

        for pattern, (category, message, recoverable) in self.ERROR_PATTERNS.items():
            if re.search(pattern, error_lower):
                return AgentError(
                    category=category,
                    message=f"{message}: {error_text[:200]}",
                    tool_name=tool_name,
                    command=command,
                    recoverable=recoverable,
                    suggestion=self.RECOVERY_SUGGESTIONS.get(category),
                )

        # Default to internal error
        return AgentError(
            category=ErrorCategory.INTERNAL,
            message=error_text[:500],
            tool_name=tool_name,
            command=command,
            recoverable=False,
            suggestion="An unexpected error occurred. Check the tool output for details.",
        )

    def format_for_claude(self, error: AgentError) -> str:
        """Format error for Claude to understand and potentially recover."""
        parts = [f"Error ({error.category.value}): {error.message}"]

        if error.tool_name:
            parts.append(f"Tool: {error.tool_name}")
        if error.command:
            parts.append(f"Command: {error.command}")
        if error.suggestion:
            parts.append(f"Suggestion: {error.suggestion}")
        if error.recoverable:
            parts.append(
                "This error may be recoverable. Consider trying with different parameters or an alternative approach."
            )

        return "\n".join(parts)

    def format_for_user(self, error: AgentError) -> str:
        """Format error for user-friendly display."""
        lines = [f"Error: {error.message}"]

        if error.suggestion:
            lines.append(f"\nSuggestion: {error.suggestion}")

        return "\n".join(lines)
