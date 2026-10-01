from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from andromeda.db.base import Base
from .common import CodeNameMixin, UUIDPrimaryKeyMixin


class FundingType(UUIDPrimaryKeyMixin, CodeNameMixin, Base):
    __tablename__ = "funding_type"


class QuotaType(UUIDPrimaryKeyMixin, CodeNameMixin, Base):
    __tablename__ = "quota_type"


class BenefitType(UUIDPrimaryKeyMixin, CodeNameMixin, Base):
    __tablename__ = "benefit_type"


class OlympiadResultType(UUIDPrimaryKeyMixin, CodeNameMixin, Base):
    __tablename__ = "olympiad_result_type"


class University(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "university"
    __table_args__ = (
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)


class Department(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "department"
    __table_args__ = (
        UniqueConstraint("university_id", "code", name="uq_department_university_code"),
        UniqueConstraint("id", "university_id", name="uq_department_id_university"),
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    university_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("university.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Program(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "program"
    __table_args__ = (
        UniqueConstraint("university_id", "code", name="uq_program_university_code"),
        UniqueConstraint("id", "university_id", name="uq_program_id_university"),
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("duration_months > 0", name="duration_months_positive"),
    )

    university_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("university.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    degree_level: Mapped[str] = mapped_column(Text, nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class ProgramDepartment(Base):
    __tablename__ = "program_department"
    __table_args__ = (
        ForeignKeyConstraint(
            ["program_id", "university_id"],
            ["program.id", "program.university_id"],
            name="fk_program_department_program_university",
            ondelete="CASCADE",
        ),
        Index("ix_program_department_program_university", "program_id", "university_id"),
        Index("ix_program_department_department_university", "department_id", "university_id"),
        ForeignKeyConstraint(
            ["department_id", "university_id"],
            ["department.id", "department.university_id"],
            name="fk_program_department_department_university",
            ondelete="CASCADE",
        ),
    )

    program_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    university_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AdmissionCampaign(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "admission_campaign"
    __table_args__ = (
        UniqueConstraint("university_id", "year", name="uq_admission_campaign_university_year"),
        UniqueConstraint("id", "university_id", name="uq_admission_campaign_id_university"),
        CheckConstraint("year >= 1900", name="year_valid"),
        CheckConstraint(
            "application_start IS NULL OR application_end IS NULL OR application_end >= application_start",
            name="application_dates_ordered",
        ),
    )

    university_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("university.id", ondelete="RESTRICT"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    application_start: Mapped[date | None] = mapped_column(Date)
    application_end: Mapped[date | None] = mapped_column(Date)


class ProgramOffering(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "program_offering"
    __table_args__ = (
        ForeignKeyConstraint(
            ["program_id", "university_id"],
            ["program.id", "program.university_id"],
            name="fk_program_offering_program_university",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "university_id"],
            ["admission_campaign.id", "admission_campaign.university_id"],
            name="fk_program_offering_campaign_university",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "program_id", "campaign_id", "study_form", "language", name="uq_program_offering_business_key"
        ),
        CheckConstraint("length(btrim(study_form)) > 0", name="study_form_not_blank"),
        CheckConstraint("length(btrim(language)) > 0", name="language_not_blank"),
        Index("ix_program_offering_program_university", "program_id", "university_id"),
        Index("ix_program_offering_campaign_university", "campaign_id", "university_id"),
    )

    program_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    university_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    study_form: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)


class CompetitionPool(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "competition_pool"
    __table_args__ = (
        UniqueConstraint(
            "offering_id", "funding_type_id", "quota_type_id", name="uq_competition_pool_business_key"
        ),
        CheckConstraint("places >= 0", name="places_nonnegative"),
        CheckConstraint("tuition_per_year IS NULL OR tuition_per_year >= 0", name="tuition_nonnegative"),
        Index("ix_competition_pool_funding_type", "funding_type_id"),
        Index("ix_competition_pool_quota_type", "quota_type_id"),
    )

    offering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("program_offering.id", ondelete="RESTRICT"), nullable=False
    )
    funding_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funding_type.id", ondelete="RESTRICT"), nullable=False
    )
    quota_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quota_type.id", ondelete="RESTRICT"), nullable=False
    )
    places: Mapped[int] = mapped_column(Integer, nullable=False)
    tuition_per_year: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class AdmissionStatistic(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "admission_statistic"
    __table_args__ = (
        UniqueConstraint("pool_id", "year", name="uq_admission_statistic_pool_year"),
        CheckConstraint("year >= 1900", name="year_valid"),
        CheckConstraint("passing_score IS NULL OR passing_score >= 0", name="passing_score_nonnegative"),
        CheckConstraint("average_score IS NULL OR average_score >= 0", name="average_score_nonnegative"),
        CheckConstraint("enrolled_count IS NULL OR enrolled_count >= 0", name="enrolled_count_nonnegative"),
    )

    pool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competition_pool.id", ondelete="RESTRICT"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    passing_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    average_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    enrolled_count: Mapped[int | None] = mapped_column(Integer)


class Exam(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exam"
    __table_args__ = (
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementSet(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "requirement_set"
    __table_args__ = (
        UniqueConstraint("offering_id", "name", name="uq_requirement_set_offering_name"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    offering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("program_offering.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementNode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "requirement_node"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_set_id", "parent_node_id"],
            ["requirement_node.requirement_set_id", "requirement_node.id"],
            name="fk_requirement_node_parent_same_set",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("requirement_set_id", "id", name="uq_requirement_node_set_id"),
        CheckConstraint("node_type IN ('exam', 'operator')", name="node_type_valid"),
        CheckConstraint("operator_type IS NULL OR operator_type IN ('and', 'or', 'at_least')", name="operator_type_valid"),
        CheckConstraint(
            "(node_type = 'exam' AND exam_id IS NOT NULL AND operator_type IS NULL AND min_count IS NULL) "
            "OR (node_type = 'operator' AND exam_id IS NULL AND operator_type IS NOT NULL AND min_score IS NULL "
            "AND ((operator_type = 'at_least' AND min_count IS NOT NULL AND min_count > 0) "
            "OR (operator_type IN ('and', 'or') AND min_count IS NULL)))",
            name="node_shape_valid",
        ),
        CheckConstraint("min_score IS NULL OR min_score >= 0", name="min_score_nonnegative"),
        CheckConstraint("parent_node_id IS NULL OR parent_node_id <> id", name="not_own_parent"),
        Index(
            "uq_requirement_node_single_root",
            "requirement_set_id",
            unique=True,
            postgresql_where=text("parent_node_id IS NULL"),
        ),
        Index("ix_requirement_node_set_parent", "requirement_set_id", "parent_node_id"),
        Index("ix_requirement_node_parent", "parent_node_id"),
        Index("ix_requirement_node_exam", "exam_id"),
    )

    requirement_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirement_set.id", ondelete="RESTRICT"), nullable=False
    )
    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    exam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam.id", ondelete="RESTRICT")
    )
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    operator_type: Mapped[str | None] = mapped_column(Text)
    min_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    min_count: Mapped[int | None] = mapped_column(Integer)
