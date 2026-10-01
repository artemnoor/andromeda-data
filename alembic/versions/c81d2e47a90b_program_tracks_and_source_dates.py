"""Add concrete educational programs and preserve unknown statistic dates.

Revision ID: c81d2e47a90b
Revises: a4e2c7d9015b
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c81d2e47a90b"
down_revision: Union[str, None] = "a4e2c7d9015b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Legacy offerings/curricula only point to a direction. Backfill a concrete
    # track only when the old department link identifies exactly one department;
    # never guess when the old schema is ambiguous.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT p.id
                FROM program AS p
                WHERE (
                    EXISTS (SELECT 1 FROM program_offering AS po WHERE po.program_id = p.id)
                    OR EXISTS (SELECT 1 FROM curriculum AS c WHERE c.program_id = p.id)
                )
                AND (
                    SELECT count(*) FROM program_department AS pd WHERE pd.program_id = p.id
                ) <> 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot infer track department for legacy offerings/curricula; map each row before upgrading';
            END IF;
        END;
        $$;
        """
    )

    op.alter_column("program", "duration_months", existing_type=sa.Integer(), nullable=True)

    op.create_table(
        "educational_program",
        sa.Column("program_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("university_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name=op.f("ck_educational_program_name_not_blank")),
        sa.CheckConstraint("duration_months > 0", name=op.f("ck_educational_program_duration_months_positive")),
        sa.ForeignKeyConstraint(
            ["program_id", "university_id"],
            ["program.id", "program.university_id"],
            name="fk_educational_program_program_university",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id", "university_id"],
            ["department.id", "department.university_id"],
            name="fk_educational_program_department_university",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_educational_program")),
        sa.UniqueConstraint(
            "program_id", "department_id", "name", name="uq_educational_program_track"
        ),
        sa.UniqueConstraint(
            "id", "program_id", "university_id", name="uq_educational_program_id_program_university"
        ),
        sa.UniqueConstraint("id", "program_id", name="uq_educational_program_id_program"),
    )
    op.create_index(
        "ix_educational_program_program_university",
        "educational_program",
        ["program_id", "university_id"],
    )
    op.create_index(
        "ix_educational_program_department_university",
        "educational_program",
        ["department_id", "university_id"],
    )

    op.execute(
        """
        CREATE TEMPORARY TABLE _educational_program_backfill ON COMMIT DROP AS
        SELECT gen_random_uuid() AS educational_program_id,
               p.id AS program_id,
               pd.department_id,
               p.university_id,
               p.name,
               p.duration_months,
               p.description
        FROM program_department AS pd
        JOIN program AS p ON p.id = pd.program_id;
        """
    )
    op.execute(
        """
        INSERT INTO educational_program (
            id, program_id, department_id, university_id, name, duration_months, description
        )
        SELECT educational_program_id, program_id, department_id, university_id,
               name, duration_months, description
        FROM _educational_program_backfill;
        """
    )

    op.add_column("program_offering", sa.Column("educational_program_id", sa.UUID(), nullable=True))
    op.execute(
        """
        UPDATE program_offering AS po
        SET educational_program_id = ep.educational_program_id
        FROM _educational_program_backfill AS ep
        WHERE ep.program_id = po.program_id;
        """
    )
    op.alter_column("program_offering", "educational_program_id", existing_type=sa.UUID(), nullable=False)
    op.drop_constraint("uq_program_offering_business_key", "program_offering", type_="unique")
    op.create_unique_constraint(
        "uq_program_offering_business_key",
        "program_offering",
        ["educational_program_id", "campaign_id", "study_form", "language"],
    )
    op.create_foreign_key(
        "fk_program_offering_educational_program_context",
        "program_offering",
        "educational_program",
        ["educational_program_id", "program_id", "university_id"],
        ["id", "program_id", "university_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_program_offering_educational_program_context",
        "program_offering",
        ["educational_program_id", "program_id", "university_id"],
    )

    op.add_column("curriculum", sa.Column("educational_program_id", sa.UUID(), nullable=True))
    op.execute(
        """
        UPDATE curriculum AS c
        SET educational_program_id = ep.educational_program_id
        FROM _educational_program_backfill AS ep
        WHERE ep.program_id = c.program_id;
        """
    )
    op.alter_column("curriculum", "educational_program_id", existing_type=sa.UUID(), nullable=False)
    op.drop_constraint("uq_curriculum_program_version", "curriculum", type_="unique")
    op.create_unique_constraint(
        "uq_curriculum_educational_program_version",
        "curriculum",
        ["educational_program_id", "version"],
    )
    op.create_foreign_key(
        "fk_curriculum_educational_program_context",
        "curriculum",
        "educational_program",
        ["educational_program_id", "program_id"],
        ["id", "program_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_curriculum_program_id",
        "curriculum",
        ["program_id"],
    )
    op.create_index(
        "ix_curriculum_educational_program_context",
        "curriculum",
        ["educational_program_id", "program_id"],
    )

    # An absent source date stays NULL. At most one undated record per pool is
    # allowed, while separately dated observations remain uniquely addressable.
    op.drop_constraint(
        "uq_admission_statistic_pool_snapshot_date", "admission_statistic", type_="unique"
    )
    op.alter_column("admission_statistic", "snapshot_date", existing_type=sa.Date(), nullable=True)
    op.create_index(
        "uq_admission_statistic_pool_snapshot_date",
        "admission_statistic",
        ["pool_id", "snapshot_date"],
        unique=True,
        postgresql_where=sa.text("snapshot_date IS NOT NULL"),
    )
    op.create_index(
        "uq_admission_statistic_pool_without_snapshot",
        "admission_statistic",
        ["pool_id"],
        unique=True,
        postgresql_where=sa.text("snapshot_date IS NULL"),
    )

    op.drop_constraint("uq_olympiad_benefit_business_key", "olympiad_benefit", type_="unique")
    op.add_column("olympiad_benefit", sa.Column("confirmation_exam_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_olympiad_benefit_confirmation_exam_id_exam",
        "olympiad_benefit",
        "exam",
        ["confirmation_exam_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_olympiad_benefit_confirmation_exam",
        "olympiad_benefit",
        ["confirmation_exam_id"],
    )
    op.create_index(
        "uq_olympiad_benefit_business_key_with_exam",
        "olympiad_benefit",
        ["olympiad_profile_id", "offering_id", "result_type_id", "benefit_type_id", "confirmation_exam_id"],
        unique=True,
        postgresql_where=sa.text("confirmation_exam_id IS NOT NULL"),
    )
    op.create_index(
        "uq_olympiad_benefit_business_key_without_exam",
        "olympiad_benefit",
        ["olympiad_profile_id", "offering_id", "result_type_id", "benefit_type_id"],
        unique=True,
        postgresql_where=sa.text("confirmation_exam_id IS NULL"),
    )


def downgrade() -> None:
    # Refuse a lossy downgrade when track-specific facts cannot be represented by
    # the old direction-level curriculum/offering keys or program fields.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM admission_statistic
                WHERE snapshot_date IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade statistics with unknown snapshot dates; supply real dates first';
            END IF;

            IF EXISTS (SELECT 1 FROM olympiad_benefit WHERE confirmation_exam_id IS NOT NULL) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: olympiad benefits contain confirmation exam data';
            END IF;

            IF EXISTS (
                SELECT program_id, campaign_id, study_form, language
                FROM program_offering
                GROUP BY program_id, campaign_id, study_form, language
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: multiple track offerings share a direction-level business key';
            END IF;

            IF EXISTS (
                SELECT program_id, version
                FROM curriculum
                GROUP BY program_id, version
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: multiple track curricula share a direction-level version';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM educational_program AS ep
                JOIN program AS p ON p.id = ep.program_id
                WHERE ep.name IS DISTINCT FROM p.name
                   OR ep.description IS DISTINCT FROM p.description
                   OR (p.duration_months IS NOT NULL AND ep.duration_months <> p.duration_months)
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: track-specific names, descriptions, or durations would be lost';
            END IF;

            IF EXISTS (
                SELECT p.id
                FROM program AS p
                LEFT JOIN educational_program AS ep ON ep.program_id = p.id
                GROUP BY p.id
                HAVING (p.duration_months IS NULL AND count(ep.id) = 0)
                    OR count(DISTINCT ep.duration_months) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: direction-level duration cannot be reconstructed without guessing';
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        """
        UPDATE program AS p
        SET duration_months = track.duration_months
        FROM (
            SELECT program_id, min(duration_months) AS duration_months
            FROM educational_program
            GROUP BY program_id
        ) AS track
        WHERE p.id = track.program_id AND p.duration_months IS NULL;
        """
    )
    op.execute(
        """
        INSERT INTO program_department (program_id, department_id, university_id)
        SELECT DISTINCT ep.program_id, ep.department_id, ep.university_id
        FROM educational_program AS ep
        ON CONFLICT (program_id, department_id) DO NOTHING;
        """
    )

    op.drop_index("uq_olympiad_benefit_business_key_without_exam", table_name="olympiad_benefit")
    op.drop_index("uq_olympiad_benefit_business_key_with_exam", table_name="olympiad_benefit")
    op.drop_index("ix_olympiad_benefit_confirmation_exam", table_name="olympiad_benefit")
    op.drop_constraint(
        "fk_olympiad_benefit_confirmation_exam_id_exam", "olympiad_benefit", type_="foreignkey"
    )
    op.drop_column("olympiad_benefit", "confirmation_exam_id")
    op.create_unique_constraint(
        "uq_olympiad_benefit_business_key",
        "olympiad_benefit",
        ["olympiad_profile_id", "offering_id", "result_type_id", "benefit_type_id"],
    )

    op.drop_index("uq_admission_statistic_pool_without_snapshot", table_name="admission_statistic")
    op.drop_index("uq_admission_statistic_pool_snapshot_date", table_name="admission_statistic")
    op.alter_column("admission_statistic", "snapshot_date", existing_type=sa.Date(), nullable=False)
    op.create_unique_constraint(
        "uq_admission_statistic_pool_snapshot_date",
        "admission_statistic",
        ["pool_id", "snapshot_date"],
    )

    op.drop_index("ix_curriculum_educational_program_context", table_name="curriculum")
    op.drop_index("ix_curriculum_program_id", table_name="curriculum")
    op.drop_constraint(
        "fk_curriculum_educational_program_context", "curriculum", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_curriculum_educational_program_version", "curriculum", type_="unique"
    )
    op.create_unique_constraint(
        "uq_curriculum_program_version", "curriculum", ["program_id", "version"]
    )
    op.drop_column("curriculum", "educational_program_id")

    op.drop_index("ix_program_offering_educational_program_context", table_name="program_offering")
    op.drop_constraint(
        "fk_program_offering_educational_program_context", "program_offering", type_="foreignkey"
    )
    op.drop_constraint("uq_program_offering_business_key", "program_offering", type_="unique")
    op.create_unique_constraint(
        "uq_program_offering_business_key",
        "program_offering",
        ["program_id", "campaign_id", "study_form", "language"],
    )
    op.drop_column("program_offering", "educational_program_id")

    op.drop_index("ix_educational_program_department_university", table_name="educational_program")
    op.drop_index("ix_educational_program_program_university", table_name="educational_program")
    op.drop_table("educational_program")
    op.alter_column("program", "duration_months", existing_type=sa.Integer(), nullable=False)
