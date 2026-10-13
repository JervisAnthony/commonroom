"""Minimal relationship/consent/session metadata; no observed location data."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean, CheckConstraint, Computed, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, String, UniqueConstraint, Uuid, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FriendshipModel(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("user_a_id < user_b_id", name="ck_friendships_canonical_pair"),
        UniqueConstraint("friendship_id", "user_a_id", "user_b_id", name="uq_friendships_members"),
        Index(
            "uq_friendships_active_pair", "user_a_id", "user_b_id", unique=True,
            postgresql_where=text("is_active"), sqlite_where=text("is_active = 1"),
        ),
    )

    friendship_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_a_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    user_b_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SharingPermissionModel(Base):
    """Each row is a distinct explicit grant; only one row per direction is current."""

    __tablename__ = "sharing_permissions"
    __table_args__ = (
        CheckConstraint("sharer_user_id <> recipient_user_id", name="ck_permissions_distinct_parties"),
        CheckConstraint("scope IN ('PRESENCE', 'APPROXIMATE', 'PRECISE')", name="ck_permissions_scope"),
        CheckConstraint("expires_at IS NULL OR expires_at > granted_at", name="ck_permissions_expiry"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= granted_at", name="ck_permissions_revocation"),
        ForeignKeyConstraint(
            ["friendship_id", "member_a_id", "member_b_id"],
            ["friendships.friendship_id", "friendships.user_a_id", "friendships.user_b_id"],
            name="fk_permissions_friendship_members", ondelete="CASCADE",
        ),
        UniqueConstraint("permission_id", "friendship_id", name="uq_permissions_friendship"),
        Index(
            "uq_permissions_current_direction", "friendship_id", "sharer_user_id",
            "recipient_user_id", unique=True,
            postgresql_where=text("is_current"), sqlite_where=text("is_current = 1"),
        ),
    )

    permission_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    friendship_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    sharer_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    recipient_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    # Derived solely for DB-enforced unordered friendship membership, never accepted input.
    member_a_id: Mapped[UUID] = mapped_column(Uuid, Computed(
        "CASE WHEN sharer_user_id < recipient_user_id THEN sharer_user_id ELSE recipient_user_id END",
        persisted=True,
    ))
    member_b_id: Mapped[UUID] = mapped_column(Uuid, Computed(
        "CASE WHEN sharer_user_id < recipient_user_id THEN recipient_user_id ELSE sharer_user_id END",
        persisted=True,
    ))
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SharingSessionModel(Base):
    __tablename__ = "sharing_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["permission_id", "friendship_id"],
            ["sharing_permissions.permission_id", "sharing_permissions.friendship_id"],
            name="fk_sessions_exact_permission", ondelete="CASCADE",
        ),
        CheckConstraint("scope IN ('PRESENCE', 'APPROXIMATE', 'PRECISE')", name="ck_sessions_scope"),
        CheckConstraint("expires_at > started_at", name="ck_sessions_expiry"),
        Index("ix_sessions_expiry", "expires_at"),
    )

    session_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    friendship_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey(
        "friendships.friendship_id", ondelete="CASCADE"
    ), nullable=False)
    permission_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
