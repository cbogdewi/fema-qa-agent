"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    # LLM provider: "groq" (default, free tier), "gemini" (free tier) or "fake" (tests/offline).
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "groq"))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-flash-latest"))
    llm_timeout_s: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_S", "20")))

    db_path: Path = field(default_factory=lambda: Path(os.getenv("DB_PATH", str(ROOT / "data" / "fema.duckdb"))))
    eval_results_path: Path = field(
        default_factory=lambda: Path(os.getenv("EVAL_RESULTS_PATH", str(ROOT / "evals" / "results" / "latest.json")))
    )

    allowed_origins: list[str] = field(
        default_factory=lambda: _list(
            "ALLOWED_ORIGINS",
            "https://dashboard.bogdewic.com,https://www.bogdewic.com,http://localhost:8000,http://127.0.0.1:8000",
        )
    )
    # Per-client request limits (per warm Lambda instance; abuse guard, not billing guard).
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "6")))
    rate_limit_per_day: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_DAY", "100")))
    max_question_chars: int = 500
    max_result_rows: int = 200


def get_settings() -> Settings:
    return Settings()
