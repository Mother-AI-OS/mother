"""Policy engine for Mother AI OS enterprise security.

The PolicyEngine is the central component that evaluates all capability
calls against the configured policy before execution. It provides a hard
gate that cannot be bypassed, unlike simple confirmation prompts.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .conditions import (
    evaluate_command_condition,
    evaluate_data_condition,
    evaluate_filesystem_condition,
    evaluate_network_condition,
)
from .loader import load_policy
from .models import (
    PolicyAction,
    PolicyConfig,
    PolicyDecision,
    PolicyRule,
    RiskTier,
)

logger = logging.getLogger("mother.policy")


class PolicyEngine:
    """Enforces policy rules before capability execution.

    The PolicyEngine evaluates all capability calls against the configured
    policy and returns a PolicyDecision indicating whether the action is
    allowed, denied, or requires additional steps (like confirmation or audit).

    This is a HARD GATE - if the policy denies an action, it cannot be
    executed regardless of user confirmation.

    Usage:
        engine = PolicyEngine()  # Loads default policy
        decision = engine.evaluate("shell_run_command", {"command": "ls -la"})
        if not decision.allowed:
            raise PolicyViolationError(decision.reason)
    """

    def __init__(self, config: PolicyConfig | None = None):
        """Initialize the policy engine.

        Args:
            config: Policy configuration. If None, loads from default locations.
        """
        self.config = config or load_policy()
        self._capability_rules_cache: dict[str, list[PolicyRule]] = {}
        logger.info(
            f"Policy engine initialized: {self.config.name} "
            f"(safe_mode={self.config.safe_mode}, {len(self.config.rules)} rules)"
        )

    def reload_policy(self, config: PolicyConfig | None = None) -> None:
        """Reload policy configuration.

        Args:
            config: New policy configuration. If None, reloads from file.
        """
        self.config = config or load_policy()
        self._capability_rules_cache.clear()
        logger.info(f"Policy reloaded: {self.config.name}")

    def evaluate(
        self,
        capability_name: str,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate a capability call against the policy.

        This is the main entry point for policy enforcement. It checks:
        1. Safe mode restrictions for high-risk capabilities
        2. Explicit rules that match the capability
        3. Condition-based evaluation (filesystem, commands, network)
        4. Default action if no rules match

        Args:
            capability_name: The capability being invoked (e.g., "shell_run_command")
            params: Parameters passed to the capability
            context: Additional context (caller info, session, etc.)

        Returns:
            PolicyDecision indicating whether the action is allowed
        """
        params = params or {}
        context = context or {}

        logger.debug(f"Evaluating policy for {capability_name}")

        # Check safe mode restrictions first
        if self.config.safe_mode:
            decision = self._check_safe_mode(capability_name, params)
            if not decision.allowed:
                return decision

        # Evaluate condition-based checks BEFORE rules
        # Conditions act as hard restrictions that can deny even if rules allow
        condition_decision = self._evaluate_conditions(capability_name, params)
        if condition_decision is not None and not condition_decision.allowed:
            return condition_decision

        # Get matching rules
        rules = self._get_rules_for_capability(capability_name)

        # Evaluate rules in priority order
        for rule in rules:
            decision = self._evaluate_rule(rule, capability_name, params, context)
            if decision is not None:
                return decision

        # Apply default action
        return self._apply_default_action(capability_name)

    def is_capability_enabled(self, capability_name: str) -> bool:
        """Check if a capability is enabled by policy.

        This is a quick check that doesn't evaluate params, useful for
        filtering capability lists.

        Args:
            capability_name: The capability name

        Returns:
            True if the capability might be allowed (subject to params)
        """
        if self.config.safe_mode:
            # In safe mode, high-risk capabilities are disabled
            if self._is_high_risk_capability(capability_name):
                return False

        # Check for explicit deny rules
        rules = self._get_rules_for_capability(capability_name)
        for rule in rules:
            if rule.action == PolicyAction.DENY:
                return False

        return True

    def get_allowed_capabilities(self, all_capabilities: list[str]) -> list[str]:
        """Filter a list of capabilities to only those allowed by policy.

        Args:
            all_capabilities: List of all capability names

        Returns:
            List of capability names that are not explicitly denied
        """
        return [cap for cap in all_capabilities if self.is_capability_enabled(cap)]

    def explain_decision(self, decision: PolicyDecision) -> str:
        """Generate a human-readable explanation of a policy decision.

        Args:
            decision: The policy decision to explain

        Returns:
            Formatted explanation string
        """
        lines = []

        if decision.allowed:
            lines.append(f"ALLOWED: {decision.reason}")
        else:
            lines.append(f"DENIED: {decision.reason}")

        if decision.matched_rules:
            lines.append(f"Matched rules: {', '.join(decision.matched_rules)}")

        lines.append(f"Risk tier: {decision.risk_tier.value}")

        if decision.requires_audit:
            lines.append("Note: This action will be audit logged")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _get_rules_for_capability(self, capability_name: str) -> list[PolicyRule]:
        """Get rules matching a capability, with caching."""
        if capability_name not in self._capability_rules_cache:
            self._capability_rules_cache[capability_name] = self.config.get_rules_for_capability(capability_name)
        return self._capability_rules_cache[capability_name]

    def _check_safe_mode(
        self,
        capability_name: str,
        params: dict[str, Any],
    ) -> PolicyDecision:
        """Check safe mode restrictions.

        In safe mode, high-risk capabilities are blocked unless explicitly
        enabled by a policy rule.
        """
        if self._is_high_risk_capability(capability_name):
            # Check if there's an explicit allow rule
            rules = self._get_rules_for_capability(capability_name)
            has_allow_rule = any(r.action == PolicyAction.ALLOW for r in rules)

            if not has_allow_rule:
                return PolicyDecision.deny(
                    reason=f"Capability '{capability_name}' is blocked in safe mode. "
                    f"Add an explicit policy rule to enable it.",
                    matched_rules=["safe_mode"],
                    risk_tier=RiskTier.HIGH,
                )

        return PolicyDecision.allow(reason="Safe mode check passed")

    def _is_high_risk_capability(self, capability_name: str) -> bool:
        """Check if a capability is considered high-risk."""
        high_risk_patterns = [
            r"^shell_",  # Shell execution
            r"^tor_",  # Tor/darknet
            r"^tor-shell_",  # Tor shell
            r"_delete$",  # Delete operations
            r"_write$",  # Write operations (to unknown locations)
            r"_execute$",  # Generic execute
            r"_run_command$",
            r"_run_script$",
        ]

        for pattern in high_risk_patterns:
            if re.search(pattern, capability_name):
                return True

        return False

    def _evaluate_rule(
        self,
        rule: PolicyRule,
        capability_name: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> PolicyDecision | None:
        """Evaluate a single rule against the capability call.

        Returns None if the rule doesn't result in a decision (continue checking).
        """
        # Check additional conditions in the rule
        if rule.conditions:
            conditions_met = self._check_rule_conditions(rule.conditions, params, context)
            if not conditions_met:
                return None  # Conditions not met, skip this rule

        # Apply the rule's action
        if rule.action == PolicyAction.DENY:
            return PolicyDecision.deny(
                reason=rule.description or f"Blocked by rule: {rule.name}",
                matched_rules=[rule.name],
                risk_tier=RiskTier.HIGH if self._is_high_risk_capability(capability_name) else RiskTier.MEDIUM,
            )
        elif rule.action == PolicyAction.ALLOW:
            return PolicyDecision.allow(
                reason=rule.description or f"Allowed by rule: {rule.name}",
                matched_rules=[rule.name],
                risk_tier=RiskTier.LOW,
            )
        elif rule.action == PolicyAction.CONFIRM:
            return PolicyDecision.require_confirmation(
                reason=rule.description or f"Confirmation required by rule: {rule.name}",
                matched_rules=[rule.name],
            )
        elif rule.action == PolicyAction.AUDIT:
            return PolicyDecision(
                allowed=True,
                action=PolicyAction.AUDIT,
                reason=rule.description or f"Audit logging required by rule: {rule.name}",
                matched_rules=[rule.name],
                risk_tier=RiskTier.MEDIUM,
                requires_audit=True,
            )

        return None

    def _check_rule_conditions(
        self,
        conditions: dict[str, Any],
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        """Check if rule conditions are met."""
        for key, expected in conditions.items():
            if key.startswith("param."):
                # Check parameter value
                param_name = key[6:]  # Remove "param." prefix
                actual = params.get(param_name)

                if isinstance(expected, dict):
                    # Complex condition (regex, range, etc.)
                    if "regex" in expected:
                        if not actual or not re.match(expected["regex"], str(actual)):
                            return False
                    if "min" in expected:
                        if actual is None or actual < expected["min"]:
                            return False
                    if "max" in expected:
                        if actual is None or actual > expected["max"]:
                            return False
                    if "in" in expected:
                        if actual not in expected["in"]:
                            return False
                else:
                    # Simple equality check
                    if actual != expected:
                        return False

            elif key.startswith("context."):
                # Check context value
                context_key = key[8:]
                if context.get(context_key) != expected:
                    return False

        return True

    def _evaluate_conditions(
        self,
        capability_name: str,
        params: dict[str, Any],
    ) -> PolicyDecision | None:
        """Evaluate condition-based checks for specific capability types."""
        # Filesystem capabilities
        if capability_name.startswith("filesystem_") or "_file" in capability_name:
            path = params.get("path") or params.get("file_path") or params.get("source")
            if path:
                operation = self._infer_operation(capability_name)
                return evaluate_filesystem_condition(self.config.filesystem, path, operation)

        # Shell/command capabilities
        if capability_name.startswith("shell_") or capability_name.endswith("_command"):
            command = params.get("command") or params.get("script")
            cwd = params.get("cwd")
            if command:
                return evaluate_command_condition(self.config.commands, command, cwd)

        # Network capabilities
        if capability_name.startswith("web_") or capability_name.startswith("tor_") or "_fetch" in capability_name:
            url = params.get("url")
            if url:
                return evaluate_network_condition(self.config.network, url=url)

        # Email with attachments (potential data exfiltration)
        if "send" in capability_name or "email" in capability_name:
            body = params.get("body") or params.get("content") or ""
            attachments = params.get("attachments") or []
            if body or attachments:
                # Check body for sensitive data
                decision = evaluate_data_condition(
                    self.config.data,
                    body,
                    destination=params.get("to") or "external",
                )
                if not decision.allowed:
                    return decision

        return None

    def _infer_operation(self, capability_name: str) -> str:
        """Infer the filesystem operation type from capability name."""
        if "write" in capability_name or "create" in capability_name:
            return "write"
        elif "delete" in capability_name or "remove" in capability_name:
            return "delete"
        elif "list" in capability_name or "read" in capability_name:
            return "read"
        else:
            return "read"  # Default to read (least privilege)

    def _apply_default_action(self, capability_name: str) -> PolicyDecision:
        """Apply the default action when no rules match."""
        if self.config.default_action == PolicyAction.ALLOW:
            return PolicyDecision.allow(
                reason="No rules matched, default action is allow",
                risk_tier=RiskTier.LOW,
            )
        elif self.config.default_action == PolicyAction.DENY:
            return PolicyDecision.deny(
                reason="No rules matched, default action is deny",
                risk_tier=RiskTier.MEDIUM,
            )
        elif self.config.default_action == PolicyAction.CONFIRM:
            return PolicyDecision.require_confirmation(
                reason="No rules matched, default action is require confirmation",
            )
        else:
            # Default to deny for safety
            return PolicyDecision.deny(
                reason="Unknown default action, denying for safety",
                risk_tier=RiskTier.HIGH,
            )


class PolicyViolationError(Exception):
    """Raised when a capability call violates policy."""

    def __init__(self, decision: PolicyDecision):
        self.decision = decision
        super().__init__(decision.reason)


# Global policy engine instance (lazy loaded)
_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine instance.

    Creates the engine on first call, loading policy from default locations.

    Returns:
        PolicyEngine instance
    """
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine


def reload_policy_engine(config: PolicyConfig | None = None) -> PolicyEngine:
    """Reload the global policy engine.

    Args:
        config: New configuration, or None to reload from file

    Returns:
        New PolicyEngine instance
    """
    global _engine
    _engine = PolicyEngine(config)
    return _engine


# Export classes and functions
__all__ = [
    "PolicyEngine",
    "PolicyViolationError",
    "get_policy_engine",
    "reload_policy_engine",
]
