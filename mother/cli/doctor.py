"""Mother doctor command - production readiness checks.

Provides comprehensive system health checks with PASS/WARN/FAIL status:
- Authentication configuration
- LLM provider configuration
- Security settings
- File system permissions
- Database integrity
- Rate limiting status
"""

import json
import os
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CheckStatus(str, Enum):
    """Status of a health check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    status: CheckStatus
    message: str
    details: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class DoctorReport:
    """Complete doctor report."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        """Count of passed checks."""
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)

    @property
    def warnings(self) -> int:
        """Count of warning checks."""
        return sum(1 for c in self.checks if c.status == CheckStatus.WARN)

    @property
    def failures(self) -> int:
        """Count of failed checks."""
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def is_production_ready(self) -> bool:
        """Check if system is production ready (no failures)."""
        return self.failures == 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "checks": [c.to_dict() for c in self.checks],
            "summary": {
                "passed": self.passed,
                "warnings": self.warnings,
                "failures": self.failures,
                "production_ready": self.is_production_ready,
            },
        }


def check_authentication() -> CheckResult:
    """Check authentication configuration."""
    from ..config.settings import get_settings

    settings = get_settings()

    if not settings.require_auth:
        return CheckResult(
            name="Authentication",
            status=CheckStatus.FAIL,
            message="Authentication is DISABLED",
            details="Set MOTHER_REQUIRE_AUTH=true for production",
        )

    if settings.api_key:
        return CheckResult(
            name="Authentication",
            status=CheckStatus.PASS,
            message="Legacy API key configured",
            details="Consider migrating to multi-key mode for better security",
        )

    return CheckResult(
        name="Authentication",
        status=CheckStatus.WARN,
        message="No legacy API key set",
        details="Using multi-key mode or no authentication",
    )


def check_multikey_mode() -> CheckResult:
    """Check multi-key store status."""
    from ..config.settings import get_settings

    settings = get_settings()
    db_path = settings.config_dir / "keys.db"

    if not db_path.exists():
        return CheckResult(
            name="Multi-Key Mode",
            status=CheckStatus.WARN,
            message="Key store not initialized",
            details="Run 'mother keys init' to enable multi-key authentication",
        )

    try:
        from ..auth.keys import APIKeyStore

        store = APIKeyStore()
        count = store.key_count()

        if count == 0:
            return CheckResult(
                name="Multi-Key Mode",
                status=CheckStatus.WARN,
                message="Key store empty",
                details="Run 'mother keys add <name>' to create an API key",
            )

        return CheckResult(
            name="Multi-Key Mode",
            status=CheckStatus.PASS,
            message=f"Multi-key store initialized ({count} keys)",
            details=str(db_path),
        )
    except Exception as e:
        return CheckResult(
            name="Multi-Key Mode",
            status=CheckStatus.FAIL,
            message="Key store corrupted",
            details=str(e),
        )


def check_llm_provider() -> CheckResult:
    """Check LLM provider configuration."""
    from ..config.settings import get_settings

    settings = get_settings()
    provider = settings.ai_provider

    key_map = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "zhipu": settings.zhipu_api_key,
        "gemini": settings.gemini_api_key,
    }

    api_key = key_map.get(provider)

    if not api_key:
        return CheckResult(
            name="LLM Provider",
            status=CheckStatus.FAIL,
            message=f"No API key for provider '{provider}'",
            details=f"Set {provider.upper()}_API_KEY environment variable",
        )

    # Check if key looks valid (has reasonable length)
    if len(api_key) < 20:
        return CheckResult(
            name="LLM Provider",
            status=CheckStatus.WARN,
            message=f"API key for '{provider}' seems short",
            details="Verify your API key is correct",
        )

    return CheckResult(
        name="LLM Provider",
        status=CheckStatus.PASS,
        message=f"Provider '{provider}' configured",
        details=f"Model: {settings.llm_model or 'default'}",
    )


def check_safe_mode() -> CheckResult:
    """Check safe mode status."""
    from ..config.settings import get_settings

    settings = get_settings()

    if not settings.safe_mode:
        return CheckResult(
            name="Safe Mode",
            status=CheckStatus.WARN,
            message="Safe mode is DISABLED",
            details="High-risk capabilities are allowed. Set MOTHER_SAFE_MODE=true for production",
        )

    return CheckResult(
        name="Safe Mode",
        status=CheckStatus.PASS,
        message="Safe mode enabled",
        details="High-risk capabilities are restricted",
    )


def check_sandbox_mode() -> CheckResult:
    """Check sandbox mode status."""
    from ..config.settings import get_settings

    settings = get_settings()

    if not settings.sandbox_mode:
        return CheckResult(
            name="Sandbox Mode",
            status=CheckStatus.WARN,
            message="Sandbox mode is DISABLED",
            details="File operations are not sandboxed. Set MOTHER_SANDBOX_MODE=true for production",
        )

    return CheckResult(
        name="Sandbox Mode",
        status=CheckStatus.PASS,
        message="Sandbox mode enabled",
        details=f"Workspace: {settings.workspace_dir}",
    )


def check_audit_logging() -> CheckResult:
    """Check audit logging configuration."""
    from ..config.settings import get_settings

    settings = get_settings()

    if not settings.audit_log_enabled:
        return CheckResult(
            name="Audit Logging",
            status=CheckStatus.WARN,
            message="Audit logging is DISABLED",
            details="Set MOTHER_AUDIT_ENABLED=true for compliance",
        )

    log_path = Path(settings.audit_log_path)
    log_dir = log_path.parent

    # Check if directory exists or can be created
    if not log_dir.exists():
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return CheckResult(
                name="Audit Logging",
                status=CheckStatus.FAIL,
                message="Cannot create audit log directory",
                details=f"No write permission for {log_dir}",
            )

    # Check if file is writable
    if log_path.exists() and not os.access(log_path, os.W_OK):
        return CheckResult(
            name="Audit Logging",
            status=CheckStatus.FAIL,
            message="Audit log not writable",
            details=str(log_path),
        )

    return CheckResult(
        name="Audit Logging",
        status=CheckStatus.PASS,
        message="Audit logging enabled",
        details=str(log_path),
    )


def check_policy_file() -> CheckResult:
    """Check policy file configuration."""
    from ..config.settings import get_settings

    settings = get_settings()

    if not settings.policy_path:
        return CheckResult(
            name="Policy File",
            status=CheckStatus.WARN,
            message="No custom policy file",
            details="Using default policy. Set MOTHER_POLICY_PATH for custom restrictions",
        )

    policy_path = Path(settings.policy_path)

    if not policy_path.exists():
        return CheckResult(
            name="Policy File",
            status=CheckStatus.FAIL,
            message="Policy file not found",
            details=str(policy_path),
        )

    # Try to parse the policy
    try:
        import yaml

        with open(policy_path) as f:
            yaml.safe_load(f)

        return CheckResult(
            name="Policy File",
            status=CheckStatus.PASS,
            message="Policy file configured",
            details=str(policy_path),
        )
    except ImportError:
        return CheckResult(
            name="Policy File",
            status=CheckStatus.PASS,
            message="Policy file exists (YAML parsing skipped)",
            details=str(policy_path),
        )
    except Exception as e:
        return CheckResult(
            name="Policy File",
            status=CheckStatus.FAIL,
            message="Policy file invalid",
            details=str(e),
        )


def check_workspace_directory() -> CheckResult:
    """Check workspace directory."""
    from ..config.settings import get_settings

    settings = get_settings()
    workspace = Path(settings.workspace_dir)

    if not workspace.exists():
        try:
            workspace.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return CheckResult(
                name="Workspace Directory",
                status=CheckStatus.FAIL,
                message="Cannot create workspace directory",
                details=f"No write permission for {workspace.parent}",
            )

    if not os.access(workspace, os.W_OK):
        return CheckResult(
            name="Workspace Directory",
            status=CheckStatus.FAIL,
            message="Workspace not writable",
            details=str(workspace),
        )

    return CheckResult(
        name="Workspace Directory",
        status=CheckStatus.PASS,
        message="Workspace directory accessible",
        details=str(workspace.absolute()),
    )


def check_config_directory() -> CheckResult:
    """Check config directory."""
    from ..config.settings import get_settings

    settings = get_settings()
    config_dir = Path(settings.config_dir)

    if not config_dir.exists():
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return CheckResult(
                name="Config Directory",
                status=CheckStatus.FAIL,
                message="Cannot create config directory",
                details=f"No write permission for {config_dir.parent}",
            )

    if not os.access(config_dir, os.R_OK):
        return CheckResult(
            name="Config Directory",
            status=CheckStatus.FAIL,
            message="Config directory not readable",
            details=str(config_dir),
        )

    return CheckResult(
        name="Config Directory",
        status=CheckStatus.PASS,
        message="Config directory accessible",
        details=str(config_dir.absolute()),
    )


def check_rate_limiting() -> CheckResult:
    """Check rate limiting configuration."""
    try:
        from ..api.ratelimit import RateLimitConfig

        config = RateLimitConfig()

        if not config.enabled:
            return CheckResult(
                name="Rate Limiting",
                status=CheckStatus.WARN,
                message="Rate limiting is DISABLED",
                details="Enable rate limiting for production",
            )

        return CheckResult(
            name="Rate Limiting",
            status=CheckStatus.PASS,
            message="Rate limiting enabled",
            details=f"Default: {config.default_rpm} RPM, Admin: {config.admin_rpm} RPM",
        )
    except ImportError:
        return CheckResult(
            name="Rate Limiting",
            status=CheckStatus.WARN,
            message="Rate limiting module not available",
            details="Install rate limiting dependencies",
        )


def check_database_integrity() -> CheckResult:
    """Check database file integrity."""
    from ..config.settings import get_settings

    settings = get_settings()
    issues = []

    # Check keys.db
    keys_db = settings.config_dir / "keys.db"
    if keys_db.exists():
        try:
            conn = sqlite3.connect(keys_db)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()

            if result != "ok":
                issues.append(f"keys.db: {result}")
        except Exception as e:
            issues.append(f"keys.db: {e}")

    # Check other common database files
    for db_name in ["sessions.db", "memory.db"]:
        db_path = settings.config_dir / db_name
        if db_path.exists():
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                conn.close()

                if result != "ok":
                    issues.append(f"{db_name}: {result}")
            except Exception as e:
                issues.append(f"{db_name}: {e}")

    if issues:
        return CheckResult(
            name="Database Integrity",
            status=CheckStatus.FAIL,
            message="Database integrity issues found",
            details="; ".join(issues),
        )

    return CheckResult(
        name="Database Integrity",
        status=CheckStatus.PASS,
        message="All databases healthy",
        details="PRAGMA integrity_check passed",
    )


def check_file_permissions() -> CheckResult:
    """Check sensitive file permissions."""
    from ..config.settings import CREDENTIALS_FILE, get_settings

    settings = get_settings()
    issues = []

    # Check credentials file
    if CREDENTIALS_FILE.exists():
        mode = CREDENTIALS_FILE.stat().st_mode & 0o777
        if mode > 0o600:
            issues.append(f"credentials.env: mode {oct(mode)} (should be 0600)")

    # Check keys.db
    keys_db = settings.config_dir / "keys.db"
    if keys_db.exists():
        mode = keys_db.stat().st_mode & 0o777
        if mode > 0o600:
            issues.append(f"keys.db: mode {oct(mode)} (should be 0600)")

    if issues:
        return CheckResult(
            name="File Permissions",
            status=CheckStatus.WARN,
            message="Loose file permissions detected",
            details="; ".join(issues),
        )

    return CheckResult(
        name="File Permissions",
        status=CheckStatus.PASS,
        message="File permissions appropriate",
        details="Sensitive files have restricted access",
    )


def check_network_binding() -> CheckResult:
    """Check API network binding."""
    from ..config.settings import get_settings

    settings = get_settings()

    if settings.api_host == "0.0.0.0":
        return CheckResult(
            name="Network Binding",
            status=CheckStatus.WARN,
            message="API bound to all interfaces",
            details="Set MOTHER_HOST=127.0.0.1 unless external access is required",
        )

    if settings.api_host in ("127.0.0.1", "localhost"):
        return CheckResult(
            name="Network Binding",
            status=CheckStatus.PASS,
            message="API bound to localhost only",
            details=f"Listening on {settings.api_host}:{settings.api_port}",
        )

    return CheckResult(
        name="Network Binding",
        status=CheckStatus.WARN,
        message=f"API bound to specific interface: {settings.api_host}",
        details="Verify this is the intended configuration",
    )


def run_all_checks() -> DoctorReport:
    """Run all production readiness checks."""
    report = DoctorReport()

    checks = [
        check_authentication,
        check_multikey_mode,
        check_llm_provider,
        check_safe_mode,
        check_sandbox_mode,
        check_audit_logging,
        check_policy_file,
        check_workspace_directory,
        check_config_directory,
        check_rate_limiting,
        check_database_integrity,
        check_file_permissions,
        check_network_binding,
    ]

    for check_fn in checks:
        try:
            result = check_fn()
            report.checks.append(result)
        except Exception as e:
            report.checks.append(
                CheckResult(
                    name=check_fn.__name__.replace("check_", "").replace("_", " ").title(),
                    status=CheckStatus.FAIL,
                    message="Check failed with exception",
                    details=str(e),
                )
            )

    return report


def format_status(status: CheckStatus) -> str:
    """Format status with color codes."""
    if status == CheckStatus.PASS:
        return "\033[92m[PASS]\033[0m"
    elif status == CheckStatus.WARN:
        return "\033[93m[WARN]\033[0m"
    else:
        return "\033[91m[FAIL]\033[0m"


def print_report(report: DoctorReport, verbose: bool = False) -> None:
    """Print the report to stdout."""
    print("\nMother Doctor - Production Readiness Check")
    print("=" * 50)

    for check in report.checks:
        status_str = format_status(check.status)
        print(f"{status_str} {check.name}: {check.message}")
        if verbose and check.details:
            print(f"         {check.details}")

    print("=" * 50)
    print(f"Summary: {report.passed} passed, {report.warnings} warnings, {report.failures} failures")

    if report.is_production_ready:
        print("\033[92m\nSystem is production ready!\033[0m")
    else:
        print("\033[91m\nSystem has issues that should be addressed.\033[0m")


def cmd_doctor(verbose: bool = False, json_output: bool = False) -> int:
    """Run the doctor command.

    Args:
        verbose: Show detailed information for each check
        json_output: Output as JSON

    Returns:
        Exit code (0 if production ready, 1 if issues found)
    """
    report = run_all_checks()

    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report, verbose=verbose)

    return 0 if report.is_production_ready else 1


# Exports
__all__ = [
    "CheckStatus",
    "CheckResult",
    "DoctorReport",
    "run_all_checks",
    "cmd_doctor",
]
