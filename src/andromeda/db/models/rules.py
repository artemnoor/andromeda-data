from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from andromeda.db.base import Base
from .common import CodeNameMixin, UUIDPrimaryKeyMixin


class PolicyRuleType(UUIDPrimaryKeyMixin, CodeNameMixin, Base):
    __tablename__ = "policy_rule_type"


class PolicyRule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "policy_rule"
    __table_args__ = (
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        Index("ix_policy_rule_rule_type", "rule_type_id"),
    )

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rule_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy_rule_type.id", ondelete="RESTRICT"), nullable=False
    )


class PolicyRuleVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "policy_rule_version"
    __table_args__ = (
        UniqueConstraint("rule_id", "version", name="uq_policy_rule_version_rule_version"),
        UniqueConstraint("id", "rule_id", name="uq_policy_rule_version_id_rule"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("status IN ('draft', 'published')", name="status_valid"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="validity_ordered"),
        Index(
            "ix_policy_rule_version_published_validity",
            "valid_from",
            "valid_to",
            postgresql_where=text("status = 'published'"),
        ),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy_rule.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))


class RuleSet(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rule_set"
    __table_args__ = (
        UniqueConstraint("campaign_id", "name", "version", name="uq_rule_set_campaign_name_version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("status IN ('draft', 'published')", name="status_valid"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admission_campaign.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))


class RuleSetMember(Base):
    __tablename__ = "rule_set_member"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_version_id", "rule_id"],
            ["policy_rule_version.id", "policy_rule_version.rule_id"],
            name="fk_rule_set_member_version_rule",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("rule_set_id", "rule_id", name="uq_rule_set_member_one_version_per_rule"),
        Index("ix_rule_set_member_rule_version", "rule_version_id", "rule_id"),
    )

    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rule_set.id", ondelete="RESTRICT"), primary_key=True
    )
    rule_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
