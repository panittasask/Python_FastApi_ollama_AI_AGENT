"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 600

    # Models
    refiner_model: str = "qwen2.5:7b"
    coder_model: str = "deepseek-coder:6.7b"
    fix_model: str = "codellama:13b"
    planner_model: str = "qwen2.5:7b"

    # Generation parameters
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 8192
    num_ctx: int = 8192

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    output_dir: Path = Path("./generated_projects")
    max_fix_iterations: int = 5
    max_generation_loops: int = 30
    enable_auto_test: bool = True

    def ensure_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
