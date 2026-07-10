from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ai_provider: str = os.getenv("NOVELCRAFT_AI_PROVIDER", "deepseek")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    request_timeout_seconds: int = int(os.getenv("NOVELCRAFT_REQUEST_TIMEOUT_SECONDS", "45"))
    bootstrap_budget_cny: float = float(os.getenv("NOVELCRAFT_BOOTSTRAP_BUDGET_CNY", "2.0"))


settings = Settings()
