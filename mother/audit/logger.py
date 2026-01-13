"""Enterprise audit logging for Mother AI OS.

This module provides structured JSONL audit logging with:
- JSONL format for machine-readable logs
- Log rotation by size and time
- Sensitive data redaction
- Correlation IDs for request tracing
- Risk tier and policy decision logging
"""

from __future__ import annotations

import atexit
import json
import logging
import threading
import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .redaction import get_redactor

logger = logging.getLogger("mother.audit")


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Capability events
    CAPABILITY_REQUEST = "capability_request"
    CAPABILITY_ALLOWED = "capability_allowed"
    CAPABILITY_DENIED = "capability_denied"
    CAPABILITY_EXECUTED = "capability_executed"
    CAPABILITY_FAILED = "capability_failed"

    # Policy events
    POLICY_EVALUATION = "policy_evaluation"
    POLICY_VIOLATION = "policy_violation"

    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_REVOKED = "auth_revoked"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CONFIG_CHANGE = "config_change"

    # Plugin events
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_UNLOADED = "plugin_unloaded"
    PLUGIN_ERROR = "plugin_error"

    # Data events
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    SENSITIVE_DATA_DETECTED = "sensitive_data_detected"


class AuditEntry(BaseModel):
    """A single audit log entry.

    Attributes:
        timestamp: ISO 8601 timestamp
        event_type: Type of audit event
        correlation_id: Request correlation ID for tracing
        session_id: Session identifier
        user_id: User/API key identifier
        capability: Capability name (if applicable)
        plugin: Plugin name (if applicable)
        action: Policy action taken
        risk_tier: Risk level of the action
        allowed: Whether the action was allowed
        reason: Human-readable explanation
        params: Sanitized parameters (redacted)
        result: Sanitized result (redacted)
        metadata: Additional context
        duration_ms: Execution duration in milliseconds
        source_ip: Client IP address
        user_agent: Client user agent
    """

    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    event_type: AuditEventType
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str | None = None
    user_id: str | None = None
    capability: str | None = None
    plugin: str | None = None
    action: str | None = None
    risk_tier: str | None = None
    allowed: bool | None = None
    reason: str | None = None
    params: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = None
    source_ip: str | None = None
    user_agent: str | None = None


class AuditLogConfig(BaseModel):
    """Configuration for the audit logger.

    Attributes:
        enabled: Whether audit logging is enabled
        log_path: Path to the audit log file
        max_file_size_mb: Maximum size before rotation (MB)
        max_files: Maximum number of rotated files to keep
        rotate_on_startup: Create new log file on each startup
        include_params: Include (redacted) parameters in logs
        include_results: Include (redacted) results in logs
        redact_sensitive: Enable sensitive data redaction
        async_write: Use async/buffered writes
        buffer_size: Number of entries to buffer before flush
        flush_interval_seconds: Seconds between auto-flushes
    """

    enabled: bool = True
    log_path: Path = Field(default=Path("./logs/audit.jsonl"))
    max_file_size_mb: int = 100
    max_file_size_bytes: int | None = None  # Override for testing (takes precedence)
    max_files: int = 10
    rotate_on_startup: bool = False
    include_params: bool = True
    include_results: bool = True
    redact_sensitive: bool = True
    async_write: bool = True
    buffer_size: int = 100
    flush_interval_seconds: int = 5


class AuditLogger:
    """Enterprise audit logger with JSONL output and log rotation.

    Thread-safe logger that writes structured audit events to JSONL files
    with automatic rotation and sensitive data redaction.
    """

    def __init__(self, config: AuditLogConfig | None = None):
        """Initialize the audit logger.

        Args:
            config: Audit logging configuration
        """
        self.config = config or AuditLogConfig()
        self._redactor = get_redactor() if self.config.redact_sensitive else None
        self._file_handle: Any | None = None
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        self._current_file_size = 0

        if self.config.enabled:
            self._initialize_log_file()
            atexit.register(self.close)

    def _initialize_log_file(self) -> None:
        """Initialize the log file, creating directories if needed."""
        try:
            # Ensure directory exists
            self.config.log_path.parent.mkdir(parents=True, exist_ok=True)

            # Check for rotation on startup
            if self.config.rotate_on_startup and self.config.log_path.exists():
                self._rotate_logs()

            # Open file in append mode
            self._file_handle = open(self.config.log_path, "a", encoding="utf-8")
            self._current_file_size = self.config.log_path.stat().st_size if self.config.log_path.exists() else 0

            logger.info(f"Audit logging initialized: {self.config.log_path}")
        except Exception as e:
            logger.error(f"Failed to initialize audit log: {e}")
            self.config.enabled = False

    def _rotate_logs(self) -> None:
        """Rotate log files."""
        if not self.config.log_path.exists():
            return

        # Close current file
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

        # Generate rotation timestamp
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        rotated_name = f"{self.config.log_path.stem}_{timestamp}{self.config.log_path.suffix}"
        rotated_path = self.config.log_path.parent / rotated_name

        # Rename current log
        try:
            self.config.log_path.rename(rotated_path)
            logger.info(f"Rotated audit log to: {rotated_path}")
        except Exception as e:
            logger.error(f"Failed to rotate audit log: {e}")

        # Clean up old files
        self._cleanup_old_logs()

        # Reset file size counter
        self._current_file_size = 0

    def _cleanup_old_logs(self) -> None:
        """Remove old rotated log files beyond max_files limit."""
        log_dir = self.config.log_path.parent
        pattern = f"{self.config.log_path.stem}_*{self.config.log_path.suffix}"

        try:
            # Get all rotated files sorted by modification time
            rotated_files = sorted(
                log_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # Remove files beyond the limit
            for old_file in rotated_files[self.config.max_files - 1 :]:
                try:
                    old_file.unlink()
                    logger.debug(f"Removed old audit log: {old_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove old audit log {old_file}: {e}")

        except Exception as e:
            logger.warning(f"Failed to cleanup old audit logs: {e}")

    def _should_rotate(self) -> bool:
        """Check if log rotation is needed."""
        if self.config.max_file_size_bytes is not None:
            max_size_bytes = self.config.max_file_size_bytes
        else:
            max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
        return self._current_file_size >= max_size_bytes

    def _write_entry(self, entry: AuditEntry) -> None:
        """Write an audit entry to the log file.

        Args:
            entry: The audit entry to write
        """
        if not self.config.enabled:
            return

        try:
            # Serialize to JSON
            entry_dict = entry.model_dump(exclude_none=True)

            # Redact sensitive data if enabled
            if self._redactor:
                entry_dict = self._redactor.redact_value(entry_dict)

            json_line = json.dumps(entry_dict, default=str) + "\n"

            with self._lock:
                if self.config.async_write:
                    self._buffer.append(json_line)
                    if len(self._buffer) >= self.config.buffer_size:
                        self._flush_buffer()
                else:
                    self._write_direct(json_line)

        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}")

    def _write_direct(self, json_line: str) -> None:
        """Write directly to file (must be called with lock held)."""
        if not self._file_handle:
            self._initialize_log_file()

        if self._file_handle:
            # Check for rotation
            if self._should_rotate():
                self._rotate_logs()
                self._initialize_log_file()

            self._file_handle.write(json_line)
            self._file_handle.flush()
            self._current_file_size += len(json_line.encode("utf-8"))

    def _flush_buffer(self) -> None:
        """Flush the buffer to disk (must be called with lock held)."""
        if not self._buffer:
            return

        if not self._file_handle:
            self._initialize_log_file()

        if self._file_handle:
            # Check for rotation before writing
            if self._should_rotate():
                self._rotate_logs()
                self._initialize_log_file()

            for line in self._buffer:
                self._file_handle.write(line)
                self._current_file_size += len(line.encode("utf-8"))

            self._file_handle.flush()
            self._buffer.clear()

    def flush(self) -> None:
        """Manually flush buffered entries to disk."""
        with self._lock:
            self._flush_buffer()

    def close(self) -> None:
        """Close the audit logger and flush remaining entries."""
        with self._lock:
            self._flush_buffer()
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None

    # --- High-level logging methods ---

    def log_capability_request(
        self,
        capability: str,
        plugin: str,
        params: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        source_ip: str | None = None,
        **metadata: Any,
    ) -> str:
        """Log a capability request.

        Args:
            capability: Capability name
            plugin: Plugin name
            params: Request parameters
            correlation_id: Correlation ID (generated if not provided)
            session_id: Session ID
            user_id: User ID
            source_ip: Client IP
            **metadata: Additional metadata

        Returns:
            Correlation ID for the request
        """
        entry = AuditEntry(
            event_type=AuditEventType.CAPABILITY_REQUEST,
            correlation_id=correlation_id or str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            capability=capability,
            plugin=plugin,
            params=params if self.config.include_params else None,
            source_ip=source_ip,
            metadata=metadata,
        )
        self._write_entry(entry)
        return entry.correlation_id

    def log_policy_decision(
        self,
        capability: str,
        plugin: str,
        action: str,
        allowed: bool,
        reason: str,
        risk_tier: str | None = None,
        correlation_id: str | None = None,
        matched_rules: list[str] | None = None,
        **metadata: Any,
    ) -> None:
        """Log a policy decision.

        Args:
            capability: Capability name
            plugin: Plugin name
            action: Policy action (allow, deny, audit, confirm)
            allowed: Whether action was allowed
            reason: Explanation for the decision
            risk_tier: Risk level
            correlation_id: Request correlation ID
            matched_rules: List of rules that matched
            **metadata: Additional metadata
        """
        event_type = (
            AuditEventType.CAPABILITY_ALLOWED
            if allowed
            else AuditEventType.CAPABILITY_DENIED
        )

        entry = AuditEntry(
            event_type=event_type,
            correlation_id=correlation_id or str(uuid.uuid4()),
            capability=capability,
            plugin=plugin,
            action=action,
            allowed=allowed,
            reason=reason,
            risk_tier=risk_tier,
            metadata={"matched_rules": matched_rules or [], **metadata},
        )
        self._write_entry(entry)

    def log_capability_result(
        self,
        capability: str,
        plugin: str,
        success: bool,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: float | None = None,
        correlation_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Log a capability execution result.

        Args:
            capability: Capability name
            plugin: Plugin name
            success: Whether execution succeeded
            result: Execution result
            error: Error message if failed
            duration_ms: Execution duration
            correlation_id: Request correlation ID
            **metadata: Additional metadata
        """
        event_type = (
            AuditEventType.CAPABILITY_EXECUTED
            if success
            else AuditEventType.CAPABILITY_FAILED
        )

        entry = AuditEntry(
            event_type=event_type,
            correlation_id=correlation_id or str(uuid.uuid4()),
            capability=capability,
            plugin=plugin,
            allowed=success,
            result=result if self.config.include_results and success else None,
            reason=error if not success else None,
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self._write_entry(entry)

    def log_policy_violation(
        self,
        capability: str,
        plugin: str,
        violation_type: str,
        details: str,
        params: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Log a policy violation.

        Args:
            capability: Capability name
            plugin: Plugin name
            violation_type: Type of violation
            details: Violation details
            params: Violating parameters
            correlation_id: Request correlation ID
            **metadata: Additional metadata
        """
        entry = AuditEntry(
            event_type=AuditEventType.POLICY_VIOLATION,
            correlation_id=correlation_id or str(uuid.uuid4()),
            capability=capability,
            plugin=plugin,
            allowed=False,
            reason=f"{violation_type}: {details}",
            params=params if self.config.include_params else None,
            metadata=metadata,
        )
        self._write_entry(entry)

    def log_auth_event(
        self,
        event_type: AuditEventType,
        user_id: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
        **metadata: Any,
    ) -> None:
        """Log an authentication event.

        Args:
            event_type: AUTH_SUCCESS, AUTH_FAILURE, or AUTH_REVOKED
            user_id: User/API key identifier
            source_ip: Client IP
            user_agent: Client user agent
            reason: Reason for failure/revocation
            **metadata: Additional metadata
        """
        entry = AuditEntry(
            event_type=event_type,
            user_id=user_id,
            source_ip=source_ip,
            user_agent=user_agent,
            reason=reason,
            allowed=event_type == AuditEventType.AUTH_SUCCESS,
            metadata=metadata,
        )
        self._write_entry(entry)

    def log_system_event(
        self,
        event_type: AuditEventType,
        details: str | None = None,
        **metadata: Any,
    ) -> None:
        """Log a system event.

        Args:
            event_type: SYSTEM_START, SYSTEM_SHUTDOWN, or CONFIG_CHANGE
            details: Event details
            **metadata: Additional metadata
        """
        entry = AuditEntry(
            event_type=event_type,
            reason=details,
            metadata=metadata,
        )
        self._write_entry(entry)

    def log_plugin_event(
        self,
        event_type: AuditEventType,
        plugin: str,
        details: str | None = None,
        **metadata: Any,
    ) -> None:
        """Log a plugin event.

        Args:
            event_type: PLUGIN_LOADED, PLUGIN_UNLOADED, or PLUGIN_ERROR
            plugin: Plugin name
            details: Event details
            **metadata: Additional metadata
        """
        entry = AuditEntry(
            event_type=event_type,
            plugin=plugin,
            reason=details,
            metadata=metadata,
        )
        self._write_entry(entry)

    def log_data_event(
        self,
        event_type: AuditEventType,
        capability: str | None = None,
        details: str | None = None,
        correlation_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Log a data access/export event.

        Args:
            event_type: DATA_ACCESS, DATA_EXPORT, or SENSITIVE_DATA_DETECTED
            capability: Related capability
            details: Event details
            correlation_id: Request correlation ID
            **metadata: Additional metadata
        """
        entry_kwargs: dict[str, Any] = {
            "event_type": event_type,
            "capability": capability,
            "reason": details,
            "metadata": metadata,
        }
        if correlation_id is not None:
            entry_kwargs["correlation_id"] = correlation_id
        entry = AuditEntry(**entry_kwargs)
        self._write_entry(entry)

    def log_raw(self, entry: AuditEntry) -> None:
        """Log a raw audit entry.

        Args:
            entry: The audit entry to log
        """
        self._write_entry(entry)


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger(config: AuditLogConfig | None = None) -> AuditLogger:
    """Get the global audit logger instance.

    Args:
        config: Optional config (creates new instance if provided)

    Returns:
        AuditLogger instance
    """
    global _audit_logger

    if config is not None:
        if _audit_logger:
            _audit_logger.close()
        _audit_logger = AuditLogger(config)
        return _audit_logger

    if _audit_logger is None:
        _audit_logger = AuditLogger()

    return _audit_logger


def audit_log(
    event_type: AuditEventType,
    **kwargs: Any,
) -> None:
    """Convenience function to log an audit event.

    Args:
        event_type: Type of event
        **kwargs: Event-specific parameters
    """
    audit_logger = get_audit_logger()

    if event_type in (
        AuditEventType.CAPABILITY_REQUEST,
        AuditEventType.CAPABILITY_ALLOWED,
        AuditEventType.CAPABILITY_DENIED,
        AuditEventType.CAPABILITY_EXECUTED,
        AuditEventType.CAPABILITY_FAILED,
    ):
        entry = AuditEntry(event_type=event_type, **kwargs)
        audit_logger.log_raw(entry)
    elif event_type == AuditEventType.POLICY_VIOLATION:
        audit_logger.log_policy_violation(**kwargs)
    elif event_type in (
        AuditEventType.AUTH_SUCCESS,
        AuditEventType.AUTH_FAILURE,
        AuditEventType.AUTH_REVOKED,
    ):
        audit_logger.log_auth_event(event_type, **kwargs)
    elif event_type in (
        AuditEventType.SYSTEM_START,
        AuditEventType.SYSTEM_SHUTDOWN,
        AuditEventType.CONFIG_CHANGE,
    ):
        audit_logger.log_system_event(event_type, **kwargs)
    elif event_type in (
        AuditEventType.PLUGIN_LOADED,
        AuditEventType.PLUGIN_UNLOADED,
        AuditEventType.PLUGIN_ERROR,
    ):
        audit_logger.log_plugin_event(event_type, **kwargs)
    else:
        entry = AuditEntry(event_type=event_type, **kwargs)
        audit_logger.log_raw(entry)


# Exports
__all__ = [
    "AuditEventType",
    "AuditEntry",
    "AuditLogConfig",
    "AuditLogger",
    "get_audit_logger",
    "audit_log",
]
