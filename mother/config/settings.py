"""Configuration settings using Pydantic."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Central credentials file location
CREDENTIALS_FILE = Path.home() / ".config" / "mother" / "credentials.env"


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=(CREDENTIALS_FILE, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Settings
    api_host: str = Field(default="127.0.0.1", alias="MOTHER_HOST")
    api_port: int = Field(default=8080, alias="MOTHER_PORT")
    api_key: Optional[str] = Field(default=None, alias="MOTHER_API_KEY")

    # Claude Settings
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(
        default="claude-sonnet-4-20250514", alias="CLAUDE_MODEL"
    )
    max_iterations: int = Field(default=10, alias="MAX_ITERATIONS")

    # Tool Credentials
    mailcraft_password: Optional[str] = Field(None, alias="MAILCRAFT_PASSWORD")
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")

    # Paths
    config_dir: Path = Field(
        default=Path.home() / ".config" / "mother",
        alias="MOTHER_CONFIG_DIR",
    )
    log_dir: Path = Field(
        default=Path.home() / ".local" / "share" / "mother" / "logs",
        alias="MOTHER_LOG_DIR",
    )

    # Tool Paths
    mailcraft_bin: Path = Field(
        default=Path.home() / ".local" / "bin" / "mailcraft",
        alias="MAILCRAFT_BIN",
    )
    leads_bin: Path = Field(
        default=Path.home() / ".local" / "bin" / "leads",
        alias="LEADS_BIN",
    )
    taxlord_dir: Path = Field(
        default=Path.home() / "projects" / "taxlord",
        alias="TAXLORD_DIR",
    )
    gcp_draft_bin: Path = Field(
        default=Path.home() / ".local" / "bin" / "gcp-draft",
        alias="GCP_DRAFT_BIN",
    )

    # Security
    require_auth: bool = Field(default=True, alias="MOTHER_REQUIRE_AUTH")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Timeouts
    tool_timeout: int = Field(default=300, alias="TOOL_TIMEOUT")


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()
