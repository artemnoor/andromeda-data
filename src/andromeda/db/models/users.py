from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from andromeda.db.base import Base
from .common import UUIDPrimaryKeyMixin


class UserProfile(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_profile"
    __table_args__ = (
        CheckConstraint("school_grade IS NULL OR school_grade > 0", name="school_grade_positive"),
        CheckConstraint("graduation_year IS NULL OR graduation_year >= 1900", name="graduation_year_valid"),
    )

    school_grade: Mapped[int | None] = mapped_column(Integer)
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(Text)


class UserExam(Base):
    __tablename__ = "user_exam"
    __table_args__ = (
        CheckConstraint("score >= 0", name="score_nonnegative"),
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
