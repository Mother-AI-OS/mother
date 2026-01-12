"""Configuration module."""

from .editions import (
    Edition,
    EditionFeatures,
    EditionManager,
    get_edition,
    get_edition_manager,
    set_edition,
)
from .settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
    "Edition",
    "EditionFeatures",
    "EditionManager",
    "get_edition",
    "get_edition_manager",
    "set_edition",
]
