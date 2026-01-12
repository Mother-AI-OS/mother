"""Edition-based feature configuration for Mother AI OS.

Defines the feature matrix for Community, Professional, and Enterprise editions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Edition(str, Enum):
    """Available editions of Mother AI OS."""

    COMMUNITY = "community"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class EditionFeatures:
    """Features available in an edition."""

    # Core features (all editions)
    core_plugin_system: bool = True
    multi_llm_support: bool = True
    safe_mode: bool = True
    schema_validation: bool = True

    # Policy features
    policy_engine: str = "basic"  # "basic", "advanced"
    custom_policy_rules: bool = False

    # Audit features
    audit_logging: bool = True
    audit_retention_days: int = 7  # -1 for unlimited
    pii_redaction: str = "basic"  # "basic", "extended", "custom"

    # Sandbox features
    sandbox_isolation: str = "basic"  # "basic", "advanced"
    high_risk_plugin_control: bool = True

    # Enterprise features
    ldap_sso_integration: bool = False
    dedicated_support: bool = False
    sla_percentage: float | None = None

    # Custom patterns for PII redaction (Enterprise only)
    custom_pii_patterns: list[str] = field(default_factory=list)


# Edition feature configurations
EDITION_FEATURES: dict[Edition, EditionFeatures] = {
    Edition.COMMUNITY: EditionFeatures(
        policy_engine="basic",
        custom_policy_rules=False,
        audit_retention_days=7,
        pii_redaction="basic",
        sandbox_isolation="basic",
        ldap_sso_integration=False,
        dedicated_support=False,
        sla_percentage=None,
    ),
    Edition.PROFESSIONAL: EditionFeatures(
        policy_engine="advanced",
        custom_policy_rules=True,
        audit_retention_days=30,
        pii_redaction="extended",
        sandbox_isolation="advanced",
        ldap_sso_integration=True,
        dedicated_support=False,
        sla_percentage=99.5,
    ),
    Edition.ENTERPRISE: EditionFeatures(
        policy_engine="advanced",
        custom_policy_rules=True,
        audit_retention_days=-1,  # Unlimited
        pii_redaction="custom",
        sandbox_isolation="advanced",
        ldap_sso_integration=True,
        dedicated_support=True,
        sla_percentage=99.9,
    ),
}


class EditionManager:
    """Manages edition-based feature access."""

    def __init__(self, edition: Edition = Edition.COMMUNITY):
        """Initialize with an edition.

        Args:
            edition: The edition to use
        """
        self._edition = edition
        self._features = EDITION_FEATURES[edition]
        self._custom_pii_patterns: list[str] = []

    @property
    def edition(self) -> Edition:
        """Get the current edition."""
        return self._edition

    @property
    def features(self) -> EditionFeatures:
        """Get the features for the current edition."""
        return self._features

    def is_feature_available(self, feature: str) -> bool:
        """Check if a feature is available in the current edition.

        Args:
            feature: Feature name to check

        Returns:
            True if the feature is available
        """
        if not hasattr(self._features, feature):
            return False
        value = getattr(self._features, feature)
        if isinstance(value, bool):
            return value
        return value is not None

    def get_audit_retention_days(self) -> int:
        """Get audit log retention days (-1 for unlimited)."""
        return self._features.audit_retention_days

    def get_pii_redaction_level(self) -> str:
        """Get the PII redaction level."""
        return self._features.pii_redaction

    def has_advanced_policy_engine(self) -> bool:
        """Check if advanced policy engine is available."""
        return self._features.policy_engine == "advanced"

    def has_ldap_sso(self) -> bool:
        """Check if LDAP/SSO integration is available."""
        return self._features.ldap_sso_integration

    def has_custom_policy_rules(self) -> bool:
        """Check if custom policy rules are available."""
        return self._features.custom_policy_rules

    def has_advanced_sandbox(self) -> bool:
        """Check if advanced sandbox features are available."""
        return self._features.sandbox_isolation == "advanced"

    def set_custom_pii_patterns(self, patterns: list[str]) -> None:
        """Set custom PII patterns (Enterprise only).

        Args:
            patterns: List of regex patterns for custom PII detection

        Raises:
            PermissionError: If not Enterprise edition
        """
        if self._edition != Edition.ENTERPRISE:
            raise PermissionError("Custom PII patterns require Enterprise edition")
        self._custom_pii_patterns = patterns

    def get_custom_pii_patterns(self) -> list[str]:
        """Get custom PII patterns."""
        return self._custom_pii_patterns

    def to_dict(self) -> dict[str, Any]:
        """Convert edition info to dictionary.

        Returns:
            Dict with edition name and features
        """
        return {
            "edition": self._edition.value,
            "features": {
                "policy_engine": self._features.policy_engine,
                "custom_policy_rules": self._features.custom_policy_rules,
                "audit_retention_days": self._features.audit_retention_days,
                "pii_redaction": self._features.pii_redaction,
                "sandbox_isolation": self._features.sandbox_isolation,
                "ldap_sso_integration": self._features.ldap_sso_integration,
                "dedicated_support": self._features.dedicated_support,
                "sla_percentage": self._features.sla_percentage,
            },
        }


# Global edition manager instance
_edition_manager: EditionManager | None = None


def get_edition_manager() -> EditionManager:
    """Get the global edition manager.

    Returns:
        The global EditionManager instance
    """
    global _edition_manager
    if _edition_manager is None:
        _edition_manager = EditionManager()
    return _edition_manager


def set_edition(edition: Edition | str) -> EditionManager:
    """Set the global edition.

    Args:
        edition: Edition to set (enum or string)

    Returns:
        The updated EditionManager instance
    """
    global _edition_manager
    if isinstance(edition, str):
        edition = Edition(edition)
    _edition_manager = EditionManager(edition)
    return _edition_manager


def get_edition() -> Edition:
    """Get the current edition.

    Returns:
        The current Edition
    """
    return get_edition_manager().edition
