"""Basic tests for Mother AI OS."""

import mother


def test_version() -> None:
    """Test that version is defined and follows semver format."""
    assert hasattr(mother, "__version__")
    assert isinstance(mother.__version__, str)
    # Check semver format (major.minor.patch)
    parts = mother.__version__.split(".")
    assert len(parts) >= 2, f"Version should be semver format: {mother.__version__}"
    assert all(p.isdigit() for p in parts[:2]), f"Version parts should be numeric: {mother.__version__}"


def test_imports() -> None:
    """Test that main modules can be imported."""
    from mother.config import get_settings

    settings = get_settings()
    assert settings is not None
