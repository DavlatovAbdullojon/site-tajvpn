from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    app_name: str = "TAJ VPN API"
    environment: str = "development"
    database_url: str = f"sqlite:///{(BASE_DIR / 'vpn_backend.db').as_posix()}"
    public_base_url: str = "https://api.tajvpn.com"
    allowed_origins: str = "https://tajvpn.com,https://admin.tajvpn.com,http://localhost:3000,http://localhost:5173"

    admin_token: str = ""
    free_trial_days: int = 15

    enot_api_base: str = "https://api.enot.io"
    enot_shop_id: str = ""
    enot_api_key: str = ""
    enot_webhook_secret: str = ""
    enot_currency: str = "RUB"
    enot_success_url: str = "https://tajvpn.com/payment/success"
    enot_fail_url: str = "https://tajvpn.com/payment/fail"
    enot_expire_minutes: int = 30
    enot_hook_path: str = "/webhooks/enot"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        return origins or ["*"]

    @property
    def enot_hook_url(self) -> str:
        base = self.public_base_url.rstrip("/")
        path = self.enot_hook_path if self.enot_hook_path.startswith("/") else f"/{self.enot_hook_path}"
        return f"{base}{path}"

    @property
    def has_enot_credentials(self) -> bool:
        return bool(self.enot_shop_id and self.enot_api_key)

    @field_validator("public_base_url", "enot_api_base", mode="before")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
