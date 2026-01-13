#!/usr/bin/env python3
"""Enterprise Features Demo for Mother AI OS.

This script demonstrates all enterprise-grade security features:
- Policy Engine (centralized capability authorization)
- Safe Mode (restrictive default configuration)
- Capability Schema Validation with versioning
- Enterprise Audit Logging (JSONL with rotation/PII redaction)
- Sandbox/Isolation (resource limits, workspace isolation)
- High-Risk Plugin Control (disabled-by-default)
- Edition-based Feature Gating

Run: python examples/enterprise_demo.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

# ============================================================================
# 1. POLICY ENGINE DEMO
# ============================================================================


def demo_policy_engine() -> None:
    """Demonstrate the Policy Engine for centralized capability control."""
    print("\n" + "=" * 60)
    print("1. POLICY ENGINE DEMO")
    print("=" * 60)

    from mother.policy import PolicyAction, PolicyConfig, PolicyEngine, PolicyRule

    # Create policy rules
    rules = [
        PolicyRule(
            name="block-shell",
            description="Block shell execution in production",
            capability_pattern="shell_.*",
            action=PolicyAction.DENY,
        ),
        PolicyRule(
            name="audit-filesystem",
            description="Audit all filesystem operations",
            capability_pattern="filesystem_.*",
            action=PolicyAction.AUDIT,
        ),
        PolicyRule(
            name="confirm-delete",
            description="Require confirmation for deletions",
            capability_pattern=".*_delete_.*",
            action=PolicyAction.CONFIRM,
        ),
    ]

    # Create policy config and engine
    config = PolicyConfig(rules=rules)
    engine = PolicyEngine(config)

    print(f"\nRegistered {len(rules)} policy rules:")
    for rule in rules:
        print(f"  - {rule.name}: {rule.action.value} ({rule.capability_pattern})")

    # Evaluate capabilities
    test_cases = [
        "shell_execute_command",
        "filesystem_read_file",
        "filesystem_delete_file",
        "email_send",
    ]

    print("\nPolicy evaluations:")
    for capability in test_cases:
        result = engine.evaluate(capability, {})
        status = "ALLOWED" if result.allowed else "DENIED"
        print(f"  {capability}: {status} - {result.action.value}")


# ============================================================================
# 2. SAFE MODE DEMO
# ============================================================================


def demo_safe_mode() -> None:
    """Demonstrate Safe Mode configuration."""
    print("\n" + "=" * 60)
    print("2. SAFE MODE DEMO")
    print("=" * 60)

    from mother.config import Settings

    # Show default (non-safe) settings
    print("\nDefault settings (MOTHER_SAFE_MODE=0):")
    settings = Settings(safe_mode=False)
    print(f"  Safe mode: {settings.safe_mode}")

    # Show safe mode settings
    print("\nSafe mode settings (MOTHER_SAFE_MODE=1):")
    safe_settings = Settings(safe_mode=True)
    print(f"  Safe mode: {safe_settings.safe_mode}")

    print("\nSafe mode enables:")
    print("  - Strict policy enforcement")
    print("  - High-risk plugins disabled")
    print("  - All actions logged")
    print("  - Confirmation required for destructive operations")


# ============================================================================
# 3. SCHEMA VALIDATION DEMO
# ============================================================================


def demo_schema_validation() -> None:
    """Demonstrate capability schema validation and versioning."""
    print("\n" + "=" * 60)
    print("3. SCHEMA VALIDATION DEMO")
    print("=" * 60)

    from mother.plugins.manifest import CapabilitySpec, ParameterSpec, ParameterType
    from mother.plugins.schema import (
        SchemaValidator,
        is_version_compatible,
        parse_semver,
    )

    # Version parsing and comparison
    print("\nVersion parsing:")
    v1 = parse_semver("1.2.3")
    v2 = parse_semver("2.0.0-beta.1")
    # Returns tuple: (major, minor, patch, prerelease, build_metadata)
    print(f"  1.2.3 -> major={v1[0]}, minor={v1[1]}, patch={v1[2]}")
    print(f"  2.0.0-beta.1 -> major={v2[0]}, prerelease={v2[3]}")

    # Version compatibility (required, actual)
    print("\nVersion compatibility:")
    tests = [
        (">=1.0.0", "1.0.0"),
        (">=1.0.0", "0.9.0"),
        ("^1.0.0", "1.5.0"),
        ("^1.0.0", "2.0.0"),
    ]
    for requirement, version in tests:
        compatible = is_version_compatible(requirement, version)
        print(f"  {version} matches {requirement}: {compatible}")

    # Schema validation
    print("\nSchema validation:")
    validator = SchemaValidator()

    # Create a capability spec
    capability = CapabilitySpec(
        name="write_file",
        description="Write content to a file",
        parameters=[
            ParameterSpec(name="path", type=ParameterType.STRING, required=True, description="File path"),
            ParameterSpec(name="content", type=ParameterType.STRING, required=True, description="Content"),
        ],
    )

    # Validate parameters
    valid_params = {"path": "/tmp/test.txt", "content": "Hello, World!"}
    invalid_params = {"path": "/tmp/test.txt"}  # Missing content

    try:
        validator.validate(capability, valid_params)
        print("  Valid params: PASSED")
    except Exception as e:
        print(f"  Valid params: FAILED - {e}")

    try:
        validator.validate(capability, invalid_params)
        print("  Invalid params: PASSED (unexpected)")
    except Exception as e:
        print(f"  Invalid params: REJECTED - {type(e).__name__}")


# ============================================================================
# 4. AUDIT LOGGING DEMO
# ============================================================================


def demo_audit_logging() -> None:
    """Demonstrate enterprise audit logging with PII redaction."""
    print("\n" + "=" * 60)
    print("4. AUDIT LOGGING DEMO")
    print("=" * 60)

    from mother.audit import (
        AuditLogConfig,
        AuditLogger,
        redact,
    )

    # Create a temporary log directory
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        # Configure audit logging
        config = AuditLogConfig(
            log_dir=log_dir,
            max_file_size_mb=10,
            max_files=5,
            flush_interval=0.1,
            include_params=True,
            redact_sensitive=True,
        )

        print("\nAudit log configuration:")
        print(f"  Log directory: {log_dir}")
        print(f"  Max file size: {config.max_file_size_mb}MB")
        print(f"  Max files: {config.max_files}")
        print(f"  PII redaction: {config.redact_sensitive}")

        # PII Redaction demo
        print("\nPII Redaction examples:")
        sensitive_data = {
            "api_key": "sk-ant-abc123xyz789def456",
            "password": "super_secret_password",
            "user_email": "john.doe@example.com",
            "aws_key": "AKIAIOSFODNN7EXAMPLE",
            "credit_card": "4111-1111-1111-1111",
            "safe_data": "This is safe",
        }

        redacted = redact(sensitive_data)
        print("  Original -> Redacted:")
        for key in sensitive_data:
            print(f"    {key}: {sensitive_data[key][:20]}... -> {redacted[key]}")

        # Create logger and log some events
        logger = AuditLogger(config)

        correlation_id = logger.log_capability_request(
            capability="filesystem_write_file",
            plugin="core",
            params={"path": "/workspace/output.txt", "api_key": "sk-ant-secret"},
            user_id="user_123",
        )
        print(f"\nLogged capability request with correlation_id: {correlation_id}")

        logger.log_policy_decision(
            capability="filesystem_write_file",
            plugin="core",
            action="allow",
            allowed=True,
            reason="Policy allowed filesystem write to workspace",
            correlation_id=correlation_id,
        )

        logger.log_capability_result(
            capability="filesystem_write_file",
            plugin="core",
            success=True,
            duration_ms=150.5,
            correlation_id=correlation_id,
        )

        # Flush and show sample log entries
        logger.flush()

        print("\nSample log entries (JSONL format):")
        log_file = log_dir / "audit.jsonl"
        if log_file.exists():
            with open(log_file) as f:
                for line in f:
                    entry = json.loads(line)
                    print(f"  {entry['event_type']}: {entry.get('capability', 'N/A')}")


# ============================================================================
# 5. SANDBOX/ISOLATION DEMO
# ============================================================================


def demo_sandbox_isolation() -> None:
    """Demonstrate sandbox and resource isolation."""
    print("\n" + "=" * 60)
    print("5. SANDBOX/ISOLATION DEMO")
    print("=" * 60)

    from mother.plugins.sandbox import (
        ResourceLimits,
        SandboxConfig,
        SandboxManager,
        WorkspaceConfig,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Configure resource limits
        limits = ResourceLimits(
            max_cpu_seconds=30,
            max_memory_mb=256,
            max_execution_time=60,
            max_file_size_mb=50,
            max_subprocess=5,
        )

        print("\nResource limits:")
        print(f"  Max CPU seconds: {limits.max_cpu_seconds}")
        print(f"  Max memory: {limits.max_memory_mb}MB")
        print(f"  Max execution time: {limits.max_execution_time}s")
        print(f"  Max file size: {limits.max_file_size_mb}MB")
        print(f"  Max subprocesses: {limits.max_subprocess}")

        # Configure workspace isolation
        workspace_config = WorkspaceConfig(
            workspace_dir=workspace,
            allow_read_outside=True,
            allowed_read_paths=["/usr/share", "/etc/mother/templates"],
        )

        print("\nWorkspace isolation:")
        print(f"  Workspace directory: {workspace}")
        print(f"  Allow read outside: {workspace_config.allow_read_outside}")
        print(f"  Allowed read paths: {workspace_config.allowed_read_paths}")

        # Test path validation
        test_paths = [
            (workspace / "output.txt", True),
            (Path("/etc/passwd"), False),
            (Path("/usr/share/doc/readme.txt"), True),  # allowed read path
        ]

        print("\nPath validation (write access):")
        for path, expected in test_paths:
            allowed = workspace_config.is_path_allowed_write(path)
            status = "ALLOWED" if allowed else "DENIED"
            print(f"  {path}: {status}")

        # Create sandbox config
        sandbox_config = SandboxConfig(
            enabled=True,
            resource_limits=limits,
            workspace=workspace_config,
            allow_shell=False,
            allow_network=True,
        )

        print("\nSandbox configuration:")
        print(f"  Enabled: {sandbox_config.enabled}")
        print(f"  Shell allowed: {sandbox_config.allow_shell}")
        print(f"  Network allowed: {sandbox_config.allow_network}")

        # Create sandbox manager
        manager = SandboxManager(sandbox_config)

        # Create sandboxes for plugins
        manager.create_sandbox("safe-plugin", ["filesystem:read"])
        manager.create_sandbox("network-plugin", ["network:internal"])

        # Check sandbox exists
        sandbox1 = manager.get_sandbox("safe-plugin")
        sandbox2 = manager.get_sandbox("network-plugin")
        print("\nCreated sandboxes for 2 plugins:")
        print(f"  - safe-plugin: {sandbox1 is not None}")
        print(f"  - network-plugin: {sandbox2 is not None}")


# ============================================================================
# 6. HIGH-RISK PLUGIN CONTROL DEMO
# ============================================================================


def demo_high_risk_plugins() -> None:
    """Demonstrate high-risk plugin control."""
    print("\n" + "=" * 60)
    print("6. HIGH-RISK PLUGIN CONTROL DEMO")
    print("=" * 60)

    from mother.plugins import PluginConfig
    from mother.plugins.manifest import HIGH_RISK_PERMISSIONS, RiskLevel

    # Show high-risk permissions
    print("\nHigh-risk permissions (trigger disabled-by-default):")
    for perm in sorted(HIGH_RISK_PERMISSIONS):
        print(f"  - {perm}")

    # Show risk levels
    print("\nRisk levels:")
    for level in RiskLevel:
        disabled = level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        status = "disabled by default" if disabled else "enabled by default"
        print(f"  {level.value.upper()}: {status}")

    # Show plugin config options
    print("\nPluginConfig options for high-risk handling:")
    default_config = PluginConfig()
    print(f"  allow_high_risk_plugins: {default_config.allow_high_risk_plugins} (default)")
    print(f"  explicitly_enabled_plugins: {default_config.explicitly_enabled_plugins}")

    # Show how to explicitly enable a high-risk plugin
    print("\nExplicitly enabling high-risk plugins:")
    print("  config = PluginConfig(")
    print('      explicitly_enabled_plugins=["trusted-shell-plugin"],')
    print("  )")

    # Show how to allow all high-risk plugins (not recommended)
    print("\nAllow all high-risk plugins (NOT recommended for production):")
    print("  config = PluginConfig(allow_high_risk_plugins=True)")


# ============================================================================
# 7. EDITION FEATURE GATING DEMO
# ============================================================================


def demo_edition_features() -> None:
    """Demonstrate edition-based feature gating."""
    print("\n" + "=" * 60)
    print("7. EDITION FEATURE GATING DEMO")
    print("=" * 60)

    from mother.config import Edition, EditionManager

    editions = [Edition.COMMUNITY, Edition.PROFESSIONAL, Edition.ENTERPRISE]

    print("\nFeature comparison by edition:")
    print("-" * 70)
    print(f"{'Feature':<30} {'Community':>12} {'Professional':>12} {'Enterprise':>12}")
    print("-" * 70)

    features = [
        ("policy_engine", lambda m: m.features.policy_engine),
        ("custom_policy_rules", lambda m: "Yes" if m.has_custom_policy_rules() else "No"),
        ("audit_retention_days", lambda m: str(m.get_audit_retention_days()) if m.get_audit_retention_days() > 0 else "Unlimited"),
        ("pii_redaction", lambda m: m.get_pii_redaction_level()),
        ("sandbox_isolation", lambda m: m.features.sandbox_isolation),
        ("ldap_sso", lambda m: "Yes" if m.has_ldap_sso() else "No"),
        ("dedicated_support", lambda m: "Yes" if m.features.dedicated_support else "No"),
        ("sla_percentage", lambda m: f"{m.features.sla_percentage}%" if m.features.sla_percentage else "No"),
    ]

    for feature_name, getter in features:
        values = []
        for edition in editions:
            manager = EditionManager(edition)
            values.append(getter(manager))
        print(f"{feature_name:<30} {values[0]:>12} {values[1]:>12} {values[2]:>12}")

    print("-" * 70)

    # Custom PII patterns (Enterprise only)
    print("\nCustom PII patterns (Enterprise only):")
    enterprise = EditionManager(Edition.ENTERPRISE)
    enterprise.set_custom_pii_patterns([r"\bACME-\d{8}\b", r"\bINTERNAL-[A-Z]{4}\b"])
    print(f"  Custom patterns: {enterprise.get_custom_pii_patterns()}")

    community = EditionManager(Edition.COMMUNITY)
    try:
        community.set_custom_pii_patterns([r"\bTEST\b"])
    except PermissionError as e:
        print(f"  Community edition: PermissionError - {e}")


# ============================================================================
# MAIN
# ============================================================================


def main() -> None:
    """Run all enterprise feature demos."""
    print("=" * 60)
    print("MOTHER AI OS - ENTERPRISE FEATURES DEMO")
    print("=" * 60)
    print("\nThis demo showcases all enterprise-grade security features")
    print("implemented in Mother AI OS.\n")

    demos = [
        demo_policy_engine,
        demo_safe_mode,
        demo_schema_validation,
        demo_audit_logging,
        demo_sandbox_isolation,
        demo_high_risk_plugins,
        demo_edition_features,
    ]

    for demo in demos:
        try:
            demo()
        except Exception as e:
            print(f"\n  ERROR: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nFor more information, see:")
    print("  - Security documentation: website/docs/concepts/security.md")
    print("  - Enterprise deployment: website/docs/deployment/enterprise.md")
    print("  - API reference: website/docs/api/")


if __name__ == "__main__":
    main()
