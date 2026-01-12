"""Policy engine for Mother AI OS enterprise security.

The policy module provides a hard security gate that enforces access controls
before any capability execution. Unlike simple confirmation prompts, policy
rules cannot be bypassed by user confirmation.

Key components:
- PolicyEngine: Main class that evaluates capability calls against policy
- PolicyConfig: Configuration model loaded from YAML files
- PolicyDecision: Result of policy evaluation (allow/deny/audit/confirm)
- Condition evaluators: Specific checks for filesystem, commands, network

Usage:
    from mother.policy import get_policy_engine, PolicyViolationError

    engine = get_policy_engine()
    decision = engine.evaluate("shell_run_command", {"command": "ls"})

    if not decision.allowed:
        raise PolicyViolationError(decision)

Configuration:
    Policy is loaded from (in order of precedence):
    1. MOTHER_POLICY_PATH environment variable
    2. ./mother_policy.yaml
    3. ./config/mother_policy.yaml
    4. ~/.config/mother/policy.yaml
    5. Built-in default policy

Safe Mode (MOTHER_SAFE_MODE=1):
    When enabled (default), high-risk capabilities are blocked unless
    explicitly allowed by a policy rule. This includes:
    - Shell command execution
    - Tor/darknet access
    - Unrestricted filesystem writes
    - Network egress to arbitrary domains
"""

from .conditions import (
    evaluate_command_condition,
    evaluate_data_condition,
    evaluate_filesystem_condition,
    evaluate_network_condition,
)
from .engine import (
    PolicyEngine,
    PolicyViolationError,
    get_policy_engine,
    reload_policy_engine,
)
from .loader import (
    PolicyLoadError,
    get_default_policy,
    get_permissive_policy,
    load_policy,
    load_policy_from_file,
    merge_policies,
    save_policy_to_file,
)
from .models import (
    CommandCondition,
    DataClassification,
    DataCondition,
    FilesystemCondition,
    NetworkCondition,
    PolicyAction,
    PolicyConfig,
    PolicyDecision,
    PolicyRule,
    RiskTier,
)

__all__ = [
    # Engine
    "PolicyEngine",
    "PolicyViolationError",
    "get_policy_engine",
    "reload_policy_engine",
    # Models
    "RiskTier",
    "PolicyAction",
    "DataClassification",
    "PolicyDecision",
    "PolicyRule",
    "PolicyConfig",
    "FilesystemCondition",
    "CommandCondition",
    "NetworkCondition",
    "DataCondition",
    # Loader
    "PolicyLoadError",
    "load_policy",
    "load_policy_from_file",
    "get_default_policy",
    "get_permissive_policy",
    "merge_policies",
    "save_policy_to_file",
    # Conditions
    "evaluate_filesystem_condition",
    "evaluate_command_condition",
    "evaluate_network_condition",
    "evaluate_data_condition",
]
