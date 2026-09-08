"""Database engine foundation and configuration for Hogwarts Trials API.

Provides helpers for configuring database connections, building synchronous SQLAlchemy 2.x
engines and session factories, and validating repository backend environment settings.
"""

from collections.abc import Mapping
import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

QUIZ_REPOSITORY_ENV_VAR = "HOGWARTS_TRIALS_QUIZ_REPOSITORY"
DATABASE_URL_ENV_VAR = "HOGWARTS_TRIALS_DATABASE_URL"

DEFAULT_REPOSITORY_BACKEND = "memory"
SUPPORTED_REPOSITORY_BACKENDS = ("memory", "postgres")

_POSTGRESQL_SCHEMES = ("postgresql", "postgresql+psycopg")


def get_repository_backend(env: Mapping[str, str] | None = None) -> str:
    """Retrieve and validate the configured quiz repository backend.

    Defaults to 'memory' if unspecified or empty. Supported backends are
    'memory' and 'postgres'.
    """
    source = os.environ if env is None else env
    raw = source.get(QUIZ_REPOSITORY_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_REPOSITORY_BACKEND

    backend = raw.strip().lower()
    if backend not in SUPPORTED_REPOSITORY_BACKENDS:
        supported = ", ".join(repr(b) for b in SUPPORTED_REPOSITORY_BACKENDS)
        raise ValueError(
            f"Unsupported quiz repository backend: {raw!r}. "
            f"Supported backends are: {supported}."
        )
    return backend


def validate_database_url(url: str) -> str:
    """Validate and normalize a PostgreSQL database URL.

    Ensures the URL uses a PostgreSQL scheme compatible with SQLAlchemy 2.x and psycopg v3.
    If the scheme is 'postgresql', it is normalized to 'postgresql+psycopg'.
    """
    if not url or not url.strip():
        raise ValueError("Database URL must be a non-empty string.")

    cleaned = url.strip()
    parsed = urlsplit(cleaned)
    scheme = parsed.scheme.lower()

    if scheme not in _POSTGRESQL_SCHEMES:
        allowed = ", ".join(repr(s) for s in _POSTGRESQL_SCHEMES)
        raise ValueError(
            f"Invalid database URL scheme: {parsed.scheme!r}. "
            f"Only PostgreSQL schemes are supported: {allowed}."
        )

    # Normalize 'postgresql://' to 'postgresql+psycopg://' to guarantee psycopg v3 driver usage
    if scheme == "postgresql":
        normalized = urlunsplit(("postgresql+psycopg", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
        return normalized

    return cleaned


def get_database_url(env: Mapping[str, str] | None = None) -> str:
    """Retrieve and validate the database URL from environment.

    Raises ValueError if HOGWARTS_TRIALS_DATABASE_URL is unset or empty.
    """
    source = os.environ if env is None else env
    raw = source.get(DATABASE_URL_ENV_VAR)
    if raw is None or not raw.strip():
        raise ValueError(
            f"{DATABASE_URL_ENV_VAR} environment variable is required "
            "when quiz repository backend is 'postgres'."
        )
    return validate_database_url(raw)


def create_db_engine(database_url: str, **kwargs: Any) -> Engine:
    """Create a synchronous SQLAlchemy 2.x Engine for PostgreSQL.

    URL is validated and normalized prior to engine construction.
    """
    normalized_url = validate_database_url(database_url)
    engine_kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        **kwargs,
    }
    return create_engine(normalized_url, **engine_kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a synchronous SQLAlchemy sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

