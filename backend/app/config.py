from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("NOVELCRAFT_ENV", "development")
    ai_provider: str = os.getenv("NOVELCRAFT_AI_PROVIDER", "deepseek")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    request_timeout_seconds: int = int(os.getenv("NOVELCRAFT_REQUEST_TIMEOUT_SECONDS", "45"))
    bootstrap_budget_cny: float = float(os.getenv("NOVELCRAFT_BOOTSTRAP_BUDGET_CNY", "2.0"))
    jwt_secret: str = os.getenv("NOVELCRAFT_JWT_SECRET", "")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_EXP_MINUTES", "30"))
    refresh_token_days: int = int(os.getenv("REFRESH_TOKEN_EXP_DAYS", "30"))
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    cookie_samesite: str = os.getenv("COOKIE_SAMESITE", "lax").lower()
    token_blacklist_fail_closed: bool = os.getenv("TOKEN_BLACKLIST_FAIL_CLOSED", "true").lower() == "true"
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    )

    def __post_init__(self) -> None:
        if self.environment.lower() == "production":
            if len(self.jwt_secret) < 32:
                raise ValueError("生产环境 NOVELCRAFT_JWT_SECRET 至少需要 32 字符")
            if not self.cookie_secure:
                raise ValueError("生产环境必须设置 COOKIE_SECURE=true")
        if self.cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE 必须是 lax、strict 或 none")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none 时必须设置 COOKIE_SECURE=true")


settings = Settings()
