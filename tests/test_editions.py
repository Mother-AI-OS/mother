"""Tests for edition-based feature configuration."""

import pytest

from mother.config.editions import (
    EDITION_FEATURES,
    Edition,
    EditionFeatures,
    EditionManager,
    get_edition,
    get_edition_manager,
    set_edition,
)


class TestEdition:
    """Tests for Edition enum."""

    def test_editions_exist(self) -> None:
        """Test all editions are defined."""
        assert Edition.COMMUNITY == "community"
        assert Edition.PROFESSIONAL == "professional"
        assert Edition.ENTERPRISE == "enterprise"

    def test_edition_from_string(self) -> None:
        """Test creating edition from string."""
        assert Edition("community") == Edition.COMMUNITY
        assert Edition("professional") == Edition.PROFESSIONAL
        assert Edition("enterprise") == Edition.ENTERPRISE


class TestEditionFeatures:
    """Tests for EditionFeatures dataclass."""

    def test_default_features(self) -> None:
        """Test default feature values."""
        features = EditionFeatures()
        assert features.core_plugin_system is True
        assert features.multi_llm_support is True
        assert features.safe_mode is True
        assert features.schema_validation is True
        assert features.policy_engine == "basic"
        assert features.audit_retention_days == 7

    def test_custom_features(self) -> None:
        """Test custom feature values."""
        features = EditionFeatures(
            policy_engine="advanced",
            audit_retention_days=30,
            ldap_sso_integration=True,
        )
        assert features.policy_engine == "advanced"
        assert features.audit_retention_days == 30
        assert features.ldap_sso_integration is True


class TestEditionFeaturesMapping:
    """Tests for EDITION_FEATURES mapping."""

    def test_community_features(self) -> None:
        """Test Community edition features."""
        features = EDITION_FEATURES[Edition.COMMUNITY]
        assert features.policy_engine == "basic"
        assert features.custom_policy_rules is False
        assert features.audit_retention_days == 7
        assert features.pii_redaction == "basic"
        assert features.sandbox_isolation == "basic"
        assert features.ldap_sso_integration is False
        assert features.dedicated_support is False
        assert features.sla_percentage is None

    def test_professional_features(self) -> None:
        """Test Professional edition features."""
        features = EDITION_FEATURES[Edition.PROFESSIONAL]
        assert features.policy_engine == "advanced"
        assert features.custom_policy_rules is True
        assert features.audit_retention_days == 30
        assert features.pii_redaction == "extended"
        assert features.sandbox_isolation == "advanced"
        assert features.ldap_sso_integration is True
        assert features.dedicated_support is False
        assert features.sla_percentage == 99.5

    def test_enterprise_features(self) -> None:
        """Test Enterprise edition features."""
        features = EDITION_FEATURES[Edition.ENTERPRISE]
        assert features.policy_engine == "advanced"
        assert features.custom_policy_rules is True
        assert features.audit_retention_days == -1  # Unlimited
        assert features.pii_redaction == "custom"
        assert features.sandbox_isolation == "advanced"
        assert features.ldap_sso_integration is True
        assert features.dedicated_support is True
        assert features.sla_percentage == 99.9


class TestEditionManager:
    """Tests for EditionManager class."""

    def test_default_edition(self) -> None:
        """Test default edition is Community."""
        manager = EditionManager()
        assert manager.edition == Edition.COMMUNITY

    def test_specific_edition(self) -> None:
        """Test creating manager with specific edition."""
        manager = EditionManager(Edition.ENTERPRISE)
        assert manager.edition == Edition.ENTERPRISE

    def test_features_property(self) -> None:
        """Test features property returns correct features."""
        manager = EditionManager(Edition.PROFESSIONAL)
        assert manager.features.policy_engine == "advanced"
        assert manager.features.audit_retention_days == 30

    def test_is_feature_available_bool(self) -> None:
        """Test checking boolean features."""
        community = EditionManager(Edition.COMMUNITY)
        enterprise = EditionManager(Edition.ENTERPRISE)

        assert community.is_feature_available("core_plugin_system") is True
        assert community.is_feature_available("ldap_sso_integration") is False
        assert enterprise.is_feature_available("ldap_sso_integration") is True

    def test_is_feature_available_nonexistent(self) -> None:
        """Test checking non-existent features."""
        manager = EditionManager()
        assert manager.is_feature_available("nonexistent_feature") is False

    def test_get_audit_retention_days(self) -> None:
        """Test getting audit retention days."""
        community = EditionManager(Edition.COMMUNITY)
        professional = EditionManager(Edition.PROFESSIONAL)
        enterprise = EditionManager(Edition.ENTERPRISE)

        assert community.get_audit_retention_days() == 7
        assert professional.get_audit_retention_days() == 30
        assert enterprise.get_audit_retention_days() == -1

    def test_get_pii_redaction_level(self) -> None:
        """Test getting PII redaction level."""
        community = EditionManager(Edition.COMMUNITY)
        professional = EditionManager(Edition.PROFESSIONAL)
        enterprise = EditionManager(Edition.ENTERPRISE)

        assert community.get_pii_redaction_level() == "basic"
        assert professional.get_pii_redaction_level() == "extended"
        assert enterprise.get_pii_redaction_level() == "custom"

    def test_has_advanced_policy_engine(self) -> None:
        """Test checking for advanced policy engine."""
        community = EditionManager(Edition.COMMUNITY)
        professional = EditionManager(Edition.PROFESSIONAL)

        assert community.has_advanced_policy_engine() is False
        assert professional.has_advanced_policy_engine() is True

    def test_has_ldap_sso(self) -> None:
        """Test checking for LDAP/SSO."""
        community = EditionManager(Edition.COMMUNITY)
        professional = EditionManager(Edition.PROFESSIONAL)

        assert community.has_ldap_sso() is False
        assert professional.has_ldap_sso() is True

    def test_has_custom_policy_rules(self) -> None:
        """Test checking for custom policy rules."""
        community = EditionManager(Edition.COMMUNITY)
        enterprise = EditionManager(Edition.ENTERPRISE)

        assert community.has_custom_policy_rules() is False
        assert enterprise.has_custom_policy_rules() is True

    def test_has_advanced_sandbox(self) -> None:
        """Test checking for advanced sandbox."""
        community = EditionManager(Edition.COMMUNITY)
        enterprise = EditionManager(Edition.ENTERPRISE)

        assert community.has_advanced_sandbox() is False
        assert enterprise.has_advanced_sandbox() is True

    def test_set_custom_pii_patterns_enterprise(self) -> None:
        """Test setting custom PII patterns in Enterprise edition."""
        manager = EditionManager(Edition.ENTERPRISE)
        patterns = [r"\bCUSTOM-\d{8}\b", r"\bINTERNAL-[A-Z]{4}\b"]
        manager.set_custom_pii_patterns(patterns)
        assert manager.get_custom_pii_patterns() == patterns

    def test_set_custom_pii_patterns_non_enterprise(self) -> None:
        """Test setting custom PII patterns fails in non-Enterprise editions."""
        manager = EditionManager(Edition.COMMUNITY)
        with pytest.raises(PermissionError):
            manager.set_custom_pii_patterns([r"\bCUSTOM-\d+\b"])

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        manager = EditionManager(Edition.PROFESSIONAL)
        result = manager.to_dict()

        assert result["edition"] == "professional"
        assert result["features"]["policy_engine"] == "advanced"
        assert result["features"]["audit_retention_days"] == 30
        assert result["features"]["sla_percentage"] == 99.5


class TestGlobalEditionFunctions:
    """Tests for global edition functions."""

    def test_get_edition_manager(self) -> None:
        """Test getting global edition manager."""
        manager = get_edition_manager()
        assert isinstance(manager, EditionManager)

    def test_set_edition_with_enum(self) -> None:
        """Test setting edition with enum."""
        set_edition(Edition.ENTERPRISE)
        assert get_edition() == Edition.ENTERPRISE

        # Reset to default
        set_edition(Edition.COMMUNITY)

    def test_set_edition_with_string(self) -> None:
        """Test setting edition with string."""
        set_edition("professional")
        assert get_edition() == Edition.PROFESSIONAL

        # Reset to default
        set_edition(Edition.COMMUNITY)

    def test_get_edition(self) -> None:
        """Test getting current edition."""
        set_edition(Edition.COMMUNITY)
        assert get_edition() == Edition.COMMUNITY


class TestEditionUpgradeScenarios:
    """Tests for edition upgrade scenarios."""

    def test_community_to_professional_upgrade(self) -> None:
        """Test features gained when upgrading from Community to Professional."""
        community = EditionManager(Edition.COMMUNITY)
        professional = EditionManager(Edition.PROFESSIONAL)

        # Features gained
        assert not community.has_advanced_policy_engine()
        assert professional.has_advanced_policy_engine()

        assert not community.has_custom_policy_rules()
        assert professional.has_custom_policy_rules()

        assert community.get_audit_retention_days() == 7
        assert professional.get_audit_retention_days() == 30

        assert not community.has_ldap_sso()
        assert professional.has_ldap_sso()

    def test_professional_to_enterprise_upgrade(self) -> None:
        """Test features gained when upgrading from Professional to Enterprise."""
        professional = EditionManager(Edition.PROFESSIONAL)
        enterprise = EditionManager(Edition.ENTERPRISE)

        # Both have these
        assert professional.has_advanced_policy_engine()
        assert enterprise.has_advanced_policy_engine()

        # Enterprise-only features
        assert professional.get_audit_retention_days() == 30
        assert enterprise.get_audit_retention_days() == -1  # Unlimited

        assert professional.get_pii_redaction_level() == "extended"
        assert enterprise.get_pii_redaction_level() == "custom"

        assert not professional.is_feature_available("dedicated_support")
        assert enterprise.is_feature_available("dedicated_support")
