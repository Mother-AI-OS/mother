"""Base class for tool wrappers.

DEPRECATED: This module provides legacy tool wrapper functionality.
New tools should be implemented as plugins using mother.plugins.base.PluginBase.

The plugin system provides:
- Async execution
- Better type safety with Pydantic
- Automatic schema generation
- Graceful degradation

Legacy tools will continue to work but are not recommended for new development.
"""

import os
import subprocess
import time
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    type: str  # string, integer, boolean, array, choice
    description: str = ""
    required: bool = False
    flag: str | None = None  # e.g., "--account"
    positional: bool = False
    default: Any = None
    choices: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """Result from tool execution."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    parsed_data: Any | None = None
    error_message: str | None = None
    execution_time: float = 0.0
    command: list[str] = field(default_factory=list)


class ToolWrapper(ABC):
    """Abstract base class for CLI tool wrappers.

    DEPRECATED: Use mother.plugins.base.PluginBase instead.
    This class is maintained for backward compatibility only.
    """

    _deprecation_warned: set = set()

    def __init__(
        self,
        binary: str,
        env_vars: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout: int = 300,
        extra_args: list[str] | None = None,
    ):
        # Warn once per class
        cls_name = self.__class__.__name__
        if cls_name not in ToolWrapper._deprecation_warned:
            ToolWrapper._deprecation_warned.add(cls_name)
            warnings.warn(
                f"{cls_name} uses deprecated ToolWrapper. "
                f"Consider using the plugin system instead (mother.plugins.base.PluginBase).",
                DeprecationWarning,
                stacklevel=2,
            )

        self.binary = binary
        self.env_vars = env_vars or {}
        self.cwd = cwd
        self.timeout = timeout
        self.extra_args = extra_args or []

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for identification."""
        pass

    @property
    def description(self) -> str:
        """Tool description."""
        return self.__doc__ or f"{self.name} CLI wrapper"

    @abstractmethod
    def get_commands(self) -> dict[str, dict]:
        """Return available commands with their schemas."""
        pass

    def get_anthropic_tool_schema(self, command: str) -> dict:
        """Generate Anthropic tool_use compatible schema."""
        cmd_def = self.get_commands().get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        properties = {}
        required = []

        for param in cmd_def.get("parameters", []):
            prop_def = {"description": param.get("description", param["name"])}

            if param["type"] == "string":
                prop_def["type"] = "string"
            elif param["type"] == "integer":
                prop_def["type"] = "integer"
            elif param["type"] == "boolean":
                prop_def["type"] = "boolean"
            elif param["type"] == "array":
                prop_def["type"] = "array"
                prop_def["items"] = {"type": "string"}
            elif param["type"] == "choice":
                prop_def["type"] = "string"
                prop_def["enum"] = param.get("choices", [])

            if param.get("default") is not None:
                prop_def["default"] = param["default"]

            properties[param["name"]] = prop_def

            if param.get("required", False):
                required.append(param["name"])

        return {
            "name": f"{self.name}_{command.replace('.', '_')}",
            "description": cmd_def.get("description", ""),
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def build_command(self, command: str, args: dict[str, Any]) -> list[str]:
        """Build command line arguments from structured input."""
        cmd_def = self.get_commands().get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Start with binary and extra args
        cmd_parts = [self.binary] + self.extra_args

        # Handle subcommands (e.g., "elster.vat" -> "elster" "vat")
        if "." in command:
            cmd_parts.extend(command.split("."))
        else:
            cmd_parts.append(command)

        # Collect positional args (must be added last)
        positional_args = []

        # Add parameters
        for param_def in cmd_def.get("parameters", []):
            param_name = param_def["name"]
            value = args.get(param_name)

            if value is None:
                if param_def.get("required"):
                    raise ValueError(f"Missing required parameter: {param_name}")
                continue

            if param_def.get("positional"):
                positional_args.append((param_def.get("position", 999), str(value)))
            elif param_def.get("flag"):
                if param_def["type"] == "boolean":
                    if value:
                        cmd_parts.append(param_def["flag"])
                elif param_def["type"] == "array":
                    for item in value:
                        cmd_parts.extend([param_def["flag"], str(item)])
                else:
                    cmd_parts.extend([param_def["flag"], str(value)])

        # Add positional args in order
        positional_args.sort(key=lambda x: x[0])
        for _, value in positional_args:
            cmd_parts.append(value)

        return cmd_parts

    def execute(self, command: str, args: dict[str, Any]) -> ToolResult:
        """Execute the command and return structured result."""
        start_time = time.time()

        try:
            cmd = self.build_command(command, args)

            # Prepare environment
            env = os.environ.copy()
            env.update(self.env_vars)

            # Execute
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
                env=env,
            )

            execution_time = time.time() - start_time

            # Parse output
            parsed_data = self.parse_output(command, result.stdout, result.stderr)

            # Check for errors
            error_message = None
            if result.returncode != 0:
                error_message = self.extract_error(result.stderr or result.stdout)

            return ToolResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                parsed_data=parsed_data,
                error_message=error_message,
                execution_time=execution_time,
                command=cmd,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Command timed out",
                error_message=f"Command timed out after {self.timeout}s",
                execution_time=time.time() - start_time,
                command=[],
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Binary not found: {self.binary}",
                error_message=f"Tool binary not found: {self.binary}",
                execution_time=time.time() - start_time,
                command=[],
            )
        except Exception as e:
            return ToolResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                error_message=str(e),
                execution_time=time.time() - start_time,
                command=[],
            )

    @abstractmethod
    def parse_output(self, command: str, stdout: str, stderr: str) -> Any | None:
        """Parse command output into structured data."""
        pass

    def extract_error(self, output: str) -> str | None:
        """Extract error message from output."""
        import re

        from ..parsers.output import strip_ansi

        clean = strip_ansi(output)

        # Look for common error patterns
        patterns = [
            r"Error:\s*(.+)",
            r"Failed to\s*(.+)",
            r"error:\s*(.+)",
            r"Exception:\s*(.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, clean, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Return first non-empty line as fallback
        for line in clean.split("\n"):
            line = line.strip()
            if line:
                return line[:200]

        return None

    def is_confirmation_required(self, command: str) -> bool:
        """Check if command requires user confirmation."""
        cmd_def = self.get_commands().get(command, {})
        return cmd_def.get("confirmation_required", False)
