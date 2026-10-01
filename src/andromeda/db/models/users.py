from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from andromeda.db.base import Base
from .common import UUIDPrimaryKeyMixin


class UserProfile(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_profile"
    __table_args__ = (
        CheckConstraint("school_grade IS NULL OR school_grade > 0", name="school_grade_positive"),
        CheckConstraint("graduation_year IS NULL OR graduation_year >= 1900", name="graduation_year_valid"),
        CheckConstraint(
            "principal_id IS NULL OR length(btrim(principal_id)) > 0", name="principal_id_not_blank"
        ),
    )

    principal_id: Mapped[str | None] = mapped_column(Text, unique=True)
    school_grade: Mapped[int | None] = mapped_column(Integer)
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(Text)


class UserExternalIdentity(UUIDPrimaryKeyMixin, Base):
    """An optional provider subject linked to a profile; this is not an auth system."""

    __tablename__ = "user_external_identity"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_user_external_identity_provider_subject"),
        UniqueConstraint("profile_id", "provider", name="uq_user_external_identity_profile_provider"),
        CheckConstraint("provider ~ '^[a-z][a-z0-9_]*$'", name="provider_code_valid"),
        CheckConstraint("length(btrim(provider_subject)) > 0", name="provider_subject_not_blank"),
        Index("ix_user_external_identity_profile", "profile_id"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_subject: Mapped[str] = mapped_column(Text, nullable=False)


class AchievementType(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "achievement_type"
    __table_args__ = (
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class AchievementPolicy(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "achievement_policy"
    __table_args__ = (
        UniqueConstraint("campaign_id", "achievement_type_id", name="uq_achievement_policy_campaign_type"),
        CheckConstraint("additional_points >= 0", name="additional_points_nonnegative"),
        CheckConstraint(
            "max_awards_per_profile IS NULL OR max_awards_per_profile > 0",
            name="max_awards_per_profile_positive",
        ),
        Index("ix_achievement_policy_achievement_type", "achievement_type_id"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admission_campaign.id", ondelete="RESTRICT"), nullable=False
    )
    achievement_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("achievement_type.id", ondelete="RESTRICT"), nullable=False
    )
    additional_points: Mapped[Decimal] = mapped_column(Numeric(7, 3), nullable=False)
    max_awards_per_profile: Mapped[int | None] = mapped_column(Integer)


class UserAchievement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_achievement"
    __table_args__ = (
        CheckConstraint(
            "external_reference IS NULL OR length(btrim(external_reference)) > 0",
            name="external_reference_not_blank",
        ),
        Index("ix_user_achievement_profile_type", "profile_id", "achievement_type_id"),
        Index("ix_user_achievement_type", "achievement_type_id"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id", ondelete="RESTRICT"), nullable=False
    )
    achievement_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("achievement_type.id", ondelete="RESTRICT"), nullable=False
    )
    achieved_on: Mapped[date | None] = mapped_column(Date)
    external_reference: Mapped[str | None] = mapped_column(Text)


class UserExam(Base):
    __tablename__ = "user_exam"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="score_in_range"),
        Index("ix_user_exam_exam", "exam_id"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id", ondelete="RESTRICT"), primary_key=True
    )
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam.id", ondelete="RESTRICT"), primary_key=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(7, 3), nullable=False)


class UserOlympiad(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_olympiad"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "olympiad_profile_id", "year", name="uq_user_olympiad_profile_olympiad_year"
        ),
        CheckConstraint("year >= 1900", name="year_valid"),
        Index("ix_user_olympiad_olympiad_profile", "olympiad_profile_id"),
        Index("ix_user_olympiad_result_type", "result_type_id"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id", ondelete="RESTRICT"), nullable=False
    )
    olympiad_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("olympiad_profile.id", ondelete="RESTRICT"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    result_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("olympiad_result_type.id", ondelete="RESTRICT"), nullable=False
    )


class UserShortlist(Base):
    __tablename__ = "user_shortlist"
    __table_args__ = (Index("ix_user_shortlist_offering", "offering_id"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id", ondelete="CASCADE"), primary_key=True
    )
    offering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("program_offering.id", ondelete="CASCADE"), primary_key=True
    )


class UserQuota(Base):
    __tablename__ = "user_quota"
    __table_args__ = (
        Index("ix_user_quota_campaign_quota", "campaign_id", "quota_type_id"),
        Index("ix_user_quota_quota_type", "quota_type_id"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_profile.id", ondelete="RESTRICT"), primary_key=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admission_campaign.id", ondelete="RESTRICT"), primary_key=True
    )
    quota_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quota_type.id", ondelete="RESTRICT"), primary_key=True
    )
