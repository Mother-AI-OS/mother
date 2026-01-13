"""Execution backends for Mother plugins.

This module provides different execution strategies for plugins:
- PythonExecutor: Direct Python class execution
- CLIExecutor: Subprocess-based CLI execution
- (Future) DockerExecutor: Container-based execution
- (Future) HTTPExecutor: REST API-based execution
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import shutil
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import PluginBase, PluginResult
from .exceptions import (
    ExecutionError,
    PluginLoadError,
    PluginTimeoutError,
    PolicyViolationError,
)

if TYPE_CHECKING:
    from .manifest import (
        CapabilitySpec,
        CLIExecutionSpec,
        PluginManifest,
        PythonExecutionSpec,
    )

logger = logging.getLogger("mother.plugins.executor")


class _FlexiblePluginWrapper(PluginBase):
    """Wrapper for plugins that don't extend PluginBase but have execute()."""

    def __init__(self, instance: Any, manifest: PluginManifest):
        """Initialize the wrapper.

        Args:
            instance: The plugin instance with execute() method
            manifest: Plugin manifest
        """
        super().__init__(manifest, {})
        self._instance = instance

    async def initialize(self) -> None:
        """Initialize the wrapped plugin if it has initialize()."""
        if hasattr(self._instance, "initialize"):
            init_result = self._instance.initialize()
            if asyncio.iscoroutine(init_result):
                await init_result

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a capability via the wrapped instance."""
        from .base import PluginResult

        result = self._instance.execute(capability, params)
        if asyncio.iscoroutine(result):
            result = await result

        # Convert dict result to PluginResult
        if isinstance(result, PluginResult):
            return result
        elif isinstance(result, dict):
            return PluginResult.success_result(data=result)
        else:
            return PluginResult.success_result(data={"result": result})

    async def shutdown(self) -> None:
        """Shutdown the wrapped plugin if it has shutdown()."""
        if hasattr(self._instance, "shutdown"):
            shutdown_result = self._instance.shutdown()
            if asyncio.iscoroutine(shutdown_result):
                await shutdown_result


class ExecutorBase(ABC):
    """Abstract base class for plugin execution backends."""

    def __init__(self, manifest: PluginManifest, config: dict[str, Any] | None = None):
        """Initialize the executor.

        Args:
            manifest: Plugin manifest
            config: Plugin configuration values
        """
        self.manifest = manifest
        self.config = config or {}
        self._plugin: PluginBase | None = None

    @property
    def plugin_name(self) -> str:
        """Get the plugin name."""
        return self.manifest.plugin.name

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the executor and load the plugin."""
        ...

    @abstractmethod
    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        identity: Any | None = None,
    ) -> PluginResult:
        """Execute a capability with parameters.

        Args:
            capability: Name of the capability to execute
            params: Parameters for the capability
            identity: IdentityContext from authentication (for scope checking)

        Returns:
            PluginResult with execution outcome
        """
        ...

    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self._plugin:
            await self._plugin.shutdown()

    def get_timeout(self, capability: str) -> int:
        """Get timeout for a capability.

        Args:
            capability: Capability name

        Returns:
            Timeout in seconds
        """
        cap = self.manifest.get_capability(capability)
        if cap and cap.timeout:
            return cap.timeout
        return self.config.get("timeout", 300)

    def check_scope(
        self,
        capability: str,
        identity: Any | None = None,
    ) -> None:
        """Check if identity has required scope for capability.

        This is checked BEFORE policy evaluation for scope-based access control.

        Args:
            capability: The capability name being executed
            identity: IdentityContext from authentication (None for legacy mode)

        Raises:
            PolicyViolationError: If scope check fails
        """
        try:
            from ..auth.scopes import check_scope as do_check_scope
        except ImportError:
            # Auth module not available - allow by default
            logger.debug("Auth scopes module not available - skipping scope check")
            return

        allowed, reason = do_check_scope(identity, capability)
        if not allowed:
            logger.warning(f"Scope check failed: {capability} - {reason}")
            raise PolicyViolationError(
                plugin_name=self.plugin_name,
                capability=capability,
                reason=reason,
                matched_rules=["scope_enforcement"],
                risk_tier="blocked",
            )

    def check_policy(
        self,
        capability: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Check if capability execution is allowed by policy.

        This is a HARD gate - if policy denies the action, it cannot proceed.
        This check happens BEFORE any execution attempt.

        Args:
            capability: The capability name being executed
            params: Parameters for the capability
            context: Additional context (caller info, session, etc.)

        Raises:
            PolicyViolationError: If policy denies the action
        """
        try:
            from ..policy import get_policy_engine
        except ImportError:
            # Policy module not available - allow by default (development mode)
            logger.warning("Policy engine not available - skipping policy check")
            return

        engine = get_policy_engine()
        decision = engine.evaluate(capability, params, context)

        if not decision.allowed:
            logger.warning(f"Policy violation: {capability} - {decision.reason} (rules: {decision.matched_rules})")
            raise PolicyViolationError(
                plugin_name=self.plugin_name,
                capability=capability,
                reason=decision.reason,
                matched_rules=decision.matched_rules,
                risk_tier=decision.risk_tier.value,
            )

        # Log if audit is required
        if decision.requires_audit:
            logger.info(f"[AUDIT] Capability execution allowed: {capability} (reason: {decision.reason})")

    def validate_params(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate parameters against the capability schema.

        This validates parameters BEFORE execution to catch errors early.
        Returns validated/normalized parameters with defaults applied.

        Args:
            capability: The capability name
            params: Parameters to validate

        Returns:
            Validated parameters with defaults applied

        Raises:
            PluginValidationError: If validation fails
        """
        cap_spec = self.manifest.get_capability(capability)
        if not cap_spec:
            # No schema to validate against
            logger.debug(f"No schema found for {capability}, skipping validation")
            return params

        try:
            from .schema import validate_params as do_validate
        except ImportError:
            # Schema module not available
            logger.warning("Schema validation module not available")
            return params

        return do_validate(cap_spec, params, self.plugin_name)


class BuiltinExecutor(ExecutorBase):
    """Executor for built-in plugins with pre-created instances.

    This executor wraps an existing PluginBase instance that was created
    during plugin discovery. It's used for built-in plugins that don't
    need dynamic loading.
    """

    def __init__(
        self,
        instance: PluginBase,
        manifest: PluginManifest,
        config: dict[str, Any] | None = None,
    ):
        """Initialize with an existing plugin instance.

        Args:
            instance: Pre-created plugin instance
            manifest: Plugin manifest
            config: Plugin configuration
        """
        super().__init__(manifest, config)
        self._plugin = instance

    async def initialize(self) -> None:
        """Initialize the plugin."""
        if self._plugin:
            await self._plugin.initialize()
        logger.info(f"Initialized built-in plugin: {self.plugin_name}")

    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        identity: Any | None = None,
    ) -> PluginResult:
        """Execute a capability on the built-in plugin.

        Args:
            capability: Capability name
            params: Execution parameters
            identity: IdentityContext from authentication (for scope checking)

        Returns:
            PluginResult with execution outcome
        """
        # Check scope FIRST - before policy
        try:
            self.check_scope(capability, identity)
        except PolicyViolationError as e:
            return PluginResult.error_result(
                e.reason,
                code="SCOPE_VIOLATION",
                metadata={
                    "matched_rules": e.matched_rules,
                    "risk_tier": e.risk_tier,
                },
            )

        # Check policy - before any execution
        try:
            # Include identity in policy context for identity-aware rules
            context = {"identity": identity.to_dict() if identity else None} if identity else None
            self.check_policy(capability, params, context)
        except PolicyViolationError as e:
            return PluginResult.error_result(
                e.reason,
                code="POLICY_VIOLATION",
                metadata={
                    "matched_rules": e.matched_rules,
                    "risk_tier": e.risk_tier,
                },
            )

        # Validate parameters against schema
        try:
            from .exceptions import PluginValidationError

            params = self.validate_params(capability, params)
        except PluginValidationError as e:
            return PluginResult.error_result(
                str(e),
                code="VALIDATION_ERROR",
                metadata={"validation_errors": e.validation_errors},
            )

        if not self._plugin:
            return PluginResult.error_result(
                "Plugin not initialized",
                code="NOT_INITIALIZED",
            )

        start_time = time.time()
        timeout = self.get_timeout(capability)

        try:
            result = await asyncio.wait_for(
                self._plugin.execute(capability, params),
                timeout=timeout,
            )
            result.execution_time = time.time() - start_time
            return result

        except TimeoutError:
            return PluginResult.timeout_result(timeout)
        except Exception as e:
            logger.exception(f"Error executing {self.plugin_name}.{capability}")
            return PluginResult.error_result(
                str(e),
                code="EXECUTION_ERROR",
                execution_time=time.time() - start_time,
            )


class PythonExecutor(ExecutorBase):
    """Execute plugins via direct Python class instantiation.

    This executor imports a Python module and instantiates a class
    that extends PluginBase or has an execute() method.
    """

    def __init__(
        self,
        manifest: PluginManifest,
        spec: PythonExecutionSpec,
        config: dict[str, Any] | None = None,
        plugin_dir: Path | None = None,
    ):
        super().__init__(manifest, config)
        self.spec = spec
        self.plugin_dir = plugin_dir
        self._added_to_path = False

    async def initialize(self) -> None:
        """Import the module and instantiate the plugin class."""
        try:
            # Add plugin directory to sys.path if needed
            if self.plugin_dir and str(self.plugin_dir) not in sys.path:
                sys.path.insert(0, str(self.plugin_dir))
                self._added_to_path = True
                logger.debug(f"Added to sys.path: {self.plugin_dir}")

            # Import the module
            module = importlib.import_module(self.spec.module)

            # Get the class
            plugin_class = getattr(module, self.spec.class_name, None)
            if plugin_class is None:
                raise PluginLoadError(
                    self.plugin_name,
                    f"Class '{self.spec.class_name}' not found in module '{self.spec.module}'",
                )

            # Check if it's a PluginBase subclass or has execute method
            if issubclass(plugin_class, PluginBase):
                # Standard PluginBase subclass
                self._plugin = plugin_class(self.manifest, self.config)
                await self._plugin.initialize()
            elif hasattr(plugin_class, "execute"):
                # Flexible plugin with execute() method (duck typing)
                self._plugin = _FlexiblePluginWrapper(
                    plugin_class(self.config),
                    self.manifest,
                )
            else:
                raise PluginLoadError(
                    self.plugin_name,
                    f"Class '{self.spec.class_name}' must extend PluginBase or have execute() method",
                )

            logger.info(f"Loaded Python plugin: {self.plugin_name}")

        except ImportError as e:
            raise PluginLoadError(
                self.plugin_name,
                f"Failed to import module '{self.spec.module}': {e}",
                cause=e,
            )
        except Exception as e:
            if isinstance(e, PluginLoadError):
                raise
            raise PluginLoadError(
                self.plugin_name,
                f"Failed to initialize plugin: {e}",
                cause=e,
            )

    async def shutdown(self) -> None:
        """Cleanup resources."""
        await super().shutdown()
        # Remove plugin directory from sys.path
        if self._added_to_path and self.plugin_dir and str(self.plugin_dir) in sys.path:
            sys.path.remove(str(self.plugin_dir))
            self._added_to_path = False

    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        identity: Any | None = None,
    ) -> PluginResult:
        """Execute a capability via the Python plugin instance."""
        # Check scope FIRST - before policy
        self.check_scope(capability, identity)

        # Check policy - before any execution
        context = {"identity": identity.to_dict() if identity else None} if identity else None
        self.check_policy(capability, params, context)

        # Validate parameters against schema
        params = self.validate_params(capability, params)

        if not self._plugin:
            raise ExecutionError(
                self.plugin_name,
                capability,
                "Plugin not initialized",
            )

        timeout = self.get_timeout(capability)
        start_time = time.time()

        try:
            result = await asyncio.wait_for(
                self._plugin.execute(capability, params),
                timeout=timeout,
            )
            result.execution_time = time.time() - start_time
            return result

        except TimeoutError:
            raise PluginTimeoutError(self.plugin_name, capability, timeout)
        except Exception as e:
            raise ExecutionError(
                self.plugin_name,
                capability,
                str(e),
            )


class CLIExecutor(ExecutorBase):
    """Execute plugins via subprocess CLI commands.

    This executor runs CLI tools as subprocesses, similar to the
    existing ToolWrapper pattern in Mother.
    """

    def __init__(
        self,
        manifest: PluginManifest,
        spec: CLIExecutionSpec,
        config: dict[str, Any] | None = None,
    ):
        super().__init__(manifest, config)
        self.spec = spec
        self._binary_path: str | None = None

    async def initialize(self) -> None:
        """Verify the CLI binary exists and is executable."""
        binary = self.spec.binary

        # Check if it's an absolute path
        if os.path.isabs(binary):
            if os.path.isfile(binary) and os.access(binary, os.X_OK):
                self._binary_path = binary
            else:
                raise PluginLoadError(
                    self.plugin_name,
                    f"Binary not found or not executable: {binary}",
                )
        else:
            # Search in PATH
            found = shutil.which(binary)
            if found:
                self._binary_path = found
            else:
                # Try common locations
                common_paths = [
                    Path.home() / ".local" / "bin" / binary,
                    Path.home() / "projects" / binary / ".venv" / "bin" / binary,
                    Path(f"/usr/local/bin/{binary}"),
                ]
                for path in common_paths:
                    if path.exists() and os.access(path, os.X_OK):
                        self._binary_path = str(path)
                        break

        if not self._binary_path:
            raise PluginLoadError(
                self.plugin_name,
                f"Binary '{binary}' not found in PATH or common locations",
            )

        logger.info(f"Loaded CLI plugin: {self.plugin_name} ({self._binary_path})")

    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        identity: Any | None = None,
    ) -> PluginResult:
        """Execute a capability via CLI subprocess."""
        # Check scope FIRST - before policy
        try:
            self.check_scope(capability, identity)
        except PolicyViolationError as e:
            return PluginResult.error_result(
                e.reason,
                code="SCOPE_VIOLATION",
                metadata={
                    "matched_rules": e.matched_rules,
                    "risk_tier": e.risk_tier,
                },
            )

        # Check policy - before any execution
        try:
            context = {"identity": identity.to_dict() if identity else None} if identity else None
            self.check_policy(capability, params, context)
        except PolicyViolationError as e:
            return PluginResult.error_result(
                e.reason,
                code="POLICY_VIOLATION",
                metadata={
                    "matched_rules": e.matched_rules,
                    "risk_tier": e.risk_tier,
                },
            )

        # Validate parameters against schema
        try:
            from .exceptions import PluginValidationError

            params = self.validate_params(capability, params)
        except PluginValidationError as e:
            return PluginResult.error_result(
                str(e),
                code="VALIDATION_ERROR",
                metadata={"validation_errors": e.validation_errors},
            )

        if not self._binary_path:
            raise ExecutionError(
                self.plugin_name,
                capability,
                "Plugin not initialized",
            )

        # Get capability spec for parameter mapping
        cap_spec = self.manifest.get_capability(capability)
        if not cap_spec:
            raise ExecutionError(
                self.plugin_name,
                capability,
                f"Unknown capability: {capability}",
            )

        # Build command
        cmd = self._build_command(capability, cap_spec, params)

        # Build environment
        env = self._build_environment()

        # Get timeout
        timeout = self.get_timeout(capability)
        start_time = time.time()

        try:
            # Run subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.spec.cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return PluginResult.timeout_result(timeout)

            execution_time = time.time() - start_time
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if process.returncode == 0:
                # Try to parse output as structured data
                parsed_data = self._parse_output(stdout_str, capability)
                return PluginResult.success_result(
                    data=parsed_data,
                    raw_output=stdout_str,
                    execution_time=execution_time,
                    command=cmd,
                )
            else:
                return PluginResult.error_result(
                    message=stderr_str or f"Command failed with exit code {process.returncode}",
                    code=f"EXIT_{process.returncode}",
                    raw_output=stdout_str + stderr_str,
                    execution_time=execution_time,
                    command=cmd,
                )

        except Exception as e:
            raise ExecutionError(
                self.plugin_name,
                capability,
                str(e),
            )

    def _build_command(
        self,
        capability: str,
        cap_spec: CapabilitySpec,
        params: dict[str, Any],
    ) -> list[str]:
        """Build the CLI command from capability and parameters.

        Args:
            capability: Capability name (often used as subcommand)
            cap_spec: Capability specification
            params: Parameter values

        Returns:
            Command as list of strings
        """
        cmd = [self._binary_path]

        # Add capability as subcommand (convention)
        # Convert capability name: send_email -> send-email or send email
        subcommand = capability.replace("_", "-")
        cmd.append(subcommand)

        # Map parameters to CLI flags
        for param_spec in cap_spec.parameters:
            value = params.get(param_spec.name)
            if value is None:
                continue

            if param_spec.positional:
                # Positional argument
                if isinstance(value, list):
                    cmd.extend(str(v) for v in value)
                else:
                    cmd.append(str(value))
            elif param_spec.flag:
                # Named flag
                if param_spec.type.value == "boolean":
                    if value:
                        cmd.append(param_spec.flag)
                elif isinstance(value, list):
                    for item in value:
                        cmd.extend([param_spec.flag, str(item)])
                else:
                    cmd.extend([param_spec.flag, str(value)])
            else:
                # Default: use --param-name format
                flag = f"--{param_spec.name.replace('_', '-')}"
                if param_spec.type.value == "boolean":
                    if value:
                        cmd.append(flag)
                elif isinstance(value, list):
                    for item in value:
                        cmd.extend([flag, str(item)])
                else:
                    cmd.extend([flag, str(value)])

        return cmd

    def _build_environment(self) -> dict[str, str]:
        """Build environment variables for the subprocess."""
        env = os.environ.copy()

        # Add configured environment variables
        for key, value in self.spec.env.items():
            # Handle variable substitution: ${secrets.api_key} or ${env.VAR}
            if value.startswith("${") and value.endswith("}"):
                var_ref = value[2:-1]
                if var_ref.startswith("secrets."):
                    # Look up in config
                    secret_key = var_ref.split(".", 1)[1].upper()
                    if secret_key in self.config:
                        env[key] = str(self.config[secret_key])
                elif var_ref.startswith("env."):
                    # Reference another env var
                    env_key = var_ref.split(".", 1)[1]
                    if env_key in os.environ:
                        env[key] = os.environ[env_key]
                elif var_ref in os.environ:
                    env[key] = os.environ[var_ref]
            else:
                env[key] = value

        # Add config values as environment variables
        for key, val in self.config.items():
            env_key = f"MOTHER_PLUGIN_{key.upper()}"
            env[env_key] = str(val)

        return env

    def _parse_output(self, output: str, capability: str) -> dict[str, Any] | None:
        """Try to parse CLI output as structured data.

        Args:
            output: Raw stdout from command
            capability: Capability name (for format hints)

        Returns:
            Parsed data dict, or None if not parseable
        """
        import json

        output = output.strip()

        # Try JSON first
        if output.startswith("{") or output.startswith("["):
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                pass

        # Return as raw text wrapped in dict
        return {"output": output} if output else None


def create_executor(
    manifest: PluginManifest,
    config: dict[str, Any] | None = None,
    plugin_dir: Path | None = None,
) -> ExecutorBase:
    """Factory function to create the appropriate executor for a plugin.

    Args:
        manifest: Plugin manifest with execution specification
        config: Plugin configuration values
        plugin_dir: Directory containing the plugin (for local module loading)

    Returns:
        Appropriate executor instance

    Raises:
        PluginLoadError: If execution type is not supported
    """
    from .manifest import ExecutionType

    exec_spec = manifest.execution

    if exec_spec.type == ExecutionType.PYTHON:
        if not exec_spec.python:
            raise PluginLoadError(manifest.plugin.name, "Missing Python execution config")
        return PythonExecutor(manifest, exec_spec.python, config, plugin_dir)

    elif exec_spec.type == ExecutionType.CLI:
        if not exec_spec.cli:
            raise PluginLoadError(manifest.plugin.name, "Missing CLI execution config")
        return CLIExecutor(manifest, exec_spec.cli, config)

    elif exec_spec.type == ExecutionType.DOCKER:
        raise PluginLoadError(
            manifest.plugin.name,
            "Docker execution not yet implemented (planned for v2)",
        )

    elif exec_spec.type == ExecutionType.HTTP:
        raise PluginLoadError(
            manifest.plugin.name,
            "HTTP execution not yet implemented (planned for v2)",
        )

    else:
        raise PluginLoadError(
            manifest.plugin.name,
            f"Unknown execution type: {exec_spec.type}",
        )
