from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from andromeda.db.base import Base
from .common import UUIDPrimaryKeyMixin


class OntologyObjectType(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ontology_object_type"
    __table_args__ = (
        UniqueConstraint("api_name", name="uq_ontology_object_type_api_name"),
        CheckConstraint("api_name ~ '^[a-z][a-z0-9_]*$'", name="api_name_snake_case"),
        CheckConstraint("length(btrim(display_name)) > 0", name="display_name_not_blank"),
    )

    api_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    backing_table: Mapped[str | None] = mapped_column(Text)


class OntologyPropertyType(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ontology_property_type"
    __table_args__ = (
        UniqueConstraint("object_type_id", "api_name", name="uq_ontology_property_type_object_api"),
        UniqueConstraint("id", "object_type_id", name="uq_ontology_property_type_id_object_type"),
        CheckConstraint("api_name ~ '^[a-z][a-z0-9_]*$'", name="api_name_snake_case"),
        CheckConstraint(
            "data_type IN ('string', 'integer', 'decimal', 'boolean', 'date', 'datetime', 'json', 'uuid')",
            name="data_type_valid",
        ),
    )

    object_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ontology_object_type.id", ondelete="RESTRICT"), nullable=False
    )
    api_name: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)


class OntologyLinkType(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ontology_link_type"
    __table_args__ = (
        UniqueConstraint("api_name", name="uq_ontology_link_type_api_name"),
        UniqueConstraint(
            "id", "source_type_id", "target_type_id", name="uq_ontology_link_type_id_endpoints"
        ),
        CheckConstraint("api_name ~ '^[a-z][a-z0-9_]*$'", name="api_name_snake_case"),
        CheckConstraint(
            "cardinality IN ('one_to_one', 'one_to_many', 'many_to_one', 'many_to_many')",
            name="cardinality_valid",
        ),
        Index("ix_ontology_link_type_source_type", "source_type_id"),
        Index("ix_ontology_link_type_target_type", "target_type_id"),
    )

    source_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ontology_object_type.id", ondelete="RESTRICT"), nullable=False
    )
    target_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ontology_object_type.id", ondelete="RESTRICT"), nullable=False
    )
    api_name: Mapped[str] = mapped_column(Text, nullable=False)
    cardinality: Mapped[str] = mapped_column(Text, nullable=False)


class ObjectRef(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "object_ref"
    __table_args__ = (
        UniqueConstraint("object_type_id", "primary_key_value", name="uq_object_ref_type_primary_key"),
        UniqueConstraint("id", "object_type_id", name="uq_object_ref_id_type"),
        CheckConstraint("length(btrim(primary_key_value)) > 0", name="primary_key_value_not_blank"),
    )

    object_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ontology_object_type.id", ondelete="RESTRICT"), nullable=False
    )
    primary_key_value: Mapped[str] = mapped_column(Text, nullable=False)


class FactAssertion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fact_assertion"
    __table_args__ = (
        ForeignKeyConstraint(
            ["object_ref_id", "object_type_id"],
            ["object_ref.id", "object_ref.object_type_id"],
            name="fk_fact_assertion_object_ref_type",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["property_type_id", "object_type_id"],
            ["ontology_property_type.id", "ontology_property_type.object_type_id"],
            name="fk_fact_assertion_property_object_type",
            ondelete="RESTRICT",
        ),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="validity_ordered"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_in_range"),
        Index("ix_fact_assertion_source_artifact", "source_artifact_id"),
        Index("ix_fact_assertion_object_ref_type", "object_ref_id", "object_type_id"),
        Index("ix_fact_assertion_object_property_time", "object_ref_id", "property_type_id", "valid_from"),
        Index(
            "ix_fact_assertion_active_object_property",
            "object_ref_id",
            "property_type_id",
            postgresql_where=text("valid_to IS NULL"),
        ),
        Index("ix_fact_assertion_property_object_type", "property_type_id", "object_type_id"),
    )

    object_ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    object_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_artifact.id", ondelete="RESTRICT"), nullable=False
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)


class LinkAssertion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "link_assertion"
    __table_args__ = (
        ForeignKeyConstraint(
            ["link_type_id", "source_type_id", "target_type_id"],
            [
                "ontology_link_type.id",
                "ontology_link_type.source_type_id",
                "ontology_link_type.target_type_id",
            ],
            name="fk_link_assertion_link_type_endpoints",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_object_id", "source_type_id"],
            ["object_ref.id", "object_ref.object_type_id"],
            name="fk_link_assertion_source_object_type",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_object_id", "target_type_id"],
            ["object_ref.id", "object_ref.object_type_id"],
            name="fk_link_assertion_target_object_type",
            ondelete="RESTRICT",
        ),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="validity_ordered"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_in_range"),
        Index("ix_link_assertion_source_artifact", "source_artifact_id"),
        Index("ix_link_assertion_link_type_endpoints", "link_type_id", "source_type_id", "target_type_id"),
        Index("ix_link_assertion_link_source_target_time", "link_type_id", "source_object_id", "target_object_id", "valid_from"),
        Index(
            "ix_link_assertion_active_link_source_target",
            "link_type_id",
            "source_object_id",
            "target_object_id",
            postgresql_where=text("valid_to IS NULL"),
        ),
        Index("ix_link_assertion_source_type", "source_object_id", "source_type_id"),
        Index("ix_link_assertion_target_type", "target_object_id", "target_type_id"),
    )

    link_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_artifact.id", ondelete="RESTRICT"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
