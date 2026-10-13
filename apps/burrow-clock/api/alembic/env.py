"""Explicit product-local migrations. Never invoked by application import."""
from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from burrow_clock_api.infrastructure.database import validate_database_url
from burrow_clock_api.infrastructure.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def get_target_url() -> str:
    # Explicit config takes priority so dedicated tests cannot inherit a production URL.
    value = (config.get_main_option("sqlalchemy.url")
             or os.environ.get("BURROW_CLOCK_TEST_DATABASE_URL")
             or os.environ.get("BURROW_CLOCK_DATABASE_URL"))
    return validate_database_url(value)


if context.is_offline_mode():
    context.configure(url=get_target_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_target_url()
    engine = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
