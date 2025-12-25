from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/tournaments",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT", "change-me")

    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 1025))
    MAIL_USE_TLS = bool(int(os.getenv("MAIL_USE_TLS", 0)))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@example.com")

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    RATELIMIT_STORAGE_URL = REDIS_URL

    # Pagination
    TOURNAMENTS_PER_PAGE = 10


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite+pysqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False


def get_config(name: str | None) -> type[BaseConfig]:
    mapping: dict[str | None, type[BaseConfig]] = {
        None: DevelopmentConfig,
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
    }
    return mapping.get(name, DevelopmentConfig)
