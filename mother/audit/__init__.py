"""Mother AI OS Enterprise Audit Logging.

This module provides comprehensive audit logging for enterprise deployments:
- JSONL format for machine-readable logs
- Automatic log rotation by size
- Sensitive data redaction (PII, API keys, credentials)
- Correlation IDs for request tracing
- Integration with policy engine

Example usage:
    from mother.audit import get_audit_logger, AuditEventType

    # Get the global audit logger
    logger = get_audit_logger()

    # Log a capability request
    correlation_id = logger.log_capability_request(
        capability="filesystem_write",
        plugin="core",
        params={"path": "/workspace/test.txt"},
        user_id="api_key_hash",
    )

    # Log the policy decision
    logger.log_policy_decision(
        capability="filesystem_write",
        plugin="core",
        action="allow",
        allowed=True,
        reason="Path within allowed workspace",
        correlation_id=correlation_id,
    )

    # Log the execution result
    logger.log_capability_result(
        capability="filesystem_write",
        plugin="core",
        success=True,
        duration_ms=15.3,
        correlation_id=correlation_id,
    )
"""

from __future__ import annotations

from .logger import (
    AuditEntry,
    AuditEventType,
    AuditLogConfig,
    AuditLogger,
    audit_log,
    get_audit_logger,
)
from .redaction import (
    RedactionConfig,
    RedactionPattern,
    Redactor,
    SensitiveDataType,
    get_redactor,
    redact,
    redact_string,
)

__all__ = [
    # Logger
    "AuditEventType",
    "AuditEntry",
    "AuditLogConfig",
    "AuditLogger",
    "get_audit_logger",
    "audit_log",
    # Redaction
    "SensitiveDataType",
    "RedactionPattern",
    "RedactionConfig",
    "Redactor",
    "get_redactor",
    "redact",
    "redact_string",
]
