"""Policy models for Mother AI OS enterprise security.

This module defines the data models for the policy engine including:
- PolicyDecision: The result of a policy evaluation
- Rule: A single policy rule with conditions
- Various condition types for filesystem, commands, network, and data
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RiskTier(str, Enum):
    """Risk classification for capabilities."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyAction(str, Enum):
    """Action to take when a rule matches."""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"  # Allow but log with elevated level
    CONFIRM = "confirm"  # Require explicit confirmation


class DataClassification(str, Enum):
    """Data classification levels for exfiltration prevention."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class PolicyDecision(BaseModel):
    """Result of evaluating a policy for a capability call.

    Attributes:
        allowed: Whether the action is permitted
        action: The policy action (allow, deny, audit, confirm)
        reason: Human-readable explanation of the decision
        matched_rules: List of rule names that matched
        risk_tier: Risk level of the capability
        requires_audit: Whether this action should be audit logged
        metadata: Additional context about the decision
    """

    allowed: bool = Field(..., description="Whether the action is permitted")
    action: PolicyAction = Field(..., description="The policy action taken")
    reason: str = Field(..., description="Human-readable explanation")
    matched_rules: list[str] = Field(default_factory=list, description="Rules that matched")
    risk_tier: RiskTier = Field(default=RiskTier.MEDIUM, description="Risk level")
    requires_audit: bool = Field(default=True, description="Should be audit logged")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @classmethod
    def allow(
        cls,
        reason: str = "Allowed by policy",
        matched_rules: list[str] | None = None,
        risk_tier: RiskTier = RiskTier.LOW,
    ) -> PolicyDecision:
        """Create an allow decision."""
        return cls(
            allowed=True,
            action=PolicyAction.ALLOW,
            reason=reason,
            matched_rules=matched_rules or [],
            risk_tier=risk_tier,
            requires_audit=risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL),
        )

    @classmethod
    def deny(
        cls,
        reason: str,
        matched_rules: list[str] | None = None,
        risk_tier: RiskTier = RiskTier.HIGH,
    ) -> PolicyDecision:
        """Create a deny decision."""
        return cls(
            allowed=False,
            action=PolicyAction.DENY,
            reason=reason,
            matched_rules=matched_rules or [],
            risk_tier=risk_tier,
            requires_audit=True,
        )

    @classmethod
    def require_confirmation(
        cls,
        reason: str,
        matched_rules: list[str] | None = None,
        risk_tier: RiskTier = RiskTier.MEDIUM,
    ) -> PolicyDecision:
        """Create a confirmation-required decision."""
        return cls(
            allowed=True,
            action=PolicyAction.CONFIRM,
            reason=reason,
            matched_rules=matched_rules or [],
            risk_tier=risk_tier,
            requires_audit=True,
        )


# -----------------------------------------------------------------------------
# Condition Models
# -----------------------------------------------------------------------------


class FilesystemCondition(BaseModel):
    """Filesystem access policy conditions.

    Attributes:
        allowed_paths: Glob patterns for allowed paths (empty = all denied)
        denied_paths: Glob patterns for explicitly denied paths
        read_only_paths: Paths where only read operations are allowed
        write_restricted: Whether writes are restricted to write_allowed_paths
        write_allowed_paths: Paths where write operations are allowed
        allow_symlinks: Whether to follow symbolic links
        max_file_size: Maximum file size in bytes for read/write operations
    """

    allowed_paths: list[str] = Field(
        default_factory=list,
        description="Glob patterns for allowed paths",
    )
    denied_paths: list[str] = Field(
        default_factory=lambda: [
            "/etc/shadow",
            "/etc/passwd",
            "**/.ssh/**",
            "**/.gnupg/**",
            "**/credentials*",
            "**/*.pem",
            "**/*.key",
            "**/secrets/**",
        ],
        description="Glob patterns for denied paths",
    )
    read_only_paths: list[str] = Field(
        default_factory=lambda: [
            "/etc/**",
            "/usr/**",
            "/bin/**",
            "/sbin/**",
        ],
        description="Paths where only read is allowed",
    )
    write_restricted: bool = Field(
        default=True,
        description="Whether writes are restricted to write_allowed_paths only",
    )
    write_allowed_paths: list[str] = Field(
        default_factory=lambda: [
            "./workspace/**/*",
            "./**/*",
        ],
        description="Paths where write operations are allowed (when write_restricted=True)",
    )
    allow_symlinks: bool = Field(default=False, description="Follow symbolic links")
    max_file_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        description="Maximum file size in bytes",
    )


class CommandCondition(BaseModel):
    """Shell command execution policy conditions.

    Attributes:
        allowed_commands: Regex patterns for allowed commands (empty = all denied in safe mode)
        denied_commands: Regex patterns for explicitly denied commands
        denied_patterns: Dangerous command patterns to block
        allowed_cwd: Allowed working directories
        max_timeout: Maximum execution timeout in seconds
        allow_pipes: Whether to allow piped commands
        allow_redirects: Whether to allow output redirects
    """

    allowed_commands: list[str] = Field(
        default_factory=list,
        description="Regex patterns for allowed commands",
    )
    denied_commands: list[str] = Field(
        default_factory=lambda: [
            r"^rm\s+-rf\s+/",
            r"^rm\s+-rf\s+/\*",
            r"^mkfs\.",
            r"^dd\s+if=",
            r":\(\)\{:\|:&\};:",  # Fork bomb
            r">\s*/dev/sd[a-z]",
            r"^chmod\s+777",
            r"^curl.*\|\s*(ba)?sh",  # Curl pipe to shell
            r"^wget.*\|\s*(ba)?sh",
        ],
        description="Regex patterns for denied commands",
    )
    denied_patterns: list[str] = Field(
        default_factory=lambda: [
            "rm -rf /",
            "> /dev/sda",
            ":(){ :|:& };:",
        ],
        description="Literal dangerous patterns",
    )
    allowed_cwd: list[str] = Field(
        default_factory=list,
        description="Allowed working directories",
    )
    max_timeout: int = Field(default=300, description="Maximum timeout in seconds")
    allow_pipes: bool = Field(default=True, description="Allow piped commands")
    allow_redirects: bool = Field(default=True, description="Allow output redirects")


class NetworkCondition(BaseModel):
    """Network access policy conditions.

    Attributes:
        allowed_domains: Domain patterns that can be accessed
        denied_domains: Domain patterns that are blocked
        allowed_ips: IP addresses/CIDRs that can be accessed
        denied_ips: IP addresses/CIDRs that are blocked
        block_private_ranges: Block RFC1918 private IP ranges
        allowed_ports: Ports that can be accessed (empty = all allowed ports)
        denied_ports: Ports that are blocked
        max_request_size: Maximum request body size in bytes
        max_response_size: Maximum response size in bytes
    """

    allowed_domains: list[str] = Field(
        default_factory=list,
        description="Allowed domain patterns (supports wildcards)",
    )
    denied_domains: list[str] = Field(
        default_factory=lambda: [
            "*.onion",  # Block Tor by default
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        ],
        description="Denied domain patterns",
    )
    allowed_ips: list[str] = Field(
        default_factory=list,
        description="Allowed IP addresses/CIDRs",
    )
    denied_ips: list[str] = Field(
        default_factory=list,
        description="Denied IP addresses/CIDRs",
    )
    block_private_ranges: bool = Field(
        default=True,
        description="Block RFC1918 private IP ranges (10.x, 172.16.x, 192.168.x)",
    )
    allowed_ports: list[int] = Field(
        default_factory=lambda: [80, 443, 8080, 8443],
        description="Allowed ports",
    )
    denied_ports: list[int] = Field(
        default_factory=lambda: [22, 23, 25, 3389],  # SSH, Telnet, SMTP, RDP
        description="Denied ports",
    )
    max_request_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum request body size",
    )
    max_response_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        description="Maximum response size",
    )


class DataCondition(BaseModel):
    """Data classification and exfiltration prevention conditions.

    Attributes:
        max_classification: Maximum data classification level allowed to leave
        block_exfiltration: Block sending data to external systems
        block_pii: Block sending personally identifiable information
        sensitive_patterns: Regex patterns for sensitive data detection
        allowed_export_domains: Domains where data export is allowed
    """

    max_classification: DataClassification = Field(
        default=DataClassification.INTERNAL,
        description="Maximum classification that can be exported",
    )
    block_exfiltration: bool = Field(
        default=True,
        description="Block sending sensitive data externally",
    )
    block_pii: bool = Field(
        default=True,
        description="Block sending personally identifiable information (PII)",
    )
    sensitive_patterns: list[str] = Field(
        default_factory=lambda: [
            r"(?i)api[_-]?key",
            r"(?i)secret[_-]?key",
            r"(?i)password",
            r"(?i)bearer\s+[a-zA-Z0-9\-_]+",
            r"(?i)authorization:\s*bearer",
            r"sk-[a-zA-Z0-9]{20,}",  # OpenAI keys
            r"sk-ant-[a-zA-Z0-9\-]+",  # Anthropic keys
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub PAT
            r"AKIA[0-9A-Z]{16}",  # AWS access key
        ],
        description="Patterns for sensitive data",
    )
    allowed_export_domains: list[str] = Field(
        default_factory=list,
        description="Domains where export is allowed",
    )


# -----------------------------------------------------------------------------
# Rule Model
# -----------------------------------------------------------------------------


class PolicyRule(BaseModel):
    """A single policy rule that evaluates capability calls.

    Attributes:
        name: Unique rule identifier
        description: Human-readable description
        capability_pattern: Regex pattern to match capability names
        action: Action to take when rule matches
        priority: Rule priority (higher = evaluated first)
        conditions: Additional conditions that must be met
        enabled: Whether this rule is active
    """

    name: str = Field(..., description="Unique rule identifier")
    description: str = Field(default="", description="Human-readable description")
    capability_pattern: str = Field(
        ...,
        description="Regex pattern to match capability names (e.g., 'shell_.*', 'filesystem_write')",
    )
    action: PolicyAction = Field(..., description="Action when rule matches")
    priority: int = Field(default=0, description="Rule priority (higher = first)")
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional conditions (params constraints, etc.)",
    )
    enabled: bool = Field(default=True, description="Whether rule is active")

    # Compiled regex (not serialized)
    _compiled_pattern: re.Pattern | None = None

    def matches_capability(self, capability_name: str) -> bool:
        """Check if this rule matches a capability name."""
        if self._compiled_pattern is None:
            self._compiled_pattern = re.compile(self.capability_pattern)
        return bool(self._compiled_pattern.match(capability_name))

    @field_validator("capability_pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """Validate regex pattern is valid."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        return v


# -----------------------------------------------------------------------------
# Policy Configuration Model
# -----------------------------------------------------------------------------


class PolicyConfig(BaseModel):
    """Complete policy configuration.

    Attributes:
        version: Policy schema version
        name: Policy name
        description: Policy description
        rules: List of policy rules
        filesystem: Default filesystem conditions
        commands: Default command conditions
        network: Default network conditions
        data: Default data classification conditions
        default_action: Action when no rules match
        safe_mode: Whether safe mode restrictions apply
    """

    version: str = Field(default="1.0", description="Policy schema version")
    name: str = Field(default="default", description="Policy name")
    description: str = Field(default="", description="Policy description")

    rules: list[PolicyRule] = Field(default_factory=list, description="Policy rules")

    filesystem: FilesystemCondition = Field(
        default_factory=FilesystemCondition,
        description="Filesystem access conditions",
    )
    commands: CommandCondition = Field(
        default_factory=CommandCondition,
        description="Command execution conditions",
    )
    network: NetworkCondition = Field(
        default_factory=NetworkCondition,
        description="Network access conditions",
    )
    data: DataCondition = Field(
        default_factory=DataCondition,
        description="Data classification conditions",
    )

    default_action: PolicyAction = Field(
        default=PolicyAction.DENY,
        description="Action when no rules match",
    )
    safe_mode: bool = Field(
        default=True,
        description="Whether safe mode restrictions apply",
    )

    def get_rules_for_capability(self, capability_name: str) -> list[PolicyRule]:
        """Get all rules that match a capability, sorted by priority."""
        matching = [r for r in self.rules if r.enabled and r.matches_capability(capability_name)]
        return sorted(matching, key=lambda r: -r.priority)


# Export all models
__all__ = [
    "RiskTier",
    "PolicyAction",
    "DataClassification",
    "PolicyDecision",
    "FilesystemCondition",
    "CommandCondition",
    "NetworkCondition",
    "DataCondition",
    "PolicyRule",
    "PolicyConfig",
]
