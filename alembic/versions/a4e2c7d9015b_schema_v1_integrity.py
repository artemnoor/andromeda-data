"""Add profile achievements, scoped rules, snapshot stats, and published requirements.

Revision ID: a4e2c7d9015b
Revises: 7678848a9056
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4e2c7d9015b"
down_revision: Union[str, None] = "7678848a9056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The old integer year did not identify when a statistic was captured. Refuse to
    # invent dates for already-loaded rows; v1 is still pre-ingestion, so this is a
    # safe, explicit migration boundary rather than a silent semantic conversion.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM admission_statistic) THEN
                RAISE EXCEPTION
                    'Schema v1 statistics need real snapshot_date values before upgrading';
            END IF;
        END;
        $$;
        """
    )

    op.drop_constraint(op.f("uq_admission_statistic_pool_year"), "admission_statistic", type_="unique")
    op.drop_constraint(op.f("ck_admission_statistic_year_valid"), "admission_statistic", type_="check")
    op.drop_column("admission_statistic", "year")
    op.add_column("admission_statistic", sa.Column("snapshot_date", sa.Date(), nullable=False))
    op.create_unique_constraint(
        op.f("uq_admission_statistic_pool_snapshot_date"),
        "admission_statistic",
        ["pool_id", "snapshot_date"],
    )
    op.create_index(
        "ix_admission_statistic_snapshot_date", "admission_statistic", ["snapshot_date"]
    )

    op.add_column("user_profile", sa.Column("principal_id", sa.Text(), nullable=True))
    op.create_unique_constraint(op.f("uq_user_profile_principal_id"), "user_profile", ["principal_id"])
    op.create_check_constraint(
        op.f("ck_user_profile_principal_id_not_blank"),
        "user_profile",
        "principal_id IS NULL OR length(btrim(principal_id)) > 0",
    )

    op.create_table(
        "user_external_identity",
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_subject", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("provider ~ '^[a-z][a-z0-9_]*$'", name=op.f("ck_user_external_identity_provider_code_valid")),
        sa.CheckConstraint("length(btrim(provider_subject)) > 0", name=op.f("ck_user_external_identity_provider_subject_not_blank")),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["user_profile.id"],
            name=op.f("fk_user_external_identity_profile_id_user_profile"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_external_identity")),
        sa.UniqueConstraint("profile_id", "provider", name="uq_user_external_identity_profile_provider"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_user_external_identity_provider_subject"),
    )
    op.create_index("ix_user_external_identity_profile", "user_external_identity", ["profile_id"])

    op.create_table(
        "achievement_type",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("length(btrim(code)) > 0", name=op.f("ck_achievement_type_code_not_blank")),
        sa.CheckConstraint("length(btrim(name)) > 0", name=op.f("ck_achievement_type_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_achievement_type")),
        sa.UniqueConstraint("code", name=op.f("uq_achievement_type_code")),
    )
    op.create_table(
        "achievement_policy",
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("achievement_type_id", sa.UUID(), nullable=False),
        sa.Column("additional_points", sa.Numeric(precision=7, scale=3), nullable=False),
        sa.Column("max_awards_per_profile", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("additional_points >= 0", name=op.f("ck_achievement_policy_additional_points_nonnegative")),
        sa.CheckConstraint(
            "max_awards_per_profile IS NULL OR max_awards_per_profile > 0",
            name=op.f("ck_achievement_policy_max_awards_per_profile_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["achievement_type_id"], ["achievement_type.id"],
            name=op.f("fk_achievement_policy_achievement_type_id_achievement_type"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["admission_campaign.id"],
            name=op.f("fk_achievement_policy_campaign_id_admission_campaign"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_achievement_policy")),
        sa.UniqueConstraint("campaign_id", "achievement_type_id", name="uq_achievement_policy_campaign_type"),
    )
    op.create_index("ix_achievement_policy_achievement_type", "achievement_policy", ["achievement_type_id"])

    op.create_table(
        "user_achievement",
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("achievement_type_id", sa.UUID(), nullable=False),
        sa.Column("achieved_on", sa.Date(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "external_reference IS NULL OR length(btrim(external_reference)) > 0",
            name=op.f("ck_user_achievement_external_reference_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["achievement_type_id"], ["achievement_type.id"],
            name=op.f("fk_user_achievement_achievement_type_id_achievement_type"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["user_profile.id"],
            name=op.f("fk_user_achievement_profile_id_user_profile"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_achievement")),
    )
    op.create_index(
        "ix_user_achievement_profile_type", "user_achievement", ["profile_id", "achievement_type_id"]
    )
    op.create_index("ix_user_achievement_type", "user_achievement", ["achievement_type_id"])

    op.create_table(
        "user_quota",
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("quota_type_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["admission_campaign.id"],
            name=op.f("fk_user_quota_campaign_id_admission_campaign"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["user_profile.id"],
            name=op.f("fk_user_quota_profile_id_user_profile"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quota_type_id"], ["quota_type.id"],
            name=op.f("fk_user_quota_quota_type_id_quota_type"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("profile_id", "campaign_id", "quota_type_id", name=op.f("pk_user_quota")),
    )
    op.create_index("ix_user_quota_campaign_quota", "user_quota", ["campaign_id", "quota_type_id"])
    op.create_index("ix_user_quota_quota_type", "user_quota", ["quota_type_id"])

    op.drop_constraint(op.f("ck_user_exam_score_nonnegative"), "user_exam", type_="check")
    op.create_check_constraint(op.f("ck_user_exam_score_in_range"), "user_exam", "score >= 0 AND score <= 100")
    op.drop_constraint(op.f("ck_requirement_node_min_score_nonnegative"), "requirement_node", type_="check")
    op.create_check_constraint(
        op.f("ck_requirement_node_min_score_in_range"),
        "requirement_node",
        "min_score IS NULL OR (min_score >= 0 AND min_score <= 100)",
    )
    op.drop_constraint(
        op.f("ck_olympiad_benefit_confirmation_score_nonnegative"), "olympiad_benefit", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_olympiad_benefit_confirmation_score_in_range"),
        "olympiad_benefit",
        "confirmation_score IS NULL OR (confirmation_score >= 0 AND confirmation_score <= 100)",
    )

    op.add_column(
        "requirement_set",
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_requirement_set_status_valid"), "requirement_set", "status IN ('draft', 'published')"
    )

    op.create_table(
        "policy_rule_program_scope",
        sa.Column("rule_version_id", sa.UUID(), nullable=False),
        sa.Column("program_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["program_id"], ["program.id"],
            name=op.f("fk_policy_rule_program_scope_program_id_program"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"], ["policy_rule_version.id"],
            name=op.f("fk_policy_rule_program_scope_rule_version_id_policy_rule_version"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("rule_version_id", "program_id", name=op.f("pk_policy_rule_program_scope")),
    )
    op.create_index("ix_policy_rule_program_scope_program", "policy_rule_program_scope", ["program_id"])

    op.create_table(
        "policy_rule_offering_scope",
        sa.Column("rule_version_id", sa.UUID(), nullable=False),
        sa.Column("offering_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["offering_id"], ["program_offering.id"],
            name=op.f("fk_policy_rule_offering_scope_offering_id_program_offering"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"], ["policy_rule_version.id"],
            name=op.f("fk_policy_rule_offering_scope_rule_version_id_policy_rule_version"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("rule_version_id", "offering_id", name=op.f("pk_policy_rule_offering_scope")),
    )
    op.create_index("ix_policy_rule_offering_scope_offering", "policy_rule_offering_scope", ["offering_id"])

    # Draft trees may be incomplete. Validation and immutability move to the
    # draft -> published transition, with child writes serialized on the parent.
    op.execute("DROP TRIGGER trg_requirement_node_tree_valid ON requirement_node")
    op.execute("DROP FUNCTION andromeda_check_requirement_node_tree()")
    op.execute("DROP FUNCTION andromeda_validate_requirement_set(uuid)")
    op.execute(
        """
        CREATE FUNCTION andromeda_validate_requirement_set_for_publish(p_requirement_set_id uuid)
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        DECLARE
            node_count bigint;
            root_count bigint;
            has_cycle boolean;
            invalid_node uuid;
        BEGIN
            SELECT count(*), count(*) FILTER (WHERE parent_node_id IS NULL)
            INTO node_count, root_count
            FROM requirement_node
            WHERE requirement_set_id = p_requirement_set_id;

            IF node_count = 0 THEN
                RAISE EXCEPTION 'requirement set % is empty', p_requirement_set_id
                    USING ERRCODE = '23514';
            END IF;
            IF root_count <> 1 THEN
                RAISE EXCEPTION 'requirement set % must have exactly one root', p_requirement_set_id
                    USING ERRCODE = '23514';
            END IF;

            WITH RECURSIVE parent_walk(start_id, node_id, parent_node_id, path, cycle) AS (
                SELECT n.id, n.id, n.parent_node_id, ARRAY[n.id], false
                FROM requirement_node AS n
                WHERE n.requirement_set_id = p_requirement_set_id
                UNION ALL
                SELECT w.start_id, parent.id, parent.parent_node_id,
                       w.path || parent.id, parent.id = ANY(w.path)
                FROM parent_walk AS w
                JOIN requirement_node AS parent
                  ON parent.requirement_set_id = p_requirement_set_id
                 AND parent.id = w.parent_node_id
                WHERE w.parent_node_id IS NOT NULL AND NOT w.cycle
            )
            SELECT EXISTS (SELECT 1 FROM parent_walk WHERE cycle)
            INTO has_cycle;

            IF has_cycle THEN
                RAISE EXCEPTION 'requirement set % contains a cycle', p_requirement_set_id
                    USING ERRCODE = '23514';
            END IF;

            SELECT n.id
            INTO invalid_node
            FROM requirement_node AS n
            LEFT JOIN requirement_node AS child
              ON child.requirement_set_id = n.requirement_set_id
             AND child.parent_node_id = n.id
            WHERE n.requirement_set_id = p_requirement_set_id
            GROUP BY n.id, n.node_type, n.operator_type, n.min_count
            HAVING (n.node_type = 'exam' AND count(child.id) <> 0)
                OR (n.node_type = 'operator' AND n.operator_type IN ('and', 'or') AND count(child.id) < 2)
                OR (n.node_type = 'operator' AND n.operator_type = 'at_least' AND count(child.id) < n.min_count)
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION 'requirement node % has an invalid child count', invalid_node
                    USING ERRCODE = '23514';
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION andromeda_guard_requirement_set_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'draft' THEN
                    RAISE EXCEPTION 'requirement sets must be created as draft'
                        USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END IF;

            IF OLD.status = 'published' THEN
                RAISE EXCEPTION 'published requirement sets are immutable'
                    USING ERRCODE = '55000';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;

            IF NEW.status = 'published' THEN
                PERFORM andromeda_validate_requirement_set_for_publish(NEW.id);
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_requirement_set_lifecycle
        BEFORE INSERT OR UPDATE OR DELETE ON requirement_set
        FOR EACH ROW EXECUTE FUNCTION andromeda_guard_requirement_set_lifecycle();
        """
    )
    op.execute(
        """
        CREATE FUNCTION andromeda_guard_requirement_node_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            parent_set_id uuid;
            parent_status text;
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW.requirement_set_id <> OLD.requirement_set_id THEN
                RAISE EXCEPTION 'requirement nodes cannot be moved between sets'
                    USING ERRCODE = '55000';
            END IF;

            IF TG_OP = 'DELETE' THEN
                parent_set_id := OLD.requirement_set_id;
            ELSE
                parent_set_id := NEW.requirement_set_id;
            END IF;

            SELECT status INTO parent_status
            FROM requirement_set
            WHERE id = parent_set_id
            FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'requirement set % does not exist', parent_set_id
                    USING ERRCODE = '23503';
            END IF;
            IF parent_status = 'published' THEN
                RAISE EXCEPTION 'nodes of a published requirement set are immutable'
                    USING ERRCODE = '55000';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_requirement_node_lifecycle
        BEFORE INSERT OR UPDATE OR DELETE ON requirement_node
        FOR EACH ROW EXECUTE FUNCTION andromeda_guard_requirement_node_lifecycle();
        """
    )

    # Scoped versions are explicit rows. No rows means global in the campaign
    # selected by RULE_SET; program and offering scopes combine as a union.
    op.execute(
        """
        CREATE FUNCTION andromeda_guard_policy_rule_scope()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_rule_version_id uuid;
            version_status text;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'rule scopes are changed by delete and insert'
                    USING ERRCODE = '55000';
            END IF;

            IF TG_OP = 'DELETE' THEN
                target_rule_version_id := OLD.rule_version_id;
            ELSE
                target_rule_version_id := NEW.rule_version_id;
            END IF;

            SELECT status INTO version_status
            FROM policy_rule_version
            WHERE id = target_rule_version_id
            FOR UPDATE;

            IF NOT FOUND THEN
                -- ON DELETE CASCADE removes scopes after the draft version row
                -- itself has been deleted. A missing parent is only acceptable
                -- for that cascade; direct inserts still fail their foreign key.
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RAISE EXCEPTION 'policy rule version % does not exist', target_rule_version_id
                    USING ERRCODE = '23503';
            END IF;
            IF version_status = 'published' THEN
                RAISE EXCEPTION 'scopes of a published policy rule version are immutable'
                    USING ERRCODE = '55000';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_rule_program_scope_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON policy_rule_program_scope
        FOR EACH ROW EXECUTE FUNCTION andromeda_guard_policy_rule_scope();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_rule_offering_scope_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON policy_rule_offering_scope
        FOR EACH ROW EXECUTE FUNCTION andromeda_guard_policy_rule_scope();
        """
    )
    op.execute(
        """
        CREATE FUNCTION andromeda_validate_rule_set_member_scope()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_campaign_id uuid;
            has_any_scope boolean;
            matches_campaign boolean;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RETURN NEW;
            END IF;

            SELECT campaign_id INTO target_campaign_id
            FROM rule_set
            WHERE id = NEW.rule_set_id;

            SELECT EXISTS (
                SELECT 1 FROM policy_rule_program_scope WHERE rule_version_id = NEW.rule_version_id
                UNION ALL
                SELECT 1 FROM policy_rule_offering_scope WHERE rule_version_id = NEW.rule_version_id
            ) INTO has_any_scope;

            IF NOT has_any_scope THEN
                RETURN NEW;
            END IF;

            SELECT
                EXISTS (
                    SELECT 1
                    FROM policy_rule_program_scope AS scope
                    JOIN program_offering AS offering ON offering.program_id = scope.program_id
                    WHERE scope.rule_version_id = NEW.rule_version_id
                      AND offering.campaign_id = target_campaign_id
                )
                OR EXISTS (
                    SELECT 1
                    FROM policy_rule_offering_scope AS scope
                    JOIN program_offering AS offering ON offering.id = scope.offering_id
                    WHERE scope.rule_version_id = NEW.rule_version_id
                      AND offering.campaign_id = target_campaign_id
                )
            INTO matches_campaign;

            IF NOT matches_campaign THEN
                RAISE EXCEPTION
                    'scoped policy rule version % does not apply to campaign %',
                    NEW.rule_version_id, target_campaign_id
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_rule_set_member_scope_campaign
        BEFORE INSERT ON rule_set_member
        FOR EACH ROW EXECUTE FUNCTION andromeda_validate_rule_set_member_scope();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_rule_set_member_scope_campaign ON rule_set_member")
    op.execute("DROP TRIGGER trg_policy_rule_offering_scope_immutable ON policy_rule_offering_scope")
    op.execute("DROP TRIGGER trg_policy_rule_program_scope_immutable ON policy_rule_program_scope")
    op.execute("DROP TRIGGER trg_requirement_node_lifecycle ON requirement_node")
    op.execute("DROP TRIGGER trg_requirement_set_lifecycle ON requirement_set")
    op.execute("DROP FUNCTION andromeda_validate_rule_set_member_scope()")
    op.execute("DROP FUNCTION andromeda_guard_policy_rule_scope()")
    op.execute("DROP FUNCTION andromeda_guard_requirement_node_lifecycle()")
    op.execute("DROP FUNCTION andromeda_guard_requirement_set_lifecycle()")
    op.execute("DROP FUNCTION andromeda_validate_requirement_set_for_publish(uuid)")

    op.drop_index("ix_policy_rule_offering_scope_offering", table_name="policy_rule_offering_scope")
    op.drop_table("policy_rule_offering_scope")
    op.drop_index("ix_policy_rule_program_scope_program", table_name="policy_rule_program_scope")
    op.drop_table("policy_rule_program_scope")

    op.drop_constraint(op.f("ck_requirement_set_status_valid"), "requirement_set", type_="check")
    op.drop_column("requirement_set", "status")

    op.drop_index("ix_user_quota_quota_type", table_name="user_quota")
    op.drop_index("ix_user_quota_campaign_quota", table_name="user_quota")
    op.drop_table("user_quota")
    op.drop_index("ix_user_achievement_type", table_name="user_achievement")
    op.drop_index("ix_user_achievement_profile_type", table_name="user_achievement")
    op.drop_table("user_achievement")
    op.drop_index("ix_achievement_policy_achievement_type", table_name="achievement_policy")
    op.drop_table("achievement_policy")
    op.drop_table("achievement_type")
    op.drop_index("ix_user_external_identity_profile", table_name="user_external_identity")
    op.drop_table("user_external_identity")

    op.drop_constraint(op.f("ck_user_profile_principal_id_not_blank"), "user_profile", type_="check")
    op.drop_constraint(op.f("uq_user_profile_principal_id"), "user_profile", type_="unique")
    op.drop_column("user_profile", "principal_id")

    op.drop_constraint(op.f("ck_user_exam_score_in_range"), "user_exam", type_="check")
    op.create_check_constraint(op.f("ck_user_exam_score_nonnegative"), "user_exam", "score >= 0")
    op.drop_constraint(op.f("ck_requirement_node_min_score_in_range"), "requirement_node", type_="check")
    op.create_check_constraint(
        op.f("ck_requirement_node_min_score_nonnegative"), "requirement_node", "min_score IS NULL OR min_score >= 0"
    )
    op.drop_constraint(
        op.f("ck_olympiad_benefit_confirmation_score_in_range"), "olympiad_benefit", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_olympiad_benefit_confirmation_score_nonnegative"),
        "olympiad_benefit",
        "confirmation_score IS NULL OR confirmation_score >= 0",
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM admission_statistic
                GROUP BY pool_id, EXTRACT(YEAR FROM snapshot_date)
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade snapshots: more than one snapshot exists for a pool in a year';
            END IF;
        END;
        $$;
        """
    )
    op.add_column("admission_statistic", sa.Column("year", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE admission_statistic SET year = EXTRACT(YEAR FROM snapshot_date)::integer"
    )
    op.alter_column("admission_statistic", "year", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint(
        op.f("uq_admission_statistic_pool_snapshot_date"), "admission_statistic", type_="unique"
    )
    op.drop_index("ix_admission_statistic_snapshot_date", table_name="admission_statistic")
    op.drop_column("admission_statistic", "snapshot_date")
    op.create_check_constraint(op.f("ck_admission_statistic_year_valid"), "admission_statistic", "year >= 1900")
    op.create_unique_constraint(
        op.f("uq_admission_statistic_pool_year"), "admission_statistic", ["pool_id", "year"]
    )

    # Restore the v1 draft-time tree validator for users rolling all the way back.
    op.execute(
        """
        CREATE FUNCTION andromeda_validate_requirement_set(p_requirement_set_id uuid)
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        DECLARE
            has_cycle boolean;
            invalid_node uuid;
        BEGIN
            WITH RECURSIVE parent_walk(start_id, node_id, parent_node_id, path, cycle) AS (
                SELECT n.id, n.id, n.parent_node_id, ARRAY[n.id], false
                FROM requirement_node AS n
                WHERE n.requirement_set_id = p_requirement_set_id
                UNION ALL
                SELECT w.start_id, parent.id, parent.parent_node_id,
                       w.path || parent.id, parent.id = ANY(w.path)
                FROM parent_walk AS w
                JOIN requirement_node AS parent
                  ON parent.requirement_set_id = p_requirement_set_id
                 AND parent.id = w.parent_node_id
                WHERE w.parent_node_id IS NOT NULL AND NOT w.cycle
            )
            SELECT EXISTS (SELECT 1 FROM parent_walk WHERE cycle)
            INTO has_cycle;

            IF has_cycle THEN
                RAISE EXCEPTION 'requirement_set % contains a parent cycle', p_requirement_set_id
                    USING ERRCODE = '23514';
            END IF;

            SELECT n.id
            INTO invalid_node
            FROM requirement_node AS n
            LEFT JOIN requirement_node AS child
              ON child.requirement_set_id = n.requirement_set_id
             AND child.parent_node_id = n.id
            WHERE n.requirement_set_id = p_requirement_set_id
            GROUP BY n.id, n.node_type, n.operator_type, n.min_count
            HAVING (n.node_type = 'exam' AND count(child.id) <> 0)
                OR (n.node_type = 'operator' AND n.operator_type IN ('and', 'or') AND count(child.id) < 2)
                OR (n.node_type = 'operator' AND n.operator_type = 'at_least' AND count(child.id) < n.min_count)
            LIMIT 1;

            IF FOUND THEN
                RAISE EXCEPTION 'requirement_node % has an invalid child count', invalid_node
                    USING ERRCODE = '23514';
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION andromeda_check_requirement_node_tree()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                PERFORM andromeda_validate_requirement_set(OLD.requirement_set_id);
            ELSIF TG_OP = 'UPDATE' THEN
                PERFORM andromeda_validate_requirement_set(OLD.requirement_set_id);
                IF NEW.requirement_set_id <> OLD.requirement_set_id THEN
                    PERFORM andromeda_validate_requirement_set(NEW.requirement_set_id);
                END IF;
            ELSE
                PERFORM andromeda_validate_requirement_set(NEW.requirement_set_id);
            END IF;
            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_requirement_node_tree_valid
        AFTER INSERT OR UPDATE OR DELETE ON requirement_node
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION andromeda_check_requirement_node_tree();
        """
    )
