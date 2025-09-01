"""Application configuration management."""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ..models import AIProvider

# Load environment variables from .env file
load_dotenv()


class AIConfig(BaseModel):
    """AI-related configuration."""

    enable_auto_enrichment: bool = Field(
        default=True, description="Enable automatic AI enrichment"
    )

    # API keys
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")

    # Model configurations
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    anthropic_model: str = Field(
        default="claude-3-haiku-20240307", description="Anthropic model to use"
    )

    # Provider settings
    default_provider: AIProvider = Field(
        default=AIProvider.OPENAI, description="Default AI provider"
    )
    confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence for auto-apply"
    )

    # Timeouts and retries
    request_timeout: int = Field(
        default=30, description="API request timeout in seconds"
    )
    max_retries: int = Field(default=2, description="Maximum retry attempts")


class DatabaseConfig(BaseModel):
    """Database configuration."""

    database_path: str = Field(
        default="~/.local/share/todo/todos.db", description="Database file path"
    )


class AppConfig(BaseModel):
    """Main application configuration."""

    ai: AIConfig = Field(default_factory=AIConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # Application settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")


def get_app_config() -> AppConfig:
    """Get application configuration from environment and defaults."""
    ai_config = AIConfig(
        enable_auto_enrichment=os.getenv("TODO_ENABLE_AI", "true").lower() == "true",
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_model=os.getenv("TODO_OPENAI_MODEL", "gpt-4o-mini"),
        anthropic_model=os.getenv("TODO_ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
        default_provider=AIProvider(os.getenv("TODO_DEFAULT_AI_PROVIDER", "openai")),
        confidence_threshold=float(os.getenv("TODO_AI_CONFIDENCE_THRESHOLD", "0.7")),
        request_timeout=int(os.getenv("TODO_AI_REQUEST_TIMEOUT", "30")),
        max_retries=int(os.getenv("TODO_AI_MAX_RETRIES", "2")),
    )

    database_config = DatabaseConfig(
        database_path=os.getenv("TODO_DATABASE_PATH", "~/.local/share/todo/todos.db")
    )

    return AppConfig(
        ai=ai_config,
        database=database_config,
        debug=os.getenv("TODO_DEBUG", "false").lower() == "true",
        log_level=os.getenv("TODO_LOG_LEVEL", "INFO").upper(),
    )
