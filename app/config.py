from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'app, 100% pilotée par l'environnement.

    Aucune valeur par défaut : si une variable manque, pydantic lève une
    `ValidationError` au démarrage (fail-fast) plutôt que de booter sur une
    config silencieusement fausse (mauvais host, mot de passe par défaut…).
    En dev les variables viennent du `.env` ; sur la borne elles sont
    injectées par le dashboard Fliphetic / le `docker-compose.yml` de déploiement.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_port: int

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    redis_url: str
    redis_session_ttl_seconds: int

    mqtt_broker_host: str
    mqtt_broker_port: int
    mqtt_topic_filter: str

    # Identifiant du canal borne permanent : les 3 écrans (playfield/backglass/
    # dmd) s'y connectent au boot et reçoivent l'état partagé broadcasté.
    borne_id: str

    log_level: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
