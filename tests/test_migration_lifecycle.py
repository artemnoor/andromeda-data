from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

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

    # Build representative rows in the previous schema. The new revision must
    # backfill a concrete department-specific track without guessing.
    _alembic("downgrade", "a4e2c7d9015b")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as connection:
        university_id = connection.execute(
            text("INSERT INTO university (code, name) VALUES ('migration_uni', 'Migration University') RETURNING id")
        ).scalar_one()
        department_id = connection.execute(
            text(
                "INSERT INTO department (university_id, code, name) "
                "VALUES (:university_id, 'd1', 'Department One') RETURNING id"
            ),
            {"university_id": university_id},
        ).scalar_one()
        program_id = connection.execute(
            text(
                "INSERT INTO program (university_id, code, name, degree_level, duration_months) "
                "VALUES (:university_id, '09.03.01', 'Computing direction', 'bachelor', 48) RETURNING id"
            ),
            {"university_id": university_id},
        ).scalar_one()
        campaign_id = connection.execute(
            text(
                "INSERT INTO admission_campaign (university_id, year) "
                "VALUES (:university_id, 2026) RETURNING id"
            ),
            {"university_id": university_id},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO program_department (program_id, department_id, university_id) "
                "VALUES (:program_id, :department_id, :university_id)"
            ),
            {
                "program_id": program_id,
                "department_id": department_id,
                "university_id": university_id,
            },
        )
        connection.execute(
            text(
                "INSERT INTO program_offering "
                "(program_id, campaign_id, university_id, study_form, language) "
                "VALUES (:program_id, :campaign_id, :university_id, 'full_time', 'ru')"
            ),
            {
                "program_id": program_id,
                "campaign_id": campaign_id,
                "university_id": university_id,
            },
        )
        connection.execute(
            text(
                "INSERT INTO curriculum (program_id, version, start_year) "
                "VALUES (:program_id, '2026', 2026)"
            ),
            {"program_id": program_id},
        )
    engine.dispose()

    _alembic("upgrade", "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        offering_track = connection.execute(
            text(
                "SELECT ep.id, ep.name, ep.duration_months, ep.department_id "
                "FROM program_offering AS po "
                "JOIN educational_program AS ep ON ep.id = po.educational_program_id "
                "WHERE po.program_id = :program_id"
            ),
            {"program_id": program_id},
        ).one()
        curriculum_track_id = connection.execute(
            text("SELECT educational_program_id FROM curriculum WHERE program_id = :program_id"),
            {"program_id": program_id},
        ).scalar_one()
        assert offering_track.id == curriculum_track_id
        assert offering_track.name == "Computing direction"
        assert offering_track.duration_months == 48
        assert offering_track.department_id == department_id
    engine.dispose()

    _alembic("check")
    _alembic("downgrade", "a4e2c7d9015b")
    _alembic("upgrade", "head")
    _alembic("check")
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")
    _alembic("check")
