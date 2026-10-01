from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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
from .admissions import BenefitType, OlympiadResultType
from .common import UUIDPrimaryKeyMixin


class Olympiad(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "olympiad"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("level > 0", name="level_positive"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    organizer: Mapped[str | None] = mapped_column(Text)
    level: Mapped[int] = mapped_column(Integer, nullable=False)


class OlympiadProfile(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "olympiad_profile"
    __table_args__ = (
        UniqueConstraint("olympiad_id", "name", name="uq_olympiad_profile_olympiad_name"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    olympiad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("olympiad.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)


class OlympiadBenefit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "olympiad_benefit"
    __table_args__ = (
        UniqueConstraint(
            "olympiad_profile_id",
            "offering_id",
            "result_type_id",
            "benefit_type_id",
            name="uq_olympiad_benefit_business_key",
        ),
        CheckConstraint(
            "confirmation_score IS NULL OR (confirmation_score >= 0 AND confirmation_score <= 100)",
            name="confirmation_score_in_range",
        ),
        Index("ix_olympiad_benefit_offering", "offering_id"),
        Index("ix_olympiad_benefit_result_type", "result_type_id"),
        Index("ix_olympiad_benefit_benefit_type", "benefit_type_id"),
    )

    olympiad_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("olympiad_profile.id", ondelete="RESTRICT"), nullable=False
    )
    offering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("program_offering.id", ondelete="RESTRICT"), nullable=False
    )
    result_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("olympiad_result_type.id", ondelete="RESTRICT"), nullable=False
    )
    benefit_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benefit_type.id", ondelete="RESTRICT"), nullable=False
    )
    confirmation_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))


class Curriculum(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "curriculum"
    __table_args__ = (
        UniqueConstraint("program_id", "version", name="uq_curriculum_program_version"),
        CheckConstraint("length(btrim(version)) > 0", name="version_not_blank"),
        CheckConstraint("start_year >= 1900", name="start_year_valid"),
    )

    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("program.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)


class SubjectArea(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "subject_area"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_own_parent"),
        Index("ix_subject_area_parent", "parent_id"),
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject_area.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Course(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "course"
    __table_args__ = (
        UniqueConstraint("subject_area_id", "name", name="uq_course_subject_area_name"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    subject_area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject_area.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class CurriculumItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "curriculum_item"
    __table_args__ = (
        UniqueConstraint("curriculum_id", "course_id", "semester", name="uq_curriculum_item_course_semester"),
        CheckConstraint("semester > 0", name="semester_positive"),
        CheckConstraint("credits >= 0", name="credits_nonnegative"),
        CheckConstraint("total_hours >= 0", name="total_hours_nonnegative"),
        CheckConstraint("lecture_hours >= 0", name="lecture_hours_nonnegative"),
        CheckConstraint("practice_hours >= 0", name="practice_hours_nonnegative"),
        CheckConstraint("lab_hours >= 0", name="lab_hours_nonnegative"),
        CheckConstraint(
            "lecture_hours + practice_hours + lab_hours <= total_hours", name="contact_hours_within_total"
        ),
        Index("ix_curriculum_item_course", "course_id"),
    )

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course.id", ondelete="RESTRICT"), nullable=False
    )
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    credits: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    total_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    lecture_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    practice_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    lab_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    assessment_type: Mapped[str] = mapped_column(Text, nullable=False)
