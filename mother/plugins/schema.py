"""Schema validation for Mother AI OS plugin system.

This module provides JSON Schema validation for capability parameters
before execution, ensuring type safety and catching errors early.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .exceptions import PluginValidationError
from .manifest import CapabilitySpec, ParameterSpec, ParameterType

logger = logging.getLogger("mother.plugins.schema")


class SchemaValidator:
    """Validates capability parameters against their schemas.

    Provides comprehensive validation including:
    - Type checking
    - Required parameter validation
    - Choice/enum validation
    - Array item type validation
    - Default value application
    """

    def __init__(self, strict: bool = True):
        """Initialize the validator.

        Args:
            strict: If True, raise errors on unknown parameters
        """
        self.strict = strict

    def validate(
        self,
        capability: CapabilitySpec,
        params: dict[str, Any],
        plugin_name: str = "unknown",
    ) -> dict[str, Any]:
        """Validate parameters against a capability schema.

        Args:
            capability: The capability specification
            params: Parameters to validate
            plugin_name: Plugin name for error messages

        Returns:
            Validated and normalized parameters with defaults applied

        Raises:
            PluginValidationError: If validation fails
        """
        errors: list[str] = []
        validated: dict[str, Any] = {}

        # Build parameter map
        param_specs = {p.name: p for p in capability.parameters}

        # Check for unknown parameters
        if self.strict:
            for param_name in params:
                if param_name not in param_specs:
                    errors.append(f"Unknown parameter: '{param_name}'")

        # Validate each defined parameter
        for param_name, spec in param_specs.items():
            value = params.get(param_name)

            # Check required
            if spec.required and value is None:
                errors.append(f"Missing required parameter: '{param_name}'")
                continue

            # Apply default if not provided
            if value is None:
                if spec.default is not None:
                    validated[param_name] = spec.default
                continue

            # Validate type
            type_error = self._validate_type(param_name, value, spec)
            if type_error:
                errors.append(type_error)
                continue

            # Validate choices
            if spec.choices and value not in spec.choices:
                errors.append(
                    f"Parameter '{param_name}' must be one of: {spec.choices}, got: {value}"
                )
                continue

            validated[param_name] = value

        if errors:
            # Convert error strings to dicts for PluginValidationError
            validation_errors = [{"message": e} for e in errors]
            raise PluginValidationError(
                plugin_name=plugin_name,
                capability=capability.name,
                validation_errors=validation_errors,
            )

        return validated

    def _validate_type(
        self, param_name: str, value: Any, spec: ParameterSpec
    ) -> str | None:
        """Validate a parameter's type.

        Returns:
            Error message if validation fails, None otherwise
        """
        expected_type = spec.type

        if expected_type == ParameterType.STRING:
            if not isinstance(value, str):
                return f"Parameter '{param_name}' must be string, got: {type(value).__name__}"

        elif expected_type == ParameterType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                return f"Parameter '{param_name}' must be integer, got: {type(value).__name__}"

        elif expected_type == ParameterType.NUMBER:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return f"Parameter '{param_name}' must be number, got: {type(value).__name__}"

        elif expected_type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return f"Parameter '{param_name}' must be boolean, got: {type(value).__name__}"

        elif expected_type == ParameterType.ARRAY:
            if not isinstance(value, list):
                return f"Parameter '{param_name}' must be array, got: {type(value).__name__}"

            # Validate array items
            if spec.items_type:
                for i, item in enumerate(value):
                    item_error = self._validate_array_item(
                        param_name, i, item, spec.items_type
                    )
                    if item_error:
                        return item_error

        elif expected_type == ParameterType.OBJECT:
            if not isinstance(value, dict):
                return f"Parameter '{param_name}' must be object, got: {type(value).__name__}"

        return None

    def _validate_array_item(
        self, param_name: str, index: int, item: Any, item_type: ParameterType
    ) -> str | None:
        """Validate an array item's type."""
        type_map = {
            ParameterType.STRING: str,
            ParameterType.INTEGER: int,
            ParameterType.NUMBER: (int, float),
            ParameterType.BOOLEAN: bool,
            ParameterType.OBJECT: dict,
            ParameterType.ARRAY: list,
        }

        expected = type_map.get(item_type)
        if expected is None:
            return None

        if item_type == ParameterType.INTEGER and isinstance(item, bool):
            return f"Parameter '{param_name}[{index}]' must be integer, got: bool"

        if item_type == ParameterType.NUMBER and isinstance(item, bool):
            return f"Parameter '{param_name}[{index}]' must be number, got: bool"

        if not isinstance(item, expected):
            return (
                f"Parameter '{param_name}[{index}]' must be {item_type.value}, "
                f"got: {type(item).__name__}"
            )

        return None


def parse_semver(version: str) -> tuple[int, int, int, str | None, str | None]:
    """Parse a semantic version string.

    Args:
        version: Version string (e.g., "1.2.3", "1.0.0-beta.1+build.123")

    Returns:
        Tuple of (major, minor, patch, prerelease, build_metadata)

    Raises:
        ValueError: If version string is invalid
    """
    pattern = r"^(\d+)\.(\d+)\.(\d+)(-([a-zA-Z0-9.]+))?(\+([a-zA-Z0-9.]+))?$"
    match = re.match(pattern, version)

    if not match:
        raise ValueError(f"Invalid semver: {version}")

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease = match.group(5)  # Group 5 is the content after -
    build_metadata = match.group(7)  # Group 7 is the content after +

    return (major, minor, patch, prerelease, build_metadata)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semantic versions.

    Args:
        v1: First version
        v2: Second version

    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    p1 = parse_semver(v1)
    p2 = parse_semver(v2)

    # Compare major, minor, patch
    for i in range(3):
        if p1[i] < p2[i]:
            return -1
        if p1[i] > p2[i]:
            return 1

    # If one has prerelease and other doesn't, non-prerelease is higher
    # e.g., 1.0.0 > 1.0.0-alpha
    if p1[3] is None and p2[3] is not None:
        return 1
    if p1[3] is not None and p2[3] is None:
        return -1

    # Both have prerelease or both don't
    if p1[3] and p2[3]:
        if p1[3] < p2[3]:
            return -1
        if p1[3] > p2[3]:
            return 1

    return 0


def is_version_compatible(required: str, actual: str) -> bool:
    """Check if actual version satisfies required version constraint.

    Supports constraints:
    - Exact: "1.0.0" (must match exactly)
    - Range: ">=1.0.0" (must be >= 1.0.0)
    - Range: ">=1.0.0,<2.0.0" (must be >= 1.0.0 and < 2.0.0)
    - Caret: "^1.0.0" (compatible with 1.x.x, >= 1.0.0 and < 2.0.0)
    - Tilde: "~1.0.0" (compatible with 1.0.x, >= 1.0.0 and < 1.1.0)

    Args:
        required: Version constraint string
        actual: Actual version to check

    Returns:
        True if actual version satisfies the constraint
    """
    required = required.strip()

    # Handle comma-separated constraints
    if "," in required:
        constraints = [c.strip() for c in required.split(",")]
        return all(is_version_compatible(c, actual) for c in constraints)

    # Caret range (^1.0.0 means >=1.0.0 and <2.0.0)
    if required.startswith("^"):
        base = required[1:]
        major, minor, patch, _, _ = parse_semver(base)
        actual_parts = parse_semver(actual)

        # Must be same major version and >= base
        if actual_parts[0] != major:
            return False
        return compare_versions(actual, base) >= 0

    # Tilde range (~1.0.0 means >=1.0.0 and <1.1.0)
    if required.startswith("~"):
        base = required[1:]
        major, minor, patch, _, _ = parse_semver(base)
        actual_parts = parse_semver(actual)

        # Must be same major.minor and >= base
        if actual_parts[0] != major or actual_parts[1] != minor:
            return False
        return compare_versions(actual, base) >= 0

    # Greater than or equal
    if required.startswith(">="):
        base = required[2:]
        return compare_versions(actual, base) >= 0

    # Greater than
    if required.startswith(">"):
        base = required[1:]
        return compare_versions(actual, base) > 0

    # Less than or equal
    if required.startswith("<="):
        base = required[2:]
        return compare_versions(actual, base) <= 0

    # Less than
    if required.startswith("<"):
        base = required[1:]
        return compare_versions(actual, base) < 0

    # Exact match
    return compare_versions(actual, required) == 0


class VersionTracker:
    """Tracks schema versions and detects breaking changes.

    Breaking changes include:
    - Removing a required parameter
    - Changing a parameter's type
    - Removing a capability
    - Making an optional parameter required
    """

    def __init__(self):
        self._schema_history: dict[str, list[dict]] = {}

    def register_schema(
        self, plugin_name: str, version: str, capabilities: list[CapabilitySpec]
    ) -> None:
        """Register a schema version.

        Args:
            plugin_name: Plugin identifier
            version: Semantic version
            capabilities: List of capability specifications
        """
        key = plugin_name

        if key not in self._schema_history:
            self._schema_history[key] = []

        # Store schema snapshot
        schema_snapshot = {
            "version": version,
            "capabilities": {
                cap.name: {
                    "parameters": {
                        p.name: {
                            "type": p.type.value,
                            "required": p.required,
                            "choices": p.choices,
                        }
                        for p in cap.parameters
                    }
                }
                for cap in capabilities
            },
        }

        self._schema_history[key].append(schema_snapshot)
        logger.debug(f"Registered schema for {plugin_name} v{version}")

    def detect_breaking_changes(
        self, plugin_name: str, old_version: str, new_version: str
    ) -> list[str]:
        """Detect breaking changes between two schema versions.

        Args:
            plugin_name: Plugin identifier
            old_version: Previous version
            new_version: New version

        Returns:
            List of breaking change descriptions
        """
        history = self._schema_history.get(plugin_name, [])

        old_schema = None
        new_schema = None

        for entry in history:
            if entry["version"] == old_version:
                old_schema = entry
            if entry["version"] == new_version:
                new_schema = entry

        if not old_schema or not new_schema:
            return []

        breaking_changes: list[str] = []

        old_caps = old_schema["capabilities"]
        new_caps = new_schema["capabilities"]

        # Check for removed capabilities
        for cap_name in old_caps:
            if cap_name not in new_caps:
                breaking_changes.append(f"Removed capability: {cap_name}")
                continue

            old_params = old_caps[cap_name]["parameters"]
            new_params = new_caps[cap_name]["parameters"]

            # Check for removed required parameters
            for param_name, param_info in old_params.items():
                if param_name not in new_params:
                    if param_info["required"]:
                        breaking_changes.append(
                            f"{cap_name}: Removed required parameter '{param_name}'"
                        )
                    continue

                new_param = new_params[param_name]

                # Check for type changes
                if param_info["type"] != new_param["type"]:
                    breaking_changes.append(
                        f"{cap_name}: Changed type of '{param_name}' "
                        f"from {param_info['type']} to {new_param['type']}"
                    )

                # Check for optional becoming required
                if not param_info["required"] and new_param["required"]:
                    breaking_changes.append(
                        f"{cap_name}: Made optional parameter '{param_name}' required"
                    )

                # Check for removed choices
                if param_info["choices"] and new_param["choices"]:
                    removed = set(param_info["choices"]) - set(new_param["choices"])
                    if removed:
                        breaking_changes.append(
                            f"{cap_name}: Removed choices for '{param_name}': {removed}"
                        )

        return breaking_changes


# Global instances
_validator: SchemaValidator | None = None
_version_tracker: VersionTracker | None = None


def get_validator() -> SchemaValidator:
    """Get the global schema validator instance."""
    global _validator
    if _validator is None:
        _validator = SchemaValidator()
    return _validator


def get_version_tracker() -> VersionTracker:
    """Get the global version tracker instance."""
    global _version_tracker
    if _version_tracker is None:
        _version_tracker = VersionTracker()
    return _version_tracker


def validate_params(
    capability: CapabilitySpec,
    params: dict[str, Any],
    plugin_name: str = "unknown",
) -> dict[str, Any]:
    """Validate parameters against a capability schema.

    Convenience function using the global validator.

    Args:
        capability: The capability specification
        params: Parameters to validate
        plugin_name: Plugin name for error messages

    Returns:
        Validated and normalized parameters

    Raises:
        PluginValidationError: If validation fails
    """
    return get_validator().validate(capability, params, plugin_name)


# Exports
__all__ = [
    "SchemaValidator",
    "VersionTracker",
    "parse_semver",
    "compare_versions",
    "is_version_compatible",
    "get_validator",
    "get_version_tracker",
    "validate_params",
]
