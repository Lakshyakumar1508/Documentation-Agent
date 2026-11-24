"""Configuration settings for DocAgent."""

from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable override support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Application Settings
    APP_NAME: str = "DocAgent"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Security & Containment
    SECRET_KEY: str = "insecure-development-secret-key-change-in-production"
    ALLOWED_ORIGINS: List[str] = ["*"]
    MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    MAX_LOG_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MAX_REPO_SCAN_FILES: int = 10_000

    # Default Excluded Patterns (Directory / Glob names)
    DEFAULT_EXCLUDES: List[str] = [
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        "coverage",
        ".idea",
        ".vscode",
        ".DS_Store",
        "Thumbs.db",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "*.so",
        "*.dll",
        "*.dylib",
        "*.exe",
        "*.bin",
        ".env*",
    ]

    # Database & Persistence
    DATABASE_URL: str = "sqlite:///docagent.db"

    # LLM Settings
    LLM_PROVIDER: str = "openai"  # "openai", "nvidia", "ollama", "mock"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT_SECONDS: int = 60

    # GitHub App Integration
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None

    # Git Operations
    GIT_AUTHOR_NAME: str = "DocAgent Bot"
    GIT_AUTHOR_EMAIL: str = "docagent-bot@users.noreply.github.com"
    DEFAULT_BRANCH_PREFIX: str = "docagent/update-"


settings = Settings()
