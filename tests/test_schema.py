"""Tests for schema validation and version tracking."""

import pytest

from mother.plugins.exceptions import PluginValidationError
from mother.plugins.manifest import CapabilitySpec, ParameterSpec, ParameterType
from mother.plugins.schema import (
    SchemaValidator,
    VersionTracker,
    compare_versions,
    get_validator,
    get_version_tracker,
    is_version_compatible,
    parse_semver,
    validate_params,
)


class TestParseSemver:
    """Tests for semantic version parsing."""

    def test_parse_simple_version(self):
        """Test parsing simple versions."""
        major, minor, patch, pre, build = parse_semver("1.2.3")
        assert major == 1
        assert minor == 2
        assert patch == 3
        assert pre is None
        assert build is None

    def test_parse_version_with_prerelease(self):
        """Test parsing version with prerelease."""
        major, minor, patch, pre, build = parse_semver("1.0.0-alpha.1")
        assert major == 1
        assert minor == 0
        assert patch == 0
        assert pre == "alpha.1"
        assert build is None

    def test_parse_version_with_build(self):
        """Test parsing version with build metadata."""
        major, minor, patch, pre, build = parse_semver("1.0.0+build.123")
        assert major == 1
        assert minor == 0
        assert patch == 0
        assert pre is None
        assert build == "build.123"

    def test_parse_full_version(self):
        """Test parsing full semver with prerelease and build."""
        major, minor, patch, pre, build = parse_semver("2.1.0-beta.2+build.456")
        assert major == 2
        assert minor == 1
        assert patch == 0
        assert pre == "beta.2"
        assert build == "build.456"

    def test_parse_invalid_version(self):
        """Test parsing invalid version raises error."""
        with pytest.raises(ValueError, match="Invalid semver"):
            parse_semver("invalid")

        with pytest.raises(ValueError, match="Invalid semver"):
            parse_semver("1.2")

        with pytest.raises(ValueError, match="Invalid semver"):
            parse_semver("1.2.3.4")


class TestCompareVersions:
    """Tests for version comparison."""

    def test_equal_versions(self):
        """Test equal versions."""
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.3.4", "2.3.4") == 0

    def test_major_version_difference(self):
        """Test major version comparison."""
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.0.0", "2.0.0") == -1

    def test_minor_version_difference(self):
        """Test minor version comparison."""
        assert compare_versions("1.2.0", "1.1.0") == 1
        assert compare_versions("1.1.0", "1.2.0") == -1

    def test_patch_version_difference(self):
        """Test patch version comparison."""
        assert compare_versions("1.0.2", "1.0.1") == 1
        assert compare_versions("1.0.1", "1.0.2") == -1

    def test_prerelease_comparison(self):
        """Test prerelease version comparison."""
        # Non-prerelease > prerelease
        assert compare_versions("1.0.0", "1.0.0-alpha") == 1
        assert compare_versions("1.0.0-alpha", "1.0.0") == -1

        # Alphabetical prerelease comparison
        assert compare_versions("1.0.0-beta", "1.0.0-alpha") == 1
        assert compare_versions("1.0.0-alpha", "1.0.0-beta") == -1


class TestIsVersionCompatible:
    """Tests for version compatibility checking."""

    def test_exact_match(self):
        """Test exact version matching."""
        assert is_version_compatible("1.0.0", "1.0.0") is True
        assert is_version_compatible("1.0.0", "1.0.1") is False

    def test_greater_equal(self):
        """Test >= constraint."""
        assert is_version_compatible(">=1.0.0", "1.0.0") is True
        assert is_version_compatible(">=1.0.0", "1.1.0") is True
        assert is_version_compatible(">=1.0.0", "2.0.0") is True
        assert is_version_compatible(">=1.0.0", "0.9.0") is False

    def test_greater_than(self):
        """Test > constraint."""
        assert is_version_compatible(">1.0.0", "1.0.1") is True
        assert is_version_compatible(">1.0.0", "1.0.0") is False

    def test_less_equal(self):
        """Test <= constraint."""
        assert is_version_compatible("<=2.0.0", "1.0.0") is True
        assert is_version_compatible("<=2.0.0", "2.0.0") is True
        assert is_version_compatible("<=2.0.0", "2.1.0") is False

    def test_less_than(self):
        """Test < constraint."""
        assert is_version_compatible("<2.0.0", "1.9.9") is True
        assert is_version_compatible("<2.0.0", "2.0.0") is False

    def test_caret_range(self):
        """Test caret range (^)."""
        # ^1.0.0 means >=1.0.0 and same major
        assert is_version_compatible("^1.0.0", "1.0.0") is True
        assert is_version_compatible("^1.0.0", "1.5.0") is True
        assert is_version_compatible("^1.0.0", "2.0.0") is False
        assert is_version_compatible("^1.0.0", "0.9.0") is False

    def test_tilde_range(self):
        """Test tilde range (~)."""
        # ~1.0.0 means >=1.0.0 and same major.minor
        assert is_version_compatible("~1.0.0", "1.0.0") is True
        assert is_version_compatible("~1.0.0", "1.0.5") is True
        assert is_version_compatible("~1.0.0", "1.1.0") is False

    def test_compound_constraint(self):
        """Test compound constraints with comma."""
        assert is_version_compatible(">=1.0.0,<2.0.0", "1.5.0") is True
        assert is_version_compatible(">=1.0.0,<2.0.0", "2.0.0") is False
        assert is_version_compatible(">=1.0.0,<2.0.0", "0.9.0") is False


class TestSchemaValidator:
    """Tests for SchemaValidator."""

    @pytest.fixture
    def capability(self) -> CapabilitySpec:
        """Create a test capability."""
        return CapabilitySpec(
            name="test_capability",
            description="A test capability",
            parameters=[
                ParameterSpec(
                    name="required_string",
                    type=ParameterType.STRING,
                    description="A required string",
                    required=True,
                ),
                ParameterSpec(
                    name="optional_int",
                    type=ParameterType.INTEGER,
                    description="An optional integer",
                    required=False,
                    default=42,
                ),
                ParameterSpec(
                    name="choice_param",
                    type=ParameterType.STRING,
                    description="A choice parameter",
                    required=False,
                    choices=["option1", "option2", "option3"],
                ),
                ParameterSpec(
                    name="array_param",
                    type=ParameterType.ARRAY,
                    description="An array parameter",
                    required=False,
                    items_type=ParameterType.STRING,
                ),
                ParameterSpec(
                    name="bool_param",
                    type=ParameterType.BOOLEAN,
                    description="A boolean parameter",
                    required=False,
                ),
            ],
        )

    def test_validate_valid_params(self, capability):
        """Test validation with valid parameters."""
        validator = SchemaValidator()
        params = {"required_string": "hello", "optional_int": 10}
        result = validator.validate(capability, params, "test-plugin")

        assert result["required_string"] == "hello"
        assert result["optional_int"] == 10

    def test_validate_applies_defaults(self, capability):
        """Test validation applies default values."""
        validator = SchemaValidator()
        params = {"required_string": "hello"}
        result = validator.validate(capability, params, "test-plugin")

        assert result["required_string"] == "hello"
        assert result["optional_int"] == 42  # Default applied

    def test_validate_missing_required(self, capability):
        """Test validation fails for missing required parameter."""
        validator = SchemaValidator()
        params = {}  # Missing required_string

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate(capability, params, "test-plugin")

        assert "required_string" in str(exc_info.value)

    def test_validate_wrong_type_string(self, capability):
        """Test validation fails for wrong type (expected string)."""
        validator = SchemaValidator()
        params = {"required_string": 123}  # Should be string

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate(capability, params, "test-plugin")

        assert "string" in str(exc_info.value).lower()

    def test_validate_wrong_type_integer(self, capability):
        """Test validation fails for wrong type (expected integer)."""
        validator = SchemaValidator()
        params = {"required_string": "hello", "optional_int": "not an int"}

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate(capability, params, "test-plugin")

        assert "integer" in str(exc_info.value).lower()

    def test_validate_invalid_choice(self, capability):
        """Test validation fails for invalid choice value."""
        validator = SchemaValidator()
        params = {"required_string": "hello", "choice_param": "invalid_option"}

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate(capability, params, "test-plugin")

        assert "must be one of" in str(exc_info.value)

    def test_validate_valid_choice(self, capability):
        """Test validation succeeds for valid choice."""
        validator = SchemaValidator()
        params = {"required_string": "hello", "choice_param": "option2"}
        result = validator.validate(capability, params, "test-plugin")

        assert result["choice_param"] == "option2"

    def test_validate_array_type(self, capability):
        """Test validation for array type."""
        validator = SchemaValidator()
        params = {"required_string": "hello", "array_param": ["a", "b", "c"]}
        result = validator.validate(capability, params, "test-plugin")

        assert result["array_param"] == ["a", "b", "c"]

    def test_validate_array_wrong_item_type(self, capability):
        """Test validation fails for wrong array item type."""
        validator = SchemaValidator()
        params = {"required_string": "hello", "array_param": [1, 2, 3]}  # Should be strings

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate(capability, params, "test-plugin")

        assert "array" in str(exc_info.value).lower() or "string" in str(exc_info.value).lower()

    def test_validate_boolean_type(self, capability):
        """Test validation for boolean type."""
        validator = SchemaValidator()
        params = {"required_string": "hello", "bool_param": True}
        result = validator.validate(capability, params, "test-plugin")

        assert result["bool_param"] is True

    def test_validate_boolean_wrong_type(self, capability):
        """Test validation fails for non-boolean as boolean."""
        validator = SchemaValidator()
        params = {"required_string": "hello", "bool_param": "true"}  # String, not bool

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate(capability, params, "test-plugin")

        assert "boolean" in str(exc_info.value).lower()

    def test_validate_strict_unknown_param(self, capability):
        """Test strict mode rejects unknown parameters."""
        validator = SchemaValidator(strict=True)
        params = {"required_string": "hello", "unknown_param": "value"}

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate(capability, params, "test-plugin")

        assert "Unknown parameter" in str(exc_info.value)

    def test_validate_non_strict_unknown_param(self, capability):
        """Test non-strict mode ignores unknown parameters."""
        validator = SchemaValidator(strict=False)
        params = {"required_string": "hello", "unknown_param": "value"}
        result = validator.validate(capability, params, "test-plugin")

        assert result["required_string"] == "hello"
        assert "unknown_param" not in result  # Unknown params not included


class TestVersionTracker:
    """Tests for VersionTracker."""

    @pytest.fixture
    def capabilities_v1(self) -> list[CapabilitySpec]:
        """Create v1 capabilities."""
        return [
            CapabilitySpec(
                name="send_message",
                description="Send a message",
                parameters=[
                    ParameterSpec(name="to", type=ParameterType.STRING, required=True),
                    ParameterSpec(name="body", type=ParameterType.STRING, required=True),
                    ParameterSpec(
                        name="priority", type=ParameterType.STRING, required=False, choices=["low", "normal", "high"]
                    ),
                ],
            ),
        ]

    @pytest.fixture
    def capabilities_v2_compatible(self) -> list[CapabilitySpec]:
        """Create v2 capabilities (backward compatible)."""
        return [
            CapabilitySpec(
                name="send_message",
                description="Send a message (v2)",
                parameters=[
                    ParameterSpec(name="to", type=ParameterType.STRING, required=True),
                    ParameterSpec(name="body", type=ParameterType.STRING, required=True),
                    ParameterSpec(
                        name="priority", type=ParameterType.STRING, required=False, choices=["low", "normal", "high"]
                    ),
                    ParameterSpec(name="cc", type=ParameterType.STRING, required=False),  # New optional param
                ],
            ),
        ]

    @pytest.fixture
    def capabilities_v2_breaking(self) -> list[CapabilitySpec]:
        """Create v2 capabilities with breaking changes."""
        return [
            CapabilitySpec(
                name="send_message",
                description="Send a message (v2 breaking)",
                parameters=[
                    ParameterSpec(name="to", type=ParameterType.STRING, required=True),
                    ParameterSpec(name="content", type=ParameterType.STRING, required=True),  # Renamed from body
                    ParameterSpec(name="priority", type=ParameterType.INTEGER, required=False),  # Changed type
                ],
            ),
        ]

    def test_register_schema(self, capabilities_v1):
        """Test registering a schema."""
        tracker = VersionTracker()
        tracker.register_schema("test-plugin", "1.0.0", capabilities_v1)

        # No error means success
        assert True

    def test_detect_no_breaking_changes(self, capabilities_v1, capabilities_v2_compatible):
        """Test detecting no breaking changes for compatible update."""
        tracker = VersionTracker()
        tracker.register_schema("test-plugin", "1.0.0", capabilities_v1)
        tracker.register_schema("test-plugin", "1.1.0", capabilities_v2_compatible)

        changes = tracker.detect_breaking_changes("test-plugin", "1.0.0", "1.1.0")
        assert len(changes) == 0

    def test_detect_removed_required_param(self, capabilities_v1, capabilities_v2_breaking):
        """Test detecting removed required parameter."""
        tracker = VersionTracker()
        tracker.register_schema("test-plugin", "1.0.0", capabilities_v1)
        tracker.register_schema("test-plugin", "2.0.0", capabilities_v2_breaking)

        changes = tracker.detect_breaking_changes("test-plugin", "1.0.0", "2.0.0")

        # Should detect 'body' removed (it was required)
        assert any("body" in change for change in changes)

    def test_detect_type_change(self, capabilities_v1, capabilities_v2_breaking):
        """Test detecting parameter type change."""
        tracker = VersionTracker()
        tracker.register_schema("test-plugin", "1.0.0", capabilities_v1)
        tracker.register_schema("test-plugin", "2.0.0", capabilities_v2_breaking)

        changes = tracker.detect_breaking_changes("test-plugin", "1.0.0", "2.0.0")

        # Should detect 'priority' type change
        assert any("priority" in change and "type" in change.lower() for change in changes)

    def test_detect_removed_capability(self, capabilities_v1):
        """Test detecting removed capability."""
        tracker = VersionTracker()
        tracker.register_schema("test-plugin", "1.0.0", capabilities_v1)
        tracker.register_schema("test-plugin", "2.0.0", [])  # No capabilities

        changes = tracker.detect_breaking_changes("test-plugin", "1.0.0", "2.0.0")

        assert any("send_message" in change for change in changes)


class TestGlobalInstances:
    """Tests for global validator and tracker instances."""

    def test_get_validator(self):
        """Test getting global validator."""
        validator = get_validator()
        assert isinstance(validator, SchemaValidator)

        # Same instance returned
        assert get_validator() is validator

    def test_get_version_tracker(self):
        """Test getting global version tracker."""
        tracker = get_version_tracker()
        assert isinstance(tracker, VersionTracker)

        # Same instance returned
        assert get_version_tracker() is tracker


class TestValidateParamsConvenience:
    """Tests for validate_params convenience function."""

    def test_validate_params_success(self):
        """Test validate_params convenience function."""
        capability = CapabilitySpec(
            name="test",
            description="Test capability",
            parameters=[
                ParameterSpec(name="value", type=ParameterType.STRING, required=True),
            ],
        )

        result = validate_params(capability, {"value": "hello"}, "test-plugin")
        assert result["value"] == "hello"

    def test_validate_params_failure(self):
        """Test validate_params raises on validation error."""
        capability = CapabilitySpec(
            name="test",
            description="Test capability",
            parameters=[
                ParameterSpec(name="value", type=ParameterType.STRING, required=True),
            ],
        )

        with pytest.raises(PluginValidationError):
            validate_params(capability, {}, "test-plugin")
