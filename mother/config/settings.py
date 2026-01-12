"""Configuration settings using Pydantic."""

from functools import lru_cache
from pathlib import Path

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
    api_key: str | None = Field(default=None, alias="MOTHER_API_KEY")

    # LLM Provider Selection
    ai_provider: str = Field(
        default="anthropic",
        alias="AI_PROVIDER",
        description="LLM provider: anthropic, openai, zhipu, gemini",
    )
    llm_model: str | None = Field(
        default=None,
        alias="LLM_MODEL",
        description="Override default model for selected provider",
    )
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS")
    max_iterations: int = Field(default=10, alias="MAX_ITERATIONS")

    # Provider API Keys
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    zhipu_api_key: str | None = Field(None, alias="ZHIPU_API_KEY")
    gemini_api_key: str | None = Field(None, alias="GEMINI_API_KEY")

    # Legacy alias (deprecated, use LLM_MODEL instead)
    claude_model: str = Field(default="claude-sonnet-4-20250514", alias="CLAUDE_MODEL")

    # Tool Credentials
    mailcraft_password: str | None = Field(None, alias="MAILCRAFT_PASSWORD")

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

    # Policy Engine (Enterprise Security)
    safe_mode: bool = Field(
        default=True,
        alias="MOTHER_SAFE_MODE",
        description="Enable safe mode (restricts high-risk capabilities)",
    )
    policy_path: str | None = Field(
        default=None,
        alias="MOTHER_POLICY_PATH",
        description="Path to policy YAML file",
    )

    # Audit Logging
    audit_log_path: Path = Field(
        default=Path("./logs/audit.jsonl"),
        alias="MOTHER_AUDIT_LOG_PATH",
        description="Path to audit log file (JSONL format)",
    )
    audit_log_enabled: bool = Field(
        default=True,
        alias="MOTHER_AUDIT_ENABLED",
        description="Enable enterprise audit logging",
    )

    # Sandbox Mode
    sandbox_mode: bool = Field(
        default=True,
        alias="MOTHER_SANDBOX_MODE",
        description="Enable sandbox mode for high-risk capabilities",
    )
    workspace_dir: Path = Field(
        default=Path("./workspace"),
        alias="MOTHER_WORKSPACE_DIR",
        description="Safe working directory for file operations",
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Timeouts
    tool_timeout: int = Field(default=300, alias="TOOL_TIMEOUT")


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()
