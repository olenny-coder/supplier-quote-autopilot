from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Supplier Quote Comparison Tool"

    DATABASE_URL: str

    OPENAI_API_KEY: str = ""

    # Resend transactional email (used by the supplier-mail agent). When the key
    # is unset the mailer refuses to send and surfaces a clear error.
    RESEND_API_KEY: str = ""
    MAIL_FROM: str = "Procurement Assistant <onboarding@resend.dev>"

    # NoDecode disables pydantic-settings' default JSON decoding for this
    # complex field, so the comma-separated .env value reaches the validator
    # below as a raw string instead of failing a json.loads() parse.
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = ["*"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
