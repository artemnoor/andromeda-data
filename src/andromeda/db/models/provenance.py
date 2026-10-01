from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from andromeda.db.base import Base
from .common import CodeNameMixin, UUIDPrimaryKeyMixin


class SourceType(UUIDPrimaryKeyMixin, CodeNameMixin, Base):
    __tablename__ = "source_type"


class Source(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        Index("ix_source_source_type", "source_type_id"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_type.id", ondelete="RESTRICT"), nullable=False
    )
    url: Mapped[str | None] = mapped_column(Text)


class SourceArtifact(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_artifact"
    __table_args__ = (
        UniqueConstraint("source_id", "checksum", name="uq_source_artifact_source_checksum"),
        CheckConstraint("length(btrim(checksum)) > 0", name="checksum_not_blank"),
        Index("ix_source_artifact_source_retrieved_at", "source_id", "retrieved_at"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
