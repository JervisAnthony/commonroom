"""Alembic environment configuration for Hogwarts Trials API.

Resolves target metadata from infrastructure persistence models and pulls the database
URL dynamically from environment variables (HOGWARTS_TRIALS_DATABASE_URL or
HOGWARTS_TRIALS_TEST_DATABASE_URL) to ensure credentials are never committed.
"""

from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from hogwarts_trials_api.infrastructure.database import validate_database_url
from hogwarts_trials_api.infrastructure.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate and migration inspection
target_metadata = Base.metadata


def get_target_url() -> str:
    """Retrieve and validate the database URL for migrations from environment or config."""
    env_url = (
        os.environ.get("HOGWARTS_TRIALS_DATABASE_URL")
        or os.environ.get("HOGWARTS_TRIALS_TEST_DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
    )
    if not env_url or not env_url.strip():
        raise ValueError(
            "Database URL for Alembic migrations is not configured. "
            "Please set HOGWARTS_TRIALS_DATABASE_URL or HOGWARTS_TRIALS_TEST_DATABASE_URL."
        )
    return validate_database_url(env_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an Engine
    is acceptable here as well. By skipping the Engine creation we don't even need a
    DBAPI to be available.
    """
    url = get_target_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection with the
    context.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_target_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

