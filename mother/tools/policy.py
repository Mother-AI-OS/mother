"""Tool installation policy enforcement.

This module provides policy checks for tool installation operations,
allowing enterprises to configure approval requirements based on risk level.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ToolPolicyViolationError
from .tool_manifest import RiskLevel

logger = logging.getLogger("mother.tools.policy")


class ToolPolicyAction(str, Enum):
    """Actions that can be taken by tool policy."""

    ALLOW = "allow"  # Allow without confirmation
    CONFIRM = "confirm"  # Require user confirmation
    DENY = "deny"  # Block the operation


@dataclass
class ToolPolicyConfig:
    """Configuration for tool installation policy.

    Attributes:
        enabled: Whether policy enforcement is enabled
        default_action: Action for tools without explicit rules
        risk_rules: Rules based on risk level
        blocked_tools: List of tool names that are always blocked
        allowed_tools: List of tool names that are always allowed
        require_confirmation_for_risk: Risk levels that require confirmation
        deny_risk_levels: Risk levels that are always denied
    """

    enabled: bool = True
    default_action: ToolPolicyAction = ToolPolicyAction.CONFIRM
    risk_rules: dict[str, ToolPolicyAction] = field(default_factory=lambda: {
        "low": ToolPolicyAction.ALLOW,
        "medium": ToolPolicyAction.CONFIRM,
        "high": ToolPolicyAction.CONFIRM,
        "critical": ToolPolicyAction.DENY,
    })
    blocked_tools: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolPolicyConfig:
        """Create config from dictionary."""
        risk_rules = {}
        if "risk_rules" in data:
            for level, action in data["risk_rules"].items():
                risk_rules[level] = ToolPolicyAction(action)

        return cls(
            enabled=data.get("enabled", True),
            default_action=ToolPolicyAction(data.get("default_action", "confirm")),
            risk_rules=risk_rules or cls().risk_rules,
            blocked_tools=data.get("blocked_tools", []),
            allowed_tools=data.get("allowed_tools", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "default_action": self.default_action.value,
            "risk_rules": {k: v.value for k, v in self.risk_rules.items()},
            "blocked_tools": self.blocked_tools,
            "allowed_tools": self.allowed_tools,
        }


@dataclass
class ToolPolicyDecision:
    """Result of a tool policy evaluation."""

    allowed: bool
    action: ToolPolicyAction
    reason: str
    requires_confirmation: bool = False
    tool_name: str | None = None
    risk_level: str | None = None

    @classmethod
    def allow(cls, reason: str, **kwargs: Any) -> ToolPolicyDecision:
        """Create an allow decision."""
        return cls(allowed=True, action=ToolPolicyAction.ALLOW, reason=reason, **kwargs)

    @classmethod
    def deny(cls, reason: str, **kwargs: Any) -> ToolPolicyDecision:
        """Create a deny decision."""
        return cls(allowed=False, action=ToolPolicyAction.DENY, reason=reason, **kwargs)

    @classmethod
    def require_confirmation(cls, reason: str, **kwargs: Any) -> ToolPolicyDecision:
        """Create a confirmation-required decision."""
        return cls(
            allowed=True,
            action=ToolPolicyAction.CONFIRM,
            reason=reason,
            requires_confirmation=True,
            **kwargs,
        )


class ToolPolicyEngine:
    """Enforces policy rules for tool installation.

    This engine evaluates tool installation requests against configured
    policy and returns decisions about whether to allow, deny, or
    require confirmation.
    """

    def __init__(self, config: ToolPolicyConfig | None = None):
        """Initialize the policy engine.

        Args:
            config: Policy configuration. Uses defaults if not provided.
        """
        self.config = config or ToolPolicyConfig()

    def evaluate_install(
        self,
        tool_name: str,
        risk_level: str | RiskLevel,
        source: str | None = None,
    ) -> ToolPolicyDecision:
        """Evaluate a tool installation request.

        Args:
            tool_name: Name of the tool
            risk_level: Risk level (low, medium, high, critical)
            source: Installation source (for logging)

        Returns:
            ToolPolicyDecision with the evaluation result
        """
        if not self.config.enabled:
            return ToolPolicyDecision.allow(
                reason="Policy enforcement disabled",
                tool_name=tool_name,
                risk_level=str(risk_level),
            )

        # Convert RiskLevel enum to string if needed
        if isinstance(risk_level, RiskLevel):
            risk_level = risk_level.value

        # Check blocked list
        if tool_name in self.config.blocked_tools:
            return ToolPolicyDecision.deny(
                reason=f"Tool '{tool_name}' is blocked by policy",
                tool_name=tool_name,
                risk_level=risk_level,
            )

        # Check allowed list (overrides risk checks)
        if tool_name in self.config.allowed_tools:
            return ToolPolicyDecision.allow(
                reason=f"Tool '{tool_name}' is explicitly allowed by policy",
                tool_name=tool_name,
                risk_level=risk_level,
            )

        # Check risk-based rules
        action = self.config.risk_rules.get(risk_level, self.config.default_action)

        if action == ToolPolicyAction.DENY:
            return ToolPolicyDecision.deny(
                reason=f"Tool with risk level '{risk_level}' is denied by policy",
                tool_name=tool_name,
                risk_level=risk_level,
            )
        elif action == ToolPolicyAction.CONFIRM:
            return ToolPolicyDecision.require_confirmation(
                reason=f"Tool with risk level '{risk_level}' requires confirmation",
                tool_name=tool_name,
                risk_level=risk_level,
            )
        else:
            return ToolPolicyDecision.allow(
                reason=f"Tool with risk level '{risk_level}' is allowed",
                tool_name=tool_name,
                risk_level=risk_level,
            )

    def check_install(
        self,
        tool_name: str,
        risk_level: str | RiskLevel,
        confirmed: bool = False,
    ) -> None:
        """Check if installation is allowed, raising if denied.

        This is a convenience method that raises ToolPolicyViolationError
        if the installation is not allowed.

        Args:
            tool_name: Name of the tool
            risk_level: Risk level
            confirmed: Whether user has confirmed (bypasses CONFIRM action)

        Raises:
            ToolPolicyViolationError: If installation is denied
        """
        decision = self.evaluate_install(tool_name, risk_level)

        if not decision.allowed:
            raise ToolPolicyViolationError(
                tool_name, "install", decision.reason, risk_level=str(decision.risk_level)
            )

        if decision.requires_confirmation and not confirmed:
            raise ToolPolicyViolationError(
                tool_name,
                "install",
                f"{decision.reason}. Use --yes to confirm.",
                risk_level=str(decision.risk_level),
            )


def load_tool_policy(path: Path | str | None = None) -> ToolPolicyConfig:
    """Load tool policy configuration from file.

    Args:
        path: Path to policy file. If None, searches default locations.

    Returns:
        ToolPolicyConfig
    """
    search_paths = []

    if path:
        search_paths.append(Path(path))
    else:
        # Default search locations
        search_paths.extend([
            Path("./mother_tool_policy.yaml"),
            Path("./config/mother_tool_policy.yaml"),
            Path.home() / ".config" / "mother" / "tool_policy.yaml",
        ])

    for check_path in search_paths:
        if check_path.exists():
            try:
                with open(check_path) as f:
                    data = yaml.safe_load(f)
                logger.info(f"Loaded tool policy from: {check_path}")
                return ToolPolicyConfig.from_dict(data or {})
            except Exception as e:
                logger.warning(f"Failed to load tool policy from {check_path}: {e}")

    # Return default config
    return ToolPolicyConfig()


# Global policy engine instance
_tool_policy_engine: ToolPolicyEngine | None = None


def get_tool_policy_engine() -> ToolPolicyEngine:
    """Get the global tool policy engine instance.

    Returns:
        ToolPolicyEngine instance
    """
    global _tool_policy_engine
    if _tool_policy_engine is None:
        config = load_tool_policy()
        _tool_policy_engine = ToolPolicyEngine(config)
    return _tool_policy_engine


def reload_tool_policy(config: ToolPolicyConfig | None = None) -> ToolPolicyEngine:
    """Reload the global tool policy engine.

    Args:
        config: New configuration, or None to reload from file

    Returns:
        New ToolPolicyEngine instance
    """
    global _tool_policy_engine
    if config is None:
        config = load_tool_policy()
    _tool_policy_engine = ToolPolicyEngine(config)
    return _tool_policy_engine


__all__ = [
    "ToolPolicyAction",
    "ToolPolicyConfig",
    "ToolPolicyDecision",
    "ToolPolicyEngine",
    "get_tool_policy_engine",
    "load_tool_policy",
    "reload_tool_policy",
]
