"""Explicit, lazy PostgreSQL engine/session construction; no import-time datastore."""

from collections.abc import Mapping
import os
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL_ENV_VAR = "BURROW_CLOCK_DATABASE_URL"
TEST_DATABASE_URL_ENV_VAR = "BURROW_CLOCK_TEST_DATABASE_URL"


def validate_database_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("A PostgreSQL database URL is required")
    parsed = make_url(url.strip())
    if parsed.drivername not in ("postgresql", "postgresql+psycopg"):
        raise ValueError("Only postgresql:// and postgresql+psycopg:// are supported")
    return parsed.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def get_database_url(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    raw = source.get(DATABASE_URL_ENV_VAR)
    if not raw:
        raise ValueError(f"{DATABASE_URL_ENV_VAR} is required for persistence")
    return validate_database_url(raw)


def create_db_engine(database_url: str, **kwargs: Any) -> Engine:
    return create_engine(validate_database_url(database_url), **{"pool_pre_ping": True, **kwargs})


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
