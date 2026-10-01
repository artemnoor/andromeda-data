from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.migration


def _alembic(*arguments: str) -> None:
    environment = os.environ.copy()
    if not environment.get("DATABASE_URL"):
        pytest.fail("DATABASE_URL must point to a disposable PostgreSQL test database")
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        text=True,
    )


def test_clean_database_upgrade_check_downgrade_and_repeat() -> None:
    """Exercise the real migration path, including a second fresh install."""
    _alembic("upgrade", "head")
    _alembic("check")
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")
    _alembic("check")
