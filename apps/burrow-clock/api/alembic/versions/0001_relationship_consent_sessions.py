"""Burrow-specific relationship, directional consent, and session metadata.

Revision ID: 0001
Revises: None
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("friendship_id", sa.Uuid(), primary_key=True),
        sa.Column("user_a_id", sa.Uuid(), nullable=False),
        sa.Column("user_b_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("user_a_id < user_b_id", name="ck_friendships_canonical_pair"),
        sa.UniqueConstraint("friendship_id", "user_a_id", "user_b_id", name="uq_friendships_members"),
    )
    op.create_index(
        "uq_friendships_active_pair", "friendships", ["user_a_id", "user_b_id"], unique=True,
        postgresql_where=sa.text("is_active"), sqlite_where=sa.text("is_active = 1"),
    )
    op.create_table(
        "sharing_permissions",
        sa.Column("permission_id", sa.Uuid(), primary_key=True),
        sa.Column("friendship_id", sa.Uuid(), nullable=False),
        sa.Column("sharer_user_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("member_a_id", sa.Uuid(), sa.Computed(
            "CASE WHEN sharer_user_id < recipient_user_id THEN sharer_user_id ELSE recipient_user_id END",
            persisted=True,
        ), nullable=False),
        sa.Column("member_b_id", sa.Uuid(), sa.Computed(
            "CASE WHEN sharer_user_id < recipient_user_id THEN recipient_user_id ELSE sharer_user_id END",
            persisted=True,
        ), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.CheckConstraint("sharer_user_id <> recipient_user_id", name="ck_permissions_distinct_parties"),
        sa.CheckConstraint("scope IN ('PRESENCE', 'APPROXIMATE', 'PRECISE')", name="ck_permissions_scope"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > granted_at", name="ck_permissions_expiry"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= granted_at", name="ck_permissions_revocation"),
        sa.ForeignKeyConstraint(
            ["friendship_id", "member_a_id", "member_b_id"],
            ["friendships.friendship_id", "friendships.user_a_id", "friendships.user_b_id"],
            name="fk_permissions_friendship_members", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("permission_id", "friendship_id", name="uq_permissions_friendship"),
    )
    op.create_index(
        "uq_permissions_current_direction", "sharing_permissions",
        ["friendship_id", "sharer_user_id", "recipient_user_id"], unique=True,
        postgresql_where=sa.text("is_current"), sqlite_where=sa.text("is_current = 1"),
    )
    op.create_table(
        "sharing_sessions",
        sa.Column("session_id", sa.Uuid(), primary_key=True),
        sa.Column("friendship_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["friendship_id"], ["friendships.friendship_id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id", "friendship_id"],
            ["sharing_permissions.permission_id", "sharing_permissions.friendship_id"],
            name="fk_sessions_exact_permission", ondelete="CASCADE",
        ),
        sa.CheckConstraint("scope IN ('PRESENCE', 'APPROXIMATE', 'PRECISE')", name="ck_sessions_scope"),
        sa.CheckConstraint("expires_at > started_at", name="ck_sessions_expiry"),
    )
    op.create_index("ix_sessions_expiry", "sharing_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_sessions_expiry", table_name="sharing_sessions")
    op.drop_table("sharing_sessions")
    op.drop_index("uq_permissions_current_direction", table_name="sharing_permissions")
    op.drop_table("sharing_permissions")
    op.drop_index("uq_friendships_active_pair", table_name="friendships")
    op.drop_table("friendships")
