import pytest

from app.config import Settings, get_settings


def _make_settings() -> Settings:
    # _env_file=None ignore the on-disk .env so tests stay deterministic
    return Settings(_env_file=None)


def test_defaults_when_no_env_vars(monkeypatch):
    for key in ("APP_PORT", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)

    settings = _make_settings()

    assert settings.app_port == 8080
    assert settings.db_host == "localhost"
    assert settings.db_port == 5432
    assert settings.db_name == "flipper"
    assert settings.db_user == "flipper_user"
    assert settings.db_password == "flipper_password"


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_PORT", "5555")
    monkeypatch.setenv("DB_NAME", "mydb")
    monkeypatch.setenv("DB_USER", "myuser")
    monkeypatch.setenv("DB_PASSWORD", "secret")

    settings = _make_settings()

    assert settings.app_port == 9000
    assert settings.db_host == "db.example.com"
    assert settings.db_port == 5555
    assert settings.db_name == "mydb"
    assert settings.db_user == "myuser"
    assert settings.db_password == "secret"


def test_env_vars_are_case_insensitive(monkeypatch):
    monkeypatch.setenv("db_host", "lowercase-host")

    settings = _make_settings()

    assert settings.db_host == "lowercase-host"


def test_invalid_port_raises(monkeypatch):
    monkeypatch.setenv("APP_PORT", "not-an-int")

    with pytest.raises(ValueError):
        _make_settings()


def test_get_settings_returns_cached_instance():
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
