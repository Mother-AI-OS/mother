"""Built-in shell plugin for Mother AI OS.

Provides shell command execution with security controls.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import socket
import getpass
from pathlib import Path
from typing import Any

from ..base import PluginBase, PluginResult
from ..manifest import (
    PluginManifest,
    PluginMetadata,
    CapabilitySpec,
    ParameterSpec,
    ParameterType,
    ExecutionSpec,
    ExecutionType,
    PythonExecutionSpec,
)


def _create_manifest() -> PluginManifest:
    """Create the shell plugin manifest programmatically."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="shell",
            version="1.0.0",
            description="Shell command execution for Mother AI OS",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Run command
            CapabilitySpec(
                name="run_command",
                description="Execute a shell command and return its output. Use for system operations, package management, git commands, etc.",
                confirmation_required=True,
                timeout=300,
                parameters=[
                    ParameterSpec(
                        name="command",
                        type=ParameterType.STRING,
                        description="The shell command to execute",
                        required=True,
                    ),
                    ParameterSpec(
                        name="cwd",
                        type=ParameterType.STRING,
                        description="Working directory for the command",
                        required=False,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Timeout in seconds (default: 60)",
                        required=False,
                        default=60,
                    ),
                    ParameterSpec(
                        name="env",
                        type=ParameterType.OBJECT,
                        description="Additional environment variables",
                        required=False,
                    ),
                ],
            ),
            # Run script
            CapabilitySpec(
                name="run_script",
                description="Execute a multi-line shell script. Useful for complex operations with multiple commands.",
                confirmation_required=True,
                timeout=600,
                parameters=[
                    ParameterSpec(
                        name="script",
                        type=ParameterType.STRING,
                        description="The shell script to execute (multi-line)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="shell",
                        type=ParameterType.STRING,
                        description="Shell to use (default: /bin/bash)",
                        required=False,
                        default="/bin/bash",
                    ),
                    ParameterSpec(
                        name="cwd",
                        type=ParameterType.STRING,
                        description="Working directory for the script",
                        required=False,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Timeout in seconds (default: 120)",
                        required=False,
                        default=120,
                    ),
                ],
            ),
            # Get environment variable
            CapabilitySpec(
                name="get_env",
                description="Get the value of an environment variable.",
                parameters=[
                    ParameterSpec(
                        name="name",
                        type=ParameterType.STRING,
                        description="Name of the environment variable",
                        required=True,
                    ),
                    ParameterSpec(
                        name="default",
                        type=ParameterType.STRING,
                        description="Default value if not set",
                        required=False,
                    ),
                ],
            ),
            # List environment variables
            CapabilitySpec(
                name="list_env",
                description="List all environment variables or filter by prefix.",
                parameters=[
                    ParameterSpec(
                        name="prefix",
                        type=ParameterType.STRING,
                        description="Filter variables by prefix (e.g., 'PATH', 'PYTHON')",
                        required=False,
                    ),
                    ParameterSpec(
                        name="include_values",
                        type=ParameterType.BOOLEAN,
                        description="Include values in output (default: true)",
                        required=False,
                        default=True,
                    ),
                ],
            ),
            # Which - find executable
            CapabilitySpec(
                name="which",
                description="Find the path to an executable in PATH.",
                parameters=[
                    ParameterSpec(
                        name="command",
                        type=ParameterType.STRING,
                        description="Name of the command to find",
                        required=True,
                    ),
                ],
            ),
            # Get current working directory
            CapabilitySpec(
                name="get_cwd",
                description="Get the current working directory.",
                parameters=[],
            ),
            # Get hostname
            CapabilitySpec(
                name="hostname",
                description="Get the system hostname.",
                parameters=[],
            ),
            # Get current user
            CapabilitySpec(
                name="whoami",
                description="Get the current username.",
                parameters=[],
            ),
            # Check if command exists
            CapabilitySpec(
                name="command_exists",
                description="Check if a command/executable exists in PATH.",
                parameters=[
                    ParameterSpec(
                        name="command",
                        type=ParameterType.STRING,
                        description="Name of the command to check",
                        required=True,
                    ),
                ],
            ),
            # Get system info
            CapabilitySpec(
                name="system_info",
                description="Get basic system information (OS, architecture, Python version).",
                parameters=[],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.shell",
                **{"class": "ShellPlugin"},
            ),
        ),
        permissions=[
            "shell:execute",
            "shell:read_env",
        ],
    )


class ShellPlugin(PluginBase):
    """Built-in plugin for shell command execution."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the shell plugin."""
        super().__init__(_create_manifest(), config)

        # Security: blocked commands that should never be executed
        self._blocked_commands = config.get("blocked_commands", []) if config else []

        # Security: allowed directories for cwd
        self._allowed_cwd: list[Path] = []
        if config and "allowed_cwd" in config:
            self._allowed_cwd = [Path(p).resolve() for p in config["allowed_cwd"]]

    def _check_command_allowed(self, command: str) -> tuple[bool, str | None]:
        """Check if a command is allowed to run.

        Returns:
            Tuple of (allowed, error_message)
        """
        # Check for blocked commands
        cmd_parts = command.split()
        if cmd_parts:
            base_cmd = cmd_parts[0]
            if base_cmd in self._blocked_commands:
                return False, f"Command '{base_cmd}' is blocked by security policy"

        # Check for dangerous patterns
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf /*",
            "> /dev/sda",
            "mkfs.",
            "dd if=",
            ":(){:|:&};:",  # Fork bomb
        ]
        for pattern in dangerous_patterns:
            if pattern in command:
                return False, f"Command contains dangerous pattern: {pattern}"

        return True, None

    def _check_cwd_allowed(self, cwd: str) -> bool:
        """Check if a working directory is allowed."""
        if not self._allowed_cwd:
            return True

        cwd_path = Path(cwd).resolve()
        return any(
            cwd_path == allowed or allowed in cwd_path.parents
            for allowed in self._allowed_cwd
        )

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a shell capability."""
        handlers = {
            "run_command": self._run_command,
            "run_script": self._run_script,
            "get_env": self._get_env,
            "list_env": self._list_env,
            "which": self._which,
            "get_cwd": self._get_cwd,
            "hostname": self._hostname,
            "whoami": self._whoami,
            "command_exists": self._command_exists,
            "system_info": self._system_info,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"Error: {e}",
                code="SHELL_ERROR",
            )

    async def _run_command(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = 60,
        env: dict[str, str] | None = None,
    ) -> PluginResult:
        """Execute a shell command."""
        # Security checks
        allowed, error = self._check_command_allowed(command)
        if not allowed:
            return PluginResult.error_result(error, code="COMMAND_BLOCKED")

        if cwd and not self._check_cwd_allowed(cwd):
            return PluginResult.error_result(
                f"Working directory not allowed: {cwd}",
                code="CWD_NOT_ALLOWED",
            )

        # Prepare environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        # Execute command
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=run_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return PluginResult.timeout_result(timeout)

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            return PluginResult.success_result(
                data={
                    "command": command,
                    "exit_code": process.returncode,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "success": process.returncode == 0,
                },
                raw_output=stdout_str if process.returncode == 0 else stderr_str,
            )

        except Exception as e:
            return PluginResult.error_result(
                f"Failed to execute command: {e}",
                code="EXECUTION_FAILED",
            )

    async def _run_script(
        self,
        script: str,
        shell: str = "/bin/bash",
        cwd: str | None = None,
        timeout: int = 120,
    ) -> PluginResult:
        """Execute a multi-line shell script."""
        # Check shell exists
        if not Path(shell).exists():
            return PluginResult.error_result(
                f"Shell not found: {shell}",
                code="SHELL_NOT_FOUND",
            )

        if cwd and not self._check_cwd_allowed(cwd):
            return PluginResult.error_result(
                f"Working directory not allowed: {cwd}",
                code="CWD_NOT_ALLOWED",
            )

        # Execute script
        try:
            process = await asyncio.create_subprocess_exec(
                shell,
                "-c",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return PluginResult.timeout_result(timeout)

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            return PluginResult.success_result(
                data={
                    "shell": shell,
                    "exit_code": process.returncode,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "success": process.returncode == 0,
                },
                raw_output=stdout_str if process.returncode == 0 else stderr_str,
            )

        except Exception as e:
            return PluginResult.error_result(
                f"Failed to execute script: {e}",
                code="EXECUTION_FAILED",
            )

    async def _get_env(
        self,
        name: str,
        default: str | None = None,
    ) -> PluginResult:
        """Get an environment variable."""
        value = os.environ.get(name, default)
        exists = name in os.environ

        return PluginResult.success_result(
            data={
                "name": name,
                "value": value,
                "exists": exists,
            }
        )

    async def _list_env(
        self,
        prefix: str | None = None,
        include_values: bool = True,
    ) -> PluginResult:
        """List environment variables."""
        env_vars = {}

        for key, value in sorted(os.environ.items()):
            if prefix and not key.startswith(prefix):
                continue

            if include_values:
                # Truncate very long values
                if len(value) > 500:
                    value = value[:500] + "..."
                env_vars[key] = value
            else:
                env_vars[key] = None

        return PluginResult.success_result(
            data={
                "count": len(env_vars),
                "prefix": prefix,
                "variables": env_vars,
            }
        )

    async def _which(self, command: str) -> PluginResult:
        """Find the path to an executable."""
        path = shutil.which(command)

        if path:
            return PluginResult.success_result(
                data={
                    "command": command,
                    "path": path,
                    "found": True,
                }
            )
        else:
            return PluginResult.success_result(
                data={
                    "command": command,
                    "path": None,
                    "found": False,
                }
            )

    async def _get_cwd(self) -> PluginResult:
        """Get current working directory."""
        cwd = os.getcwd()
        return PluginResult.success_result(
            data={
                "cwd": cwd,
                "path": str(Path(cwd).resolve()),
            }
        )

    async def _hostname(self) -> PluginResult:
        """Get system hostname."""
        hostname = socket.gethostname()
        try:
            fqdn = socket.getfqdn()
        except Exception:
            fqdn = hostname

        return PluginResult.success_result(
            data={
                "hostname": hostname,
                "fqdn": fqdn,
            }
        )

    async def _whoami(self) -> PluginResult:
        """Get current username."""
        username = getpass.getuser()
        uid = os.getuid()
        gid = os.getgid()

        return PluginResult.success_result(
            data={
                "username": username,
                "uid": uid,
                "gid": gid,
                "home": str(Path.home()),
            }
        )

    async def _command_exists(self, command: str) -> PluginResult:
        """Check if a command exists."""
        path = shutil.which(command)
        exists = path is not None

        return PluginResult.success_result(
            data={
                "command": command,
                "exists": exists,
                "path": path,
            }
        )

    async def _system_info(self) -> PluginResult:
        """Get basic system information."""
        import platform
        import sys

        return PluginResult.success_result(
            data={
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "python_version": sys.version,
                "python_executable": sys.executable,
                "hostname": socket.gethostname(),
                "username": getpass.getuser(),
            }
        )


# Export the plugin class and manifest
__all__ = ["ShellPlugin", "_create_manifest"]
