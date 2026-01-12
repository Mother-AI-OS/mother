"""Condition evaluators for policy engine.

This module provides functions to evaluate various policy conditions
including filesystem access, command execution, network requests, and data.
"""

from __future__ import annotations

import fnmatch
import ipaddress
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import (
    CommandCondition,
    DataClassification,
    DataCondition,
    FilesystemCondition,
    NetworkCondition,
    PolicyDecision,
    RiskTier,
)


def evaluate_filesystem_condition(
    condition: FilesystemCondition,
    path: str,
    operation: str = "read",
) -> PolicyDecision:
    """Evaluate filesystem access against policy conditions.

    Args:
        condition: Filesystem policy conditions
        path: The path being accessed
        operation: The operation type (read, write, delete, list)

    Returns:
        PolicyDecision indicating whether access is allowed
    """
    # Normalize the path
    try:
        normalized_path = str(Path(path).resolve())
    except (OSError, ValueError) as e:
        return PolicyDecision.deny(
            reason=f"Invalid path: {e}",
            risk_tier=RiskTier.HIGH,
        )

    # Check for symlinks if not allowed
    if not condition.allow_symlinks:
        try:
            if Path(path).is_symlink():
                return PolicyDecision.deny(
                    reason="Symbolic links are not allowed by policy",
                    risk_tier=RiskTier.MEDIUM,
                )
        except OSError:
            pass  # Path doesn't exist yet, which is fine for write ops

    # Check denied paths first (explicit deny takes precedence)
    for pattern in condition.denied_paths:
        if fnmatch.fnmatch(normalized_path, pattern) or fnmatch.fnmatch(path, pattern):
            return PolicyDecision.deny(
                reason=f"Path matches denied pattern: {pattern}",
                matched_rules=[f"denied_path:{pattern}"],
                risk_tier=RiskTier.HIGH,
            )

    # Check read-only paths for write operations
    if operation in ("write", "delete", "create", "modify"):
        for pattern in condition.read_only_paths:
            if fnmatch.fnmatch(normalized_path, pattern) or fnmatch.fnmatch(path, pattern):
                return PolicyDecision.deny(
                    reason=f"Path is read-only: {pattern}",
                    matched_rules=[f"read_only:{pattern}"],
                    risk_tier=RiskTier.MEDIUM,
                )

    # Check allowed paths (if specified, acts as allowlist)
    if condition.allowed_paths:
        allowed = False
        matched_pattern = None
        for pattern in condition.allowed_paths:
            if fnmatch.fnmatch(normalized_path, pattern) or fnmatch.fnmatch(path, pattern):
                allowed = True
                matched_pattern = pattern
                break

        if not allowed:
            return PolicyDecision.deny(
                reason="Path not in allowed paths list",
                risk_tier=RiskTier.MEDIUM,
            )

        return PolicyDecision.allow(
            reason=f"Path allowed by pattern: {matched_pattern}",
            matched_rules=[f"allowed_path:{matched_pattern}"],
            risk_tier=RiskTier.LOW,
        )

    # Default: allow if no explicit rules matched
    return PolicyDecision.allow(
        reason="Path not explicitly denied",
        risk_tier=RiskTier.LOW,
    )


def evaluate_command_condition(
    condition: CommandCondition,
    command: str,
    cwd: str | None = None,
) -> PolicyDecision:
    """Evaluate shell command against policy conditions.

    Args:
        condition: Command policy conditions
        command: The command to be executed
        cwd: Working directory for the command

    Returns:
        PolicyDecision indicating whether execution is allowed
    """
    # Check literal dangerous patterns first
    for pattern in condition.denied_patterns:
        if pattern in command:
            return PolicyDecision.deny(
                reason=f"Command contains dangerous pattern: {pattern}",
                matched_rules=[f"denied_pattern:{pattern}"],
                risk_tier=RiskTier.CRITICAL,
            )

    # Check regex denied patterns
    for pattern in condition.denied_commands:
        try:
            if re.search(pattern, command):
                return PolicyDecision.deny(
                    reason=f"Command matches denied pattern: {pattern}",
                    matched_rules=[f"denied_command:{pattern}"],
                    risk_tier=RiskTier.HIGH,
                )
        except re.error:
            continue

    # Check for pipes if not allowed
    if not condition.allow_pipes and "|" in command:
        return PolicyDecision.deny(
            reason="Piped commands are not allowed by policy",
            risk_tier=RiskTier.MEDIUM,
        )

    # Check for redirects if not allowed
    if not condition.allow_redirects and any(c in command for c in [">", ">>", "<"]):
        return PolicyDecision.deny(
            reason="Command redirects are not allowed by policy",
            risk_tier=RiskTier.MEDIUM,
        )

    # Check working directory if specified
    if cwd and condition.allowed_cwd:
        try:
            cwd_path = Path(cwd).resolve()
            allowed = False
            for allowed_cwd in condition.allowed_cwd:
                allowed_path = Path(allowed_cwd).resolve()
                if cwd_path == allowed_path or allowed_path in cwd_path.parents:
                    allowed = True
                    break
            if not allowed:
                return PolicyDecision.deny(
                    reason=f"Working directory not allowed: {cwd}",
                    risk_tier=RiskTier.MEDIUM,
                )
        except (OSError, ValueError):
            return PolicyDecision.deny(
                reason=f"Invalid working directory: {cwd}",
                risk_tier=RiskTier.MEDIUM,
            )

    # Check allowed commands if specified (allowlist mode)
    if condition.allowed_commands:
        # Extract base command
        cmd_parts = command.split()
        base_cmd = cmd_parts[0] if cmd_parts else ""

        allowed = False
        matched_pattern = None
        for pattern in condition.allowed_commands:
            try:
                if re.match(pattern, base_cmd) or re.match(pattern, command):
                    allowed = True
                    matched_pattern = pattern
                    break
            except re.error:
                continue

        if not allowed:
            return PolicyDecision.deny(
                reason="Command not in allowed list",
                risk_tier=RiskTier.MEDIUM,
            )

        return PolicyDecision.allow(
            reason=f"Command allowed by pattern: {matched_pattern}",
            matched_rules=[f"allowed_command:{matched_pattern}"],
            risk_tier=RiskTier.MEDIUM,  # Shell commands are inherently risky
        )

    # Default: allow but flag as medium risk
    return PolicyDecision.allow(
        reason="Command not explicitly denied",
        risk_tier=RiskTier.MEDIUM,
    )


def evaluate_network_condition(
    condition: NetworkCondition,
    url: str | None = None,
    host: str | None = None,
    port: int | None = None,
    ip: str | None = None,
) -> PolicyDecision:
    """Evaluate network access against policy conditions.

    Args:
        condition: Network policy conditions
        url: The URL being accessed (optional)
        host: The hostname (extracted from URL if not provided)
        port: The port (extracted from URL if not provided)
        ip: The IP address (optional, for direct IP access)

    Returns:
        PolicyDecision indicating whether access is allowed
    """
    # Parse URL if provided
    if url:
        try:
            parsed = urlparse(url)
            host = host or parsed.hostname
            port = port or parsed.port or (443 if parsed.scheme == "https" else 80)
        except Exception as e:
            return PolicyDecision.deny(
                reason=f"Invalid URL: {e}",
                risk_tier=RiskTier.MEDIUM,
            )

    if not host and not ip:
        return PolicyDecision.deny(
            reason="No host or IP specified for network access",
            risk_tier=RiskTier.MEDIUM,
        )

    # Check denied domains
    if host:
        for pattern in condition.denied_domains:
            if _match_domain(host, pattern):
                return PolicyDecision.deny(
                    reason=f"Domain matches denied pattern: {pattern}",
                    matched_rules=[f"denied_domain:{pattern}"],
                    risk_tier=RiskTier.HIGH,
                )

    # Check denied ports
    if port and port in condition.denied_ports:
        return PolicyDecision.deny(
            reason=f"Port {port} is blocked by policy",
            matched_rules=[f"denied_port:{port}"],
            risk_tier=RiskTier.HIGH,
        )

    # Check allowed ports if specified
    if port and condition.allowed_ports and port not in condition.allowed_ports:
        return PolicyDecision.deny(
            reason=f"Port {port} is not in allowed ports list",
            risk_tier=RiskTier.MEDIUM,
        )

    # Check private IP ranges
    target_ip = ip
    if not target_ip and host:
        # Check if host is an IP address
        try:
            target_ip = str(ipaddress.ip_address(host))
        except ValueError:
            pass  # Not an IP, that's fine

    if target_ip and condition.block_private_ranges:
        try:
            ip_obj = ipaddress.ip_address(target_ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                return PolicyDecision.deny(
                    reason=f"Private/local IP addresses are blocked: {target_ip}",
                    risk_tier=RiskTier.HIGH,
                )
        except ValueError:
            pass

    # Check denied IPs/CIDRs
    if target_ip:
        for denied in condition.denied_ips:
            if _ip_in_range(target_ip, denied):
                return PolicyDecision.deny(
                    reason=f"IP matches denied range: {denied}",
                    matched_rules=[f"denied_ip:{denied}"],
                    risk_tier=RiskTier.HIGH,
                )

    # Check allowed domains if specified (allowlist mode)
    if host and condition.allowed_domains:
        allowed = False
        matched_pattern = None
        for pattern in condition.allowed_domains:
            if _match_domain(host, pattern):
                allowed = True
                matched_pattern = pattern
                break

        if not allowed:
            return PolicyDecision.deny(
                reason="Domain not in allowed list",
                risk_tier=RiskTier.MEDIUM,
            )

        return PolicyDecision.allow(
            reason=f"Domain allowed by pattern: {matched_pattern}",
            matched_rules=[f"allowed_domain:{matched_pattern}"],
            risk_tier=RiskTier.LOW,
        )

    # Check allowed IPs if specified
    if target_ip and condition.allowed_ips:
        allowed = False
        matched_range = None
        for allowed_range in condition.allowed_ips:
            if _ip_in_range(target_ip, allowed_range):
                allowed = True
                matched_range = allowed_range
                break

        if not allowed:
            return PolicyDecision.deny(
                reason="IP not in allowed list",
                risk_tier=RiskTier.MEDIUM,
            )

        return PolicyDecision.allow(
            reason=f"IP allowed by range: {matched_range}",
            matched_rules=[f"allowed_ip:{matched_range}"],
            risk_tier=RiskTier.LOW,
        )

    # Default: allow
    return PolicyDecision.allow(
        reason="Network access not explicitly denied",
        risk_tier=RiskTier.LOW,
    )


def evaluate_data_condition(
    condition: DataCondition,
    data: str | bytes | dict[str, Any],
    classification: DataClassification = DataClassification.INTERNAL,
    destination: str | None = None,
) -> PolicyDecision:
    """Evaluate data against classification and exfiltration policies.

    Args:
        condition: Data policy conditions
        data: The data being processed/transmitted
        classification: Classification level of the data
        destination: Where the data is being sent (URL or domain)

    Returns:
        PolicyDecision indicating whether the operation is allowed
    """
    # Convert data to string for pattern matching
    if isinstance(data, bytes):
        try:
            data_str = data.decode("utf-8", errors="replace")
        except Exception:
            data_str = str(data)
    elif isinstance(data, dict):
        import json

        data_str = json.dumps(data, default=str)
    else:
        data_str = str(data)

    # Check for sensitive patterns
    sensitive_matches = []
    for pattern in condition.sensitive_patterns:
        try:
            if re.search(pattern, data_str):
                sensitive_matches.append(pattern)
        except re.error:
            continue

    # If exfiltration blocking is enabled and we found sensitive data
    if condition.block_exfiltration and sensitive_matches and destination:
        # Check if destination is allowed for export
        if destination and condition.allowed_export_domains:
            try:
                parsed = urlparse(destination)
                host = parsed.hostname or destination
                allowed = any(_match_domain(host, d) for d in condition.allowed_export_domains)
                if not allowed:
                    return PolicyDecision.deny(
                        reason=f"Sensitive data detected, export to {host} not allowed",
                        matched_rules=[f"sensitive_pattern:{p}" for p in sensitive_matches[:3]],
                        risk_tier=RiskTier.CRITICAL,
                    )
            except Exception:
                return PolicyDecision.deny(
                    reason="Sensitive data detected, destination validation failed",
                    risk_tier=RiskTier.CRITICAL,
                )
        elif destination:
            return PolicyDecision.deny(
                reason=f"Sensitive data detected, no allowed export domains configured",
                matched_rules=[f"sensitive_pattern:{p}" for p in sensitive_matches[:3]],
                risk_tier=RiskTier.CRITICAL,
            )

    # Check classification level
    classification_order = [
        DataClassification.PUBLIC,
        DataClassification.INTERNAL,
        DataClassification.CONFIDENTIAL,
        DataClassification.RESTRICTED,
    ]

    if classification_order.index(classification) > classification_order.index(condition.max_classification):
        return PolicyDecision.deny(
            reason=f"Data classification {classification.value} exceeds maximum allowed {condition.max_classification.value}",
            risk_tier=RiskTier.HIGH,
        )

    # Determine risk tier based on findings
    if sensitive_matches:
        return PolicyDecision.allow(
            reason="Data allowed but contains sensitive patterns",
            matched_rules=[f"sensitive_pattern:{p}" for p in sensitive_matches[:3]],
            risk_tier=RiskTier.MEDIUM,
        )

    return PolicyDecision.allow(
        reason="Data passed classification check",
        risk_tier=RiskTier.LOW,
    )


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _match_domain(host: str, pattern: str) -> bool:
    """Match a hostname against a domain pattern.

    Supports:
    - Exact match: "example.com"
    - Wildcard subdomain: "*.example.com"
    - Any subdomain: ".example.com" (matches example.com and *.example.com)
    """
    host = host.lower().strip()
    pattern = pattern.lower().strip()

    # Exact match
    if host == pattern:
        return True

    # Wildcard match
    if pattern.startswith("*."):
        base = pattern[2:]
        return host == base or host.endswith("." + base)

    # Suffix match (starts with .)
    if pattern.startswith("."):
        return host == pattern[1:] or host.endswith(pattern)

    return False


def _ip_in_range(ip: str, cidr_or_ip: str) -> bool:
    """Check if an IP address is in a CIDR range or matches exactly."""
    try:
        ip_obj = ipaddress.ip_address(ip)

        # Check if it's a CIDR range
        if "/" in cidr_or_ip:
            network = ipaddress.ip_network(cidr_or_ip, strict=False)
            return ip_obj in network
        else:
            # Exact match
            return ip_obj == ipaddress.ip_address(cidr_or_ip)
    except ValueError:
        return False


# Export functions
__all__ = [
    "evaluate_filesystem_condition",
    "evaluate_command_condition",
    "evaluate_network_condition",
    "evaluate_data_condition",
]
