from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine


def create_db_engine(database_url: str | None = None, **kwargs: object) -> Engine:
    """Create the synchronous SQLAlchemy engine using DATABASE_URL by default."""
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set before creating the database engine")
    return create_engine(url, pool_pre_ping=True, **kwargs)
