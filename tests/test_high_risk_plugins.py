"""Tests for high-risk plugin handling."""

import pytest

from mother.plugins.manifest import (
    HIGH_RISK_PERMISSIONS,
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
    RiskLevel,
)


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_levels_exist(self) -> None:
        """Test all risk levels are defined."""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_level_ordering(self) -> None:
        """Test risk levels have logical ordering."""
        levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert len(levels) == 4


class TestHighRiskPermissions:
    """Tests for HIGH_RISK_PERMISSIONS set."""

    def test_high_risk_permissions_defined(self) -> None:
        """Test high-risk permissions are defined."""
        assert "shell" in HIGH_RISK_PERMISSIONS
        assert "subprocess" in HIGH_RISK_PERMISSIONS
        assert "filesystem:write" in HIGH_RISK_PERMISSIONS
        assert "filesystem:delete" in HIGH_RISK_PERMISSIONS
        assert "secrets:write" in HIGH_RISK_PERMISSIONS
        assert "secrets:read" in HIGH_RISK_PERMISSIONS
        assert "network:external" in HIGH_RISK_PERMISSIONS

    def test_safe_permissions_not_high_risk(self) -> None:
        """Test safe permissions are not in high-risk set."""
        assert "filesystem:read" not in HIGH_RISK_PERMISSIONS
        assert "network:internal" not in HIGH_RISK_PERMISSIONS
        assert "notify" not in HIGH_RISK_PERMISSIONS


class TestPluginMetadata:
    """Tests for PluginMetadata risk settings."""

    def test_default_risk_level(self) -> None:
        """Test default risk level is MEDIUM."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test",
        )
        assert metadata.risk_level == RiskLevel.MEDIUM
        assert metadata.disabled_by_default is False

    def test_custom_risk_level(self) -> None:
        """Test custom risk level."""
        metadata = PluginMetadata(
            name="dangerous-plugin",
            version="1.0.0",
            description="Dangerous plugin",
            author="Test",
            risk_level=RiskLevel.CRITICAL,
        )
        assert metadata.risk_level == RiskLevel.CRITICAL

    def test_disabled_by_default(self) -> None:
        """Test disabled_by_default flag."""
        metadata = PluginMetadata(
            name="risky-plugin",
            version="1.0.0",
            description="Risky plugin",
            author="Test",
            disabled_by_default=True,
        )
        assert metadata.disabled_by_default is True


class TestPluginManifestHighRisk:
    """Tests for PluginManifest high-risk detection."""

    @pytest.fixture
    def base_capability(self) -> CapabilitySpec:
        """Create a basic capability."""
        return CapabilitySpec(
            name="test_action",
            description="Test action",
            parameters=[
                ParameterSpec(
                    name="input",
                    type=ParameterType.STRING,
                    description="Input value",
                ),
            ],
        )

    @pytest.fixture
    def base_execution(self) -> ExecutionSpec:
        """Create a basic execution spec."""
        return ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="test_module",
                **{"class": "TestClass"},
            ),
        )

    def test_get_high_risk_permissions_none(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test plugin with no high-risk permissions."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="safe-plugin",
                version="1.0.0",
                description="Safe plugin",
                author="Test",
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=["filesystem:read", "network:internal"],
        )
        assert manifest.get_high_risk_permissions() == []
        assert manifest.has_high_risk_permissions() is False

    def test_get_high_risk_permissions_with_shell(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test plugin with shell permission."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="shell-plugin",
                version="1.0.0",
                description="Shell plugin",
                author="Test",
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=["shell", "filesystem:read"],
        )
        high_risk = manifest.get_high_risk_permissions()
        assert "shell" in high_risk
        assert manifest.has_high_risk_permissions() is True

    def test_get_high_risk_permissions_multiple(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test plugin with multiple high-risk permissions."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="multi-risk-plugin",
                version="1.0.0",
                description="Multi-risk plugin",
                author="Test",
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=["shell", "subprocess", "secrets:read", "filesystem:write"],
        )
        high_risk = manifest.get_high_risk_permissions()
        assert len(high_risk) == 4
        assert set(high_risk) == {"shell", "subprocess", "secrets:read", "filesystem:write"}

    def test_is_disabled_by_default_explicit(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test plugin explicitly marked as disabled by default."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="explicit-disabled",
                version="1.0.0",
                description="Explicitly disabled plugin",
                author="Test",
                disabled_by_default=True,
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=["filesystem:read"],  # Safe permission
        )
        assert manifest.is_disabled_by_default() is True

    def test_is_disabled_by_default_high_risk_level(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test plugin with HIGH risk level is disabled by default."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="high-risk-plugin",
                version="1.0.0",
                description="High risk plugin",
                author="Test",
                risk_level=RiskLevel.HIGH,
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=["filesystem:read"],  # Safe permission
        )
        assert manifest.is_disabled_by_default() is True

    def test_is_disabled_by_default_critical_risk_level(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test plugin with CRITICAL risk level is disabled by default."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="critical-risk-plugin",
                version="1.0.0",
                description="Critical risk plugin",
                author="Test",
                risk_level=RiskLevel.CRITICAL,
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=[],
        )
        assert manifest.is_disabled_by_default() is True

    def test_is_disabled_by_default_high_risk_permissions(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test plugin with high-risk permissions is disabled by default."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="permissions-risk-plugin",
                version="1.0.0",
                description="Plugin with risky permissions",
                author="Test",
                risk_level=RiskLevel.LOW,  # Low risk level
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=["shell"],  # High-risk permission
        )
        assert manifest.is_disabled_by_default() is True

    def test_is_disabled_by_default_safe_plugin(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test safe plugin is not disabled by default."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="safe-plugin",
                version="1.0.0",
                description="Safe plugin",
                author="Test",
                risk_level=RiskLevel.LOW,
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=["filesystem:read", "network:internal"],
        )
        assert manifest.is_disabled_by_default() is False

    def test_is_disabled_by_default_medium_risk_safe(
        self, base_capability: CapabilitySpec, base_execution: ExecutionSpec
    ) -> None:
        """Test MEDIUM risk plugin without high-risk permissions is not disabled."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="medium-plugin",
                version="1.0.0",
                description="Medium risk plugin",
                author="Test",
                risk_level=RiskLevel.MEDIUM,
            ),
            capabilities=[base_capability],
            execution=base_execution,
            permissions=["filesystem:read", "network:internal"],
        )
        assert manifest.is_disabled_by_default() is False


class TestPluginConfigHighRisk:
    """Tests for PluginConfig high-risk settings."""

    def test_default_config_disallows_high_risk(self) -> None:
        """Test default config disallows high-risk plugins."""
        from mother.plugins import PluginConfig

        config = PluginConfig()
        assert config.allow_high_risk_plugins is False
        assert config.explicitly_enabled_plugins == []

    def test_allow_high_risk_plugins(self) -> None:
        """Test allowing high-risk plugins."""
        from mother.plugins import PluginConfig

        config = PluginConfig(allow_high_risk_plugins=True)
        assert config.allow_high_risk_plugins is True

    def test_explicitly_enabled_plugins(self) -> None:
        """Test explicitly enabled plugins list."""
        from mother.plugins import PluginConfig

        config = PluginConfig(explicitly_enabled_plugins=["dangerous-plugin"])
        assert "dangerous-plugin" in config.explicitly_enabled_plugins
