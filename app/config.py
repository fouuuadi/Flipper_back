from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_port: int = 8080

    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "flipper"
    db_user: str = "flipper_user"
    db_password: str = "flipper_password"


@lru_cache
def get_settings() -> Settings:
    return Settings()
