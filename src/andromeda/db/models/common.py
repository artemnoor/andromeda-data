from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class CodeNameMixin:
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:
        return (
            CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
            CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        )
