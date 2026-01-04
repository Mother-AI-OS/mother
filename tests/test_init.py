"""Basic tests for Mother AI OS."""

import mother


def test_version() -> None:
    """Test that version is defined."""
    assert hasattr(mother, "__version__")
    assert isinstance(mother.__version__, str)
    assert mother.__version__ == "0.1.0"


def test_imports() -> None:
    """Test that main modules can be imported."""
    from mother.config import get_settings

    settings = get_settings()
    assert settings is not None
