import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings

# Jeu complet de variables requises (config.py n'a aucun défaut → toutes
# obligatoires). Les tests partent de ce socle valide et retirent / altèrent
# une variable pour vérifier le comportement.
REQUIRED_ENV = {
    "APP_PORT": "8080",
    "DB_HOST": "db",
    "DB_PORT": "5432",
    "DB_NAME": "flipper",
    "DB_USER": "flipper_user",
    "DB_PASSWORD": "secret",
    "REDIS_URL": "redis://redis:6379",
    "REDIS_SESSION_TTL_SECONDS": "1800",
    "MQTT_BROKER_HOST": "mqtt",
    "MQTT_BROKER_PORT": "1883",
    "MQTT_TOPIC_FILTER": "flipper/#",
    "LOG_LEVEL": "INFO",
}


@pytest.fixture
def full_env(monkeypatch):
    """Renseigne toutes les variables requises dans l'environnement."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    return dict(REQUIRED_ENV)


def _make_settings() -> Settings:
    # _env_file=None ignore le .env on-disk : les tests ne dépendent que de
    # l'environnement renseigné via monkeypatch, donc restent déterministes.
    return Settings(_env_file=None)


def test_loads_all_values_from_env(full_env):
    settings = _make_settings()

    assert settings.app_port == 8080
    assert settings.db_host == "db"
    assert settings.db_port == 5432
    assert settings.db_name == "flipper"
    assert settings.db_user == "flipper_user"
    assert settings.db_password == "secret"
    assert settings.redis_url == "redis://redis:6379"
    assert settings.redis_session_ttl_seconds == 1800
    assert settings.mqtt_broker_host == "mqtt"
    assert settings.mqtt_broker_port == 1883
    assert settings.mqtt_topic_filter == "flipper/#"
    assert settings.log_level == "INFO"


@pytest.mark.parametrize("missing_key", list(REQUIRED_ENV))
def test_missing_required_var_raises(full_env, monkeypatch, missing_key):
    # Fail-fast : retirer n'importe quelle variable requise empêche le boot.
    monkeypatch.delenv(missing_key, raising=False)

    with pytest.raises(ValidationError):
        _make_settings()


def test_env_vars_are_case_insensitive(full_env, monkeypatch):
    monkeypatch.setenv("db_host", "lowercase-host")

    settings = _make_settings()

    assert settings.db_host == "lowercase-host"


def test_invalid_port_raises(full_env, monkeypatch):
    monkeypatch.setenv("APP_PORT", "not-an-int")

    with pytest.raises(ValidationError):
        _make_settings()


def test_get_settings_returns_cached_instance():
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
