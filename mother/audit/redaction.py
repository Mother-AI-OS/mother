"""Sensitive data redaction for audit logging.

This module provides utilities for detecting and redacting sensitive data
including PII, API keys, credentials, and other confidential information.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SensitiveDataType(str, Enum):
    """Types of sensitive data that can be detected."""

    API_KEY = "api_key"
    PASSWORD = "password"
    AUTH_TOKEN = "auth_token"
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    AWS_KEY = "aws_key"
    PRIVATE_KEY = "private_key"
    JWT = "jwt"
    GENERIC_SECRET = "generic_secret"


@dataclass
class RedactionPattern:
    """A pattern for detecting and redacting sensitive data."""

    data_type: SensitiveDataType
    pattern: re.Pattern
    replacement: str = "[REDACTED]"
    description: str = ""


# Pre-compiled patterns for sensitive data detection
_REDACTION_PATTERNS: list[RedactionPattern] = [
    # API Keys
    RedactionPattern(
        SensitiveDataType.API_KEY,
        re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
        "[REDACTED:OPENAI_KEY]",
        "OpenAI API key",
    ),
    RedactionPattern(
        SensitiveDataType.API_KEY,
        re.compile(r"sk-ant-[a-zA-Z0-9\-_]{20,}", re.IGNORECASE),
        "[REDACTED:ANTHROPIC_KEY]",
        "Anthropic API key",
    ),
    RedactionPattern(
        SensitiveDataType.API_KEY,
        re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
        "[REDACTED:GITHUB_PAT]",
        "GitHub Personal Access Token",
    ),
    RedactionPattern(
        SensitiveDataType.API_KEY,
        re.compile(r"gho_[a-zA-Z0-9]{36}", re.IGNORECASE),
        "[REDACTED:GITHUB_OAUTH]",
        "GitHub OAuth token",
    ),
    RedactionPattern(
        SensitiveDataType.API_KEY,
        re.compile(r"xox[baprs]-[a-zA-Z0-9\-]{10,}", re.IGNORECASE),
        "[REDACTED:SLACK_TOKEN]",
        "Slack token",
    ),
    # AWS Keys
    RedactionPattern(
        SensitiveDataType.AWS_KEY,
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "[REDACTED:AWS_ACCESS_KEY]",
        "AWS Access Key ID",
    ),
    RedactionPattern(
        SensitiveDataType.AWS_KEY,
        re.compile(r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"),
        "[REDACTED:AWS_SECRET_KEY]",
        "AWS Secret Access Key (40-char base64)",
    ),
    # Auth tokens
    RedactionPattern(
        SensitiveDataType.AUTH_TOKEN,
        re.compile(r"[Bb]earer\s+[a-zA-Z0-9\-_\.]+"),
        "[REDACTED:BEARER_TOKEN]",
        "Bearer token",
    ),
    RedactionPattern(
        SensitiveDataType.AUTH_TOKEN,
        re.compile(r"[Aa]uthorization:\s*[Bb]asic\s+[a-zA-Z0-9=+/]+"),
        "[REDACTED:BASIC_AUTH]",
        "Basic auth header",
    ),
    # JWT tokens
    RedactionPattern(
        SensitiveDataType.JWT,
        re.compile(r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"),
        "[REDACTED:JWT]",
        "JSON Web Token",
    ),
    # Passwords
    RedactionPattern(
        SensitiveDataType.PASSWORD,
        re.compile(r"(?i)password[\"']?\s*[:=]\s*[\"']?[^\s\"',}]{3,}"),
        "password=[REDACTED]",
        "Password field",
    ),
    RedactionPattern(
        SensitiveDataType.PASSWORD,
        re.compile(r"(?i)passwd[\"']?\s*[:=]\s*[\"']?[^\s\"',}]{3,}"),
        "passwd=[REDACTED]",
        "Passwd field",
    ),
    RedactionPattern(
        SensitiveDataType.PASSWORD,
        re.compile(r"(?i)secret[_-]?key[\"']?\s*[:=]\s*[\"']?[^\s\"',}]{3,}"),
        "secret_key=[REDACTED]",
        "Secret key field",
    ),
    # PII - Email addresses
    RedactionPattern(
        SensitiveDataType.EMAIL,
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "[REDACTED:EMAIL]",
        "Email address",
    ),
    # PII - SSN (US Social Security Number) - before phone to avoid overlap
    RedactionPattern(
        SensitiveDataType.SSN,
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED:SSN]",
        "US Social Security Number",
    ),
    # PII - Credit card numbers - before phone to avoid overlap
    RedactionPattern(
        SensitiveDataType.CREDIT_CARD,
        re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "[REDACTED:CREDIT_CARD]",
        "Credit card number",
    ),
    # PII - Phone numbers (various formats) - after credit card and SSN
    RedactionPattern(
        SensitiveDataType.PHONE,
        re.compile(r"\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"),
        "[REDACTED:PHONE]",
        "Phone number",
    ),
    # Private keys
    RedactionPattern(
        SensitiveDataType.PRIVATE_KEY,
        re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----.*?-----END (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----", re.DOTALL),
        "[REDACTED:PRIVATE_KEY]",
        "Private key block",
    ),
    # Generic secrets (catch-all for key=value patterns with sensitive names)
    RedactionPattern(
        SensitiveDataType.GENERIC_SECRET,
        re.compile(r"(?i)(api[_-]?key|access[_-]?token|client[_-]?secret|private[_-]?key)[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9\-_/+=]{8,}"),
        r"\1=[REDACTED]",
        "Generic secret pattern",
    ),
]


@dataclass
class RedactionConfig:
    """Configuration for the redaction engine."""

    # Which data types to redact
    redact_types: set[SensitiveDataType] = field(
        default_factory=lambda: set(SensitiveDataType)
    )

    # Additional custom patterns
    custom_patterns: list[RedactionPattern] = field(default_factory=list)

    # Whether to redact in keys as well as values
    redact_keys: bool = True

    # Preserve partial data for debugging (e.g., show last 4 chars)
    preserve_suffix_length: int = 0

    # Maximum depth for nested structure redaction
    max_depth: int = 10


class Redactor:
    """Engine for redacting sensitive data from text and structured data."""

    def __init__(self, config: RedactionConfig | None = None):
        """Initialize the redactor.

        Args:
            config: Redaction configuration
        """
        self.config = config or RedactionConfig()
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> list[RedactionPattern]:
        """Build the list of active patterns based on config."""
        patterns = []

        for pattern in _REDACTION_PATTERNS:
            if pattern.data_type in self.config.redact_types:
                patterns.append(pattern)

        patterns.extend(self.config.custom_patterns)
        return patterns

    def redact_string(self, text: str) -> str:
        """Redact sensitive data from a string.

        Args:
            text: The string to redact

        Returns:
            String with sensitive data replaced
        """
        if not text or not isinstance(text, str):
            return text

        result = text
        for pattern in self._patterns:
            if self.config.preserve_suffix_length > 0:
                # Custom replacement that preserves suffix
                def replace_preserve_suffix(match: re.Match) -> str:
                    value = match.group(0)
                    suffix = value[-self.config.preserve_suffix_length :]
                    return f"{pattern.replacement[:-1]}...{suffix}]"

                result = pattern.pattern.sub(replace_preserve_suffix, result)
            else:
                result = pattern.pattern.sub(pattern.replacement, result)

        return result

    def redact_value(self, value: Any, depth: int = 0) -> Any:
        """Recursively redact sensitive data from any value.

        Args:
            value: The value to redact (string, dict, list, etc.)
            depth: Current recursion depth

        Returns:
            Value with sensitive data redacted
        """
        if depth > self.config.max_depth:
            return "[MAX_DEPTH_EXCEEDED]"

        if value is None:
            return None

        if isinstance(value, str):
            return self.redact_string(value)

        if isinstance(value, dict):
            return self._redact_dict(value, depth)

        if isinstance(value, (list, tuple)):
            return type(value)(self.redact_value(item, depth + 1) for item in value)

        if isinstance(value, (int, float, bool)):
            return value

        # For other types, convert to string and redact
        return self.redact_string(str(value))

    def _redact_dict(self, data: dict, depth: int) -> dict:
        """Redact sensitive data from a dictionary.

        Args:
            data: Dictionary to redact
            depth: Current recursion depth

        Returns:
            Dictionary with sensitive data redacted
        """
        result = {}

        for key, value in data.items():
            # Optionally redact the key
            new_key = self.redact_string(str(key)) if self.config.redact_keys else key

            # Check if key indicates sensitive data
            key_lower = str(key).lower()
            sensitive_key_patterns = [
                "password",
                "passwd",
                "secret",
                "token",
                "api_key",
                "apikey",
                "auth",
                "credential",
                "private_key",
                "access_key",
                "client_secret",
            ]

            if any(pattern in key_lower for pattern in sensitive_key_patterns):
                # Completely redact value for sensitive keys
                if isinstance(value, str) and len(value) > 0:
                    result[new_key] = "[REDACTED]"
                else:
                    result[new_key] = self.redact_value(value, depth + 1)
            else:
                result[new_key] = self.redact_value(value, depth + 1)

        return result


# Global redactor instance
_default_redactor: Redactor | None = None


def get_redactor(config: RedactionConfig | None = None) -> Redactor:
    """Get the global redactor instance.

    Args:
        config: Optional config to use (creates new instance if provided)

    Returns:
        Redactor instance
    """
    global _default_redactor

    if config is not None:
        return Redactor(config)

    if _default_redactor is None:
        _default_redactor = Redactor()

    return _default_redactor


def redact(value: Any) -> Any:
    """Convenience function to redact sensitive data.

    Args:
        value: Value to redact

    Returns:
        Redacted value
    """
    return get_redactor().redact_value(value)


def redact_string(text: str) -> str:
    """Convenience function to redact a string.

    Args:
        text: String to redact

    Returns:
        Redacted string
    """
    return get_redactor().redact_string(text)


# Exports
__all__ = [
    "SensitiveDataType",
    "RedactionPattern",
    "RedactionConfig",
    "Redactor",
    "get_redactor",
    "redact",
    "redact_string",
]
