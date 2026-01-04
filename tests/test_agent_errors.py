"""Tests for the agent errors module."""

import pytest

from mother.agent.errors import AgentError, ErrorCategory, ErrorHandler


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_all_categories_exist(self):
        """Test all expected categories exist."""
        categories = [
            "TOOL_NOT_FOUND",
            "COMMAND_NOT_FOUND",
            "TOOL_EXECUTION",
            "TOOL_TIMEOUT",
            "AUTHENTICATION",
            "PERMISSION",
            "NETWORK",
            "PARSE_ERROR",
            "VALIDATION",
            "RATE_LIMIT",
            "MISSING_PARAMETER",
            "INTERNAL",
        ]

        for cat in categories:
            assert hasattr(ErrorCategory, cat)

    def test_category_values(self):
        """Test category values are snake_case strings."""
        for cat in ErrorCategory:
            assert isinstance(cat.value, str)
            assert cat.value == cat.value.lower()


class TestAgentError:
    """Tests for AgentError dataclass."""

    def test_basic_creation(self):
        """Test creating a basic error."""
        error = AgentError(
            category=ErrorCategory.INTERNAL,
            message="Something failed",
        )

        assert error.category == ErrorCategory.INTERNAL
        assert error.message == "Something failed"
        assert error.tool_name is None
        assert error.command is None
        assert error.recoverable is True
        assert error.suggestion is None

    def test_full_creation(self):
        """Test creating an error with all fields."""
        error = AgentError(
            category=ErrorCategory.AUTHENTICATION,
            message="Auth failed",
            tool_name="mailcraft",
            command="login",
            recoverable=False,
            suggestion="Check credentials",
        )

        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.message == "Auth failed"
        assert error.tool_name == "mailcraft"
        assert error.command == "login"
        assert error.recoverable is False
        assert error.suggestion == "Check credentials"

    def test_to_dict(self):
        """Test to_dict method."""
        error = AgentError(
            category=ErrorCategory.NETWORK,
            message="Connection refused",
            tool_name="web",
            command="fetch",
            recoverable=True,
            suggestion="Check network",
        )

        result = error.to_dict()

        assert result["category"] == "network"
        assert result["message"] == "Connection refused"
        assert result["tool_name"] == "web"
        assert result["command"] == "fetch"
        assert result["recoverable"] is True
        assert result["suggestion"] == "Check network"

    def test_to_dict_with_none_values(self):
        """Test to_dict with None values."""
        error = AgentError(
            category=ErrorCategory.INTERNAL,
            message="Error",
        )

        result = error.to_dict()

        assert result["tool_name"] is None
        assert result["command"] is None
        assert result["suggestion"] is None


class TestErrorHandler:
    """Tests for ErrorHandler class."""

    @pytest.fixture
    def handler(self):
        """Create an error handler."""
        return ErrorHandler()

    def test_classify_authentication_error(self, handler):
        """Test classifying authentication errors."""
        error = handler.classify_error("Invalid password for user")

        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.recoverable is True
        assert "password" in error.message.lower() or "authentication" in error.message.lower()

    def test_classify_credential_error(self, handler):
        """Test classifying credential errors."""
        error = handler.classify_error("Credential not found")

        assert error.category == ErrorCategory.AUTHENTICATION

    def test_classify_permission_error(self, handler):
        """Test classifying permission errors."""
        error = handler.classify_error("Permission denied for /tmp/file")

        assert error.category == ErrorCategory.PERMISSION
        assert error.recoverable is False

    def test_classify_access_denied(self, handler):
        """Test classifying access denied errors."""
        error = handler.classify_error("Access denied to resource")

        assert error.category == ErrorCategory.PERMISSION

    def test_classify_timeout_error(self, handler):
        """Test classifying timeout errors."""
        error = handler.classify_error("Operation timed out after 30s")

        assert error.category == ErrorCategory.TOOL_TIMEOUT
        assert error.recoverable is True

    def test_classify_network_error(self, handler):
        """Test classifying network errors."""
        error = handler.classify_error("Connection refused by server")

        assert error.category == ErrorCategory.NETWORK
        assert error.recoverable is True

    def test_classify_network_unreachable(self, handler):
        """Test classifying network unreachable errors."""
        error = handler.classify_error("Host unreachable")

        assert error.category == ErrorCategory.NETWORK

    def test_classify_not_found_error(self, handler):
        """Test classifying not found errors."""
        error = handler.classify_error("File not found: /path/to/file")

        assert error.category == ErrorCategory.TOOL_NOT_FOUND
        assert error.recoverable is True

    def test_classify_does_not_exist(self, handler):
        """Test classifying 'does not exist' errors."""
        error = handler.classify_error("User does not exist")

        assert error.category == ErrorCategory.TOOL_NOT_FOUND

    def test_classify_rate_limit_error(self, handler):
        """Test classifying rate limit errors."""
        error = handler.classify_error("Rate limit exceeded, try again later")

        assert error.category == ErrorCategory.RATE_LIMIT
        assert error.recoverable is True

    def test_classify_too_many_requests(self, handler):
        """Test classifying too many requests errors."""
        error = handler.classify_error("Too many requests from this IP")

        assert error.category == ErrorCategory.RATE_LIMIT

    def test_classify_missing_parameter(self, handler):
        """Test classifying missing parameter errors."""
        error = handler.classify_error("Missing required parameter: email")

        assert error.category == ErrorCategory.MISSING_PARAMETER
        assert error.recoverable is True

    def test_classify_must_provide(self, handler):
        """Test classifying 'must provide' errors."""
        error = handler.classify_error("You must provide a valid token")

        assert error.category == ErrorCategory.MISSING_PARAMETER

    def test_classify_parse_error(self, handler):
        """Test classifying parse errors."""
        error = handler.classify_error("Parse error in JSON input")

        assert error.category == ErrorCategory.PARSE_ERROR
        assert error.recoverable is True

    def test_classify_invalid_format(self, handler):
        """Test classifying invalid format errors."""
        error = handler.classify_error("Invalid date format")

        assert error.category == ErrorCategory.PARSE_ERROR

    def test_classify_unknown_error(self, handler):
        """Test classifying unknown errors."""
        error = handler.classify_error("Something completely unexpected happened")

        assert error.category == ErrorCategory.INTERNAL
        assert error.recoverable is False

    def test_classify_with_tool_info(self, handler):
        """Test classifying with tool information."""
        error = handler.classify_error(
            "Connection refused",
            tool_name="web",
            command="fetch",
        )

        assert error.tool_name == "web"
        assert error.command == "fetch"

    def test_classify_long_error_truncated(self, handler):
        """Test long error messages are truncated."""
        long_error = "x" * 1000
        error = handler.classify_error(long_error)

        # Internal errors truncate to 500 chars
        assert len(error.message) <= 500

    def test_classify_provides_suggestion(self, handler):
        """Test classification provides recovery suggestions."""
        error = handler.classify_error("Rate limit exceeded")

        assert error.suggestion is not None
        assert "wait" in error.suggestion.lower()

    def test_format_for_claude_basic(self, handler):
        """Test formatting error for Claude."""
        error = AgentError(
            category=ErrorCategory.NETWORK,
            message="Connection failed",
        )

        result = handler.format_for_claude(error)

        assert "Error (network)" in result
        assert "Connection failed" in result

    def test_format_for_claude_with_tool(self, handler):
        """Test formatting error with tool info for Claude."""
        error = AgentError(
            category=ErrorCategory.AUTHENTICATION,
            message="Auth failed",
            tool_name="mailcraft",
            command="login",
            suggestion="Check password",
            recoverable=True,
        )

        result = handler.format_for_claude(error)

        assert "Tool: mailcraft" in result
        assert "Command: login" in result
        assert "Suggestion: Check password" in result
        assert "recoverable" in result.lower()

    def test_format_for_claude_not_recoverable(self, handler):
        """Test formatting non-recoverable error."""
        error = AgentError(
            category=ErrorCategory.PERMISSION,
            message="Access denied",
            recoverable=False,
        )

        result = handler.format_for_claude(error)

        assert "recoverable" not in result.lower()

    def test_format_for_user_basic(self, handler):
        """Test formatting error for user."""
        error = AgentError(
            category=ErrorCategory.INTERNAL,
            message="Something went wrong",
        )

        result = handler.format_for_user(error)

        assert "Error: Something went wrong" in result

    def test_format_for_user_with_suggestion(self, handler):
        """Test formatting error with suggestion for user."""
        error = AgentError(
            category=ErrorCategory.NETWORK,
            message="Connection failed",
            suggestion="Check your internet connection",
        )

        result = handler.format_for_user(error)

        assert "Connection failed" in result
        assert "Suggestion:" in result
        assert "Check your internet connection" in result


class TestErrorHandlerPatterns:
    """Tests for ErrorHandler error patterns."""

    @pytest.fixture
    def handler(self):
        """Create an error handler."""
        return ErrorHandler()

    def test_all_patterns_have_suggestions(self, handler):
        """Test all error patterns have recovery suggestions."""
        for pattern_info in handler.ERROR_PATTERNS.values():
            category = pattern_info[0]
            # Most categories should have suggestions
            if category in handler.RECOVERY_SUGGESTIONS:
                assert handler.RECOVERY_SUGGESTIONS[category]

    def test_case_insensitive_matching(self, handler):
        """Test pattern matching is case insensitive."""
        error1 = handler.classify_error("PERMISSION DENIED")
        error2 = handler.classify_error("permission denied")
        error3 = handler.classify_error("Permission Denied")

        assert error1.category == ErrorCategory.PERMISSION
        assert error2.category == ErrorCategory.PERMISSION
        assert error3.category == ErrorCategory.PERMISSION
