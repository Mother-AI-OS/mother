"""Policy loader for Mother AI OS.

Loads policy configuration from YAML files and environment variables.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .models import PolicyConfig

logger = logging.getLogger("mother.policy")

# Default policy file locations (in order of precedence)
DEFAULT_POLICY_PATHS = [
    "./mother_policy.yaml",
    "./config/mother_policy.yaml",
    "~/.config/mother/policy.yaml",
    "/etc/mother/policy.yaml",
]


class PolicyLoadError(Exception):
    """Error loading policy configuration."""

    pass


def load_policy_from_file(path: str | Path) -> PolicyConfig:
    """Load policy configuration from a YAML file.

    Args:
        path: Path to the policy YAML file

    Returns:
        PolicyConfig instance

    Raises:
        PolicyLoadError: If the file cannot be loaded or parsed
    """
    path = Path(path).expanduser().resolve()

    if not path.exists():
        raise PolicyLoadError(f"Policy file not found: {path}")

    if not path.is_file():
        raise PolicyLoadError(f"Policy path is not a file: {path}")

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise PolicyLoadError(f"Invalid YAML in policy file: {e}")
    except IOError as e:
        raise PolicyLoadError(f"Cannot read policy file: {e}")

    if not isinstance(data, dict):
        raise PolicyLoadError("Policy file must contain a YAML mapping")

    try:
        config = PolicyConfig.model_validate(data)
        logger.info(f"Loaded policy from {path}: {config.name} v{config.version}")
        return config
    except Exception as e:
        raise PolicyLoadError(f"Invalid policy configuration: {e}")


def load_policy_from_env() -> PolicyConfig | None:
    """Load policy from environment variable path.

    Checks MOTHER_POLICY_PATH environment variable.

    Returns:
        PolicyConfig if found, None otherwise
    """
    policy_path = os.environ.get("MOTHER_POLICY_PATH")

    if not policy_path:
        return None

    try:
        return load_policy_from_file(policy_path)
    except PolicyLoadError as e:
        logger.warning(f"Failed to load policy from MOTHER_POLICY_PATH: {e}")
        return None


def apply_env_overrides(config: PolicyConfig) -> PolicyConfig:
    """Apply environment variable overrides to policy config.

    Environment variables take precedence over policy file settings.
    This ensures operators can enforce security at runtime.

    Supported overrides:
    - MOTHER_SAFE_MODE: Override safe_mode setting (0/false = disabled, 1/true = enabled)

    Args:
        config: Base policy configuration

    Returns:
        PolicyConfig with environment overrides applied
    """
    # Check MOTHER_SAFE_MODE environment variable
    safe_mode_env = os.environ.get("MOTHER_SAFE_MODE")
    if safe_mode_env is not None:
        # Parse boolean value
        safe_mode = safe_mode_env.lower() not in ("0", "false", "no", "off", "")
        if safe_mode != config.safe_mode:
            logger.info(f"MOTHER_SAFE_MODE override: {config.safe_mode} -> {safe_mode}")
            # Create new config with overridden safe_mode
            config = PolicyConfig(
                **{**config.model_dump(), "safe_mode": safe_mode}
            )

    return config


def load_policy() -> PolicyConfig:
    """Load policy configuration from default locations.

    Precedence:
    1. MOTHER_POLICY_PATH environment variable
    2. ./mother_policy.yaml
    3. ./config/mother_policy.yaml
    4. ~/.config/mother/policy.yaml
    5. /etc/mother/policy.yaml
    6. Default policy (built-in)

    After loading, MOTHER_SAFE_MODE environment variable can override
    the policy file's safe_mode setting.

    Returns:
        PolicyConfig instance (never fails, returns default if no file found)
    """
    config: PolicyConfig | None = None

    # Try environment variable first
    config = load_policy_from_env()

    # Try default paths if no env config
    if config is None:
        for path_str in DEFAULT_POLICY_PATHS:
            try:
                path = Path(path_str).expanduser()
                if path.exists():
                    config = load_policy_from_file(path)
                    break
            except PolicyLoadError as e:
                logger.debug(f"Skipping policy path {path_str}: {e}")
                continue

    # Fall back to default policy
    if config is None:
        logger.info("No policy file found, using default policy")
        config = get_default_policy()

    # Apply environment variable overrides
    config = apply_env_overrides(config)

    return config


def get_default_policy() -> PolicyConfig:
    """Get the default policy configuration.

    The default policy is "safe by default":
    - Shell commands are blocked (high-risk capability in safe mode)
    - Filesystem writes limited to workspace directory
    - Network egress blocked (no external connections)
    - High-risk capabilities disabled unless explicitly allowed

    Returns:
        Default PolicyConfig
    """
    from .models import (
        CommandCondition,
        DataCondition,
        FilesystemCondition,
        NetworkCondition,
        PolicyAction,
    )

    # Get workspace directory from environment or use default
    workspace_dir = os.environ.get("MOTHER_WORKSPACE_DIR", "./workspace")

    return PolicyConfig(
        version="1.0",
        name="default-safe",
        description="Default safe mode policy - restrictive by default",
        safe_mode=True,
        default_action=PolicyAction.DENY,
        # Filesystem: Only allow read anywhere, write only in workspace
        filesystem=FilesystemCondition(
            allowed_paths=[
                f"{workspace_dir}/**/*",  # Workspace is always allowed
                "./**/*",  # Current directory for reads
            ],
            denied_paths=[
                "/etc/shadow",
                "/etc/passwd",
                "/etc/sudoers",
                "**/.ssh/id_*",
                "**/.ssh/authorized_keys",
                "**/.env",
                "**/*.pem",
                "**/*.key",
                "**/credentials*",
                "**/secrets*",
            ],
            write_restricted=True,
            write_allowed_paths=[
                f"{workspace_dir}/**/*",
            ],
        ),
        # Commands: Block all shell execution in safe mode
        commands=CommandCondition(
            allowed_commands=[],  # No commands allowed by default
            denied_commands=[
                ".*",  # Block all by default
            ],
            denied_patterns=[
                "rm -rf /",
                "> /dev/sda",
                ":(){ :|:& };:",
            ],
        ),
        # Network: Block all egress by default
        network=NetworkCondition(
            allowed_domains=[],  # No domains allowed
            denied_domains=["*"],  # Block all
            block_private_ranges=True,
        ),
        # Data: Prevent exfiltration of sensitive data
        data=DataCondition(
            sensitive_patterns=[
                r"-----BEGIN.*PRIVATE KEY-----",
                r"password\s*[=:]\s*\S+",
                r"api[_-]?key\s*[=:]\s*\S+",
                r"secret\s*[=:]\s*\S+",
                r"token\s*[=:]\s*\S+",
                r"\b[A-Za-z0-9+/]{40,}\b",  # Base64 encoded secrets
            ],
            block_pii=True,
        ),
    )


def get_permissive_policy() -> PolicyConfig:
    """Get a permissive policy for development/testing.

    WARNING: This policy allows most operations and should only be used
    in trusted development environments.

    Returns:
        Permissive PolicyConfig
    """
    from .models import (
        CommandCondition,
        FilesystemCondition,
        NetworkCondition,
        PolicyAction,
        PolicyRule,
    )

    return PolicyConfig(
        version="1.0",
        name="development",
        description="Permissive policy for development - use with caution",
        safe_mode=False,
        default_action=PolicyAction.ALLOW,
        rules=[
            PolicyRule(
                name="allow-all",
                description="Allow all capabilities (development mode)",
                capability_pattern=".*",
                action=PolicyAction.ALLOW,
                priority=0,
            ),
        ],
        filesystem=FilesystemCondition(
            allowed_paths=["**/*"],
            denied_paths=[
                "/etc/shadow",
                "/etc/passwd",
                "**/.ssh/id_*",
            ],
        ),
        commands=CommandCondition(
            allowed_commands=[".*"],  # Allow all
        ),
        network=NetworkCondition(
            allowed_domains=["*"],  # Allow all
            block_private_ranges=False,
        ),
    )


def merge_policies(base: PolicyConfig, override: PolicyConfig) -> PolicyConfig:
    """Merge two policy configurations.

    The override policy takes precedence for rules and conditions.

    Args:
        base: Base policy configuration
        override: Override policy configuration

    Returns:
        Merged PolicyConfig
    """
    # Start with base, then apply overrides
    merged_data: dict[str, Any] = base.model_dump()

    override_data = override.model_dump()

    # Merge rules (override rules take precedence by name)
    base_rules = {r["name"]: r for r in merged_data.get("rules", [])}
    for rule in override_data.get("rules", []):
        base_rules[rule["name"]] = rule
    merged_data["rules"] = list(base_rules.values())

    # Override simple fields
    for field in ["name", "description", "version", "safe_mode", "default_action"]:
        if field in override_data and override_data[field] is not None:
            merged_data[field] = override_data[field]

    # Merge condition objects (override fields take precedence)
    for condition_type in ["filesystem", "commands", "network", "data"]:
        if condition_type in override_data:
            base_condition = merged_data.get(condition_type, {})
            override_condition = override_data[condition_type]
            # Only override non-default values
            for key, value in override_condition.items():
                if value is not None:
                    base_condition[key] = value
            merged_data[condition_type] = base_condition

    return PolicyConfig.model_validate(merged_data)


def save_policy_to_file(config: PolicyConfig, path: str | Path) -> None:
    """Save a policy configuration to a YAML file.

    Args:
        config: Policy configuration to save
        path: Path to save the file

    Raises:
        PolicyLoadError: If the file cannot be written
    """
    path = Path(path).expanduser().resolve()

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Use mode='json' to serialize enums as strings for YAML compatibility
        data = config.model_dump(exclude_none=True, mode="json")
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Saved policy to {path}")
    except IOError as e:
        raise PolicyLoadError(f"Cannot write policy file: {e}")


# Export functions
__all__ = [
    "PolicyLoadError",
    "load_policy_from_file",
    "load_policy_from_env",
    "load_policy",
    "apply_env_overrides",
    "get_default_policy",
    "get_permissive_policy",
    "merge_policies",
    "save_policy_to_file",
]
