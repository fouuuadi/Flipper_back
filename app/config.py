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

    redis_url: str = "redis://localhost:6379"
    redis_session_ttl_seconds: int = 1800

    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic_filter: str = "flipper/#"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
