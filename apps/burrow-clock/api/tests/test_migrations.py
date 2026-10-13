"""Real initial migration operations on SQLite; PostgreSQL migration/SQL checks are authoritative."""
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect

from burrow_clock_api.infrastructure.models import Base

API_ROOT = Path(__file__).resolve().parent.parent
TABLES = {"friendships", "sharing_permissions", "sharing_sessions"}


def assert_schema(connection):
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    inspector = inspect(connection)
    assert TABLES <= set(inspector.get_table_names())
    for table, identity in [("friendships", "friendship_id"), ("sharing_permissions", "permission_id"), ("sharing_sessions", "session_id")]:
        assert inspector.get_pk_constraint(table)["constrained_columns"] == [identity]
        assert {c["name"] for c in inspector.get_columns(table)} == set(Base.metadata.tables[table].columns.keys())
        assert all(c["default"] is None for c in inspector.get_columns(table))
    for table, index in [("friendships", "uq_friendships_active_pair"), ("sharing_permissions", "uq_permissions_current_direction")]:
        assert any(i["name"] == index and i["unique"] for i in inspector.get_indexes(table))
    permission_fks = inspector.get_foreign_keys("sharing_permissions")
    assert len(permission_fks) == 1
    assert permission_fks[0]["constrained_columns"] == ["friendship_id", "member_a_id", "member_b_id"]
    assert permission_fks[0]["referred_table"] == "friendships"
    assert permission_fks[0]["options"]["ondelete"] == "CASCADE"
    assert len(inspector.get_foreign_keys("sharing_sessions")) == 2
    assert all(fk["options"]["ondelete"] == "CASCADE" for fk in inspector.get_foreign_keys("sharing_sessions"))
    for column in inspector.get_columns("sharing_sessions"):
        if column["name"] in {"started_at", "expires_at"}:
            assert not column["nullable"]
    if connection.dialect.name == "postgresql":
        for table in ["sharing_permissions", "sharing_sessions"]:
            for column in inspector.get_columns(table):
                if column["name"].endswith("_at"):
                    assert column["type"].timezone


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_initial_revision_upgrade_downgrade_roundtrip(backend, request, migration_config):
    scripts = ScriptDirectory.from_config(migration_config)
    assert scripts.get_heads() == ["0001"]
    revision = scripts.get_revision("0001")
    assert revision.down_revision is None
    if backend == "postgres":
        engine = request.getfixturevalue("postgres_engine")
        command.upgrade(migration_config, "head")
        with engine.connect() as connection:
            assert_schema(connection)
        command.downgrade(migration_config, "base")
        with engine.connect() as connection:
            assert not TABLES & set(inspect(connection).get_table_names())
        command.upgrade(migration_config, "head")
        with engine.connect() as connection:
            assert_schema(connection)
    else:
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                revision.module.upgrade()
                assert_schema(connection)
                revision.module.downgrade()
                assert inspect(connection).get_table_names() == []
                revision.module.upgrade()
                assert_schema(connection)
        engine.dispose()


def test_postgresql_offline_sql_is_explicit_and_reversible(monkeypatch):
    monkeypatch.setenv("BURROW_CLOCK_DATABASE_URL", "sqlite:///unsupported-production.sqlite")
    output = StringIO()
    config = Config(str(API_ROOT / "alembic.ini"), output_buffer=output)
    config.set_main_option("sqlalchemy.url", "postgresql+psycopg://test_user:test_password@localhost/burrow_clock_test")
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert sql.count("TIMESTAMP WITH TIME ZONE") == 5
    assert "GENERATED ALWAYS AS" in sql
    assert "WHERE is_active" in sql and "WHERE is_current" in sql
    assert "ON DELETE CASCADE" in sql
    assert "INSERT INTO friendships" not in sql
    assert "INSERT INTO sharing_permissions" not in sql
    output.truncate(0)
    output.seek(0)
    command.downgrade(config, "0001:base", sql=True)
    assert all(f"DROP TABLE {table}" in output.getvalue() for table in TABLES)
