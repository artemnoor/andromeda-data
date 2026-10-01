from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import Connection

from andromeda.db.models.academics import Olympiad, OlympiadBenefit, OlympiadProfile
from andromeda.db.models.admissions import (
    AdmissionCampaign,
    AdmissionStatistic,
    BenefitType,
    CompetitionPool,
    Department,
    Exam,
    FundingType,
    OlympiadResultType,
    Program,
    ProgramOffering,
    QuotaType,
    RequirementNode,
    RequirementSet,
    University,
)
from andromeda.db.models.ontology import (
    FactAssertion,
    LinkAssertion,
    ObjectRef,
    OntologyLinkType,
    OntologyObjectType,
    OntologyPropertyType,
)
from andromeda.db.models.provenance import Source, SourceArtifact, SourceType
from andromeda.db.models.rules import (
    PolicyRule,
    PolicyRuleOfferingScope,
    PolicyRuleProgramScope,
    PolicyRuleType,
    PolicyRuleVersion,
    RuleSet,
    RuleSetMember,
)
from andromeda.db.models.users import (
    AchievementPolicy,
    AchievementType,
    UserAchievement,
    UserExam,
    UserExternalIdentity,
    UserProfile,
    UserQuota,
)

pytestmark = pytest.mark.integration


def _new_id() -> uuid.UUID:
    return uuid.uuid4()


def _insert_id(connection: Connection, model: Any, **values: Any) -> uuid.UUID:
    return connection.execute(
        insert(model).values(**values).returning(model.id)
    ).scalar_one()


def _insert(connection: Connection, model: Any, **values: Any) -> None:
    connection.execute(insert(model).values(**values))


def _expect_rejected(connection: Connection, action: Callable[[], Any]) -> None:
    """Assert a PostgreSQL constraint/trigger rejects one isolated statement."""
    with pytest.raises(DBAPIError):
        with connection.begin_nested():
            action()
            connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def _university(connection: Connection, code: str = "uni") -> uuid.UUID:
    return _insert_id(connection, University, code=code, name=f"University {code}")


def _campaign(connection: Connection, university_id: uuid.UUID, year: int = 2027) -> uuid.UUID:
    return _insert_id(
        connection,
        AdmissionCampaign,
        university_id=university_id,
        year=year,
    )


def _program(connection: Connection, university_id: uuid.UUID, code: str = "prog") -> uuid.UUID:
    return _insert_id(
        connection,
        Program,
        university_id=university_id,
        code=code,
        name=f"Program {code}",
        degree_level="bachelor",
        duration_months=48,
    )


def _offering(
    connection: Connection,
    university_id: uuid.UUID,
    program_id: uuid.UUID,
    campaign_id: uuid.UUID,
    *,
    study_form: str = "full_time",
    language: str = "ru",
) -> uuid.UUID:
    return _insert_id(
        connection,
        ProgramOffering,
        university_id=university_id,
        program_id=program_id,
        campaign_id=campaign_id,
        study_form=study_form,
        language=language,
    )


def _source_artifact(connection: Connection) -> uuid.UUID:
    source_type_id = _insert_id(
        connection, SourceType, code="official_site", name="Official site"
    )
    source_id = _insert_id(
        connection,
        Source,
        source_type_id=source_type_id,
        name="University admissions site",
        url="https://example.test/admissions",
    )
    return _insert_id(
        connection,
        SourceArtifact,
        source_id=source_id,
        url="https://example.test/admissions/rules",
        checksum=uuid.uuid4().hex,
    )


def test_program_and_campaign_must_belong_to_the_same_university(connection: Connection) -> None:
    university_a = _university(connection, "uni_a")
    university_b = _university(connection, "uni_b")
    program_a = _program(connection, university_a, "prog_a")
    campaign_b = _campaign(connection, university_b)

    _expect_rejected(
        connection,
        lambda: _offering(connection, university_a, program_a, campaign_b),
    )


def test_duplicate_competition_pool_is_rejected(connection: Connection) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    program_id = _program(connection, university_id)
    offering_id = _offering(connection, university_id, program_id, campaign_id)
    funding_type_id = _insert_id(connection, FundingType, code="budget", name="Budget")
    quota_type_id = _insert_id(connection, QuotaType, code="general", name="General")
    fields = dict(
        offering_id=offering_id,
        funding_type_id=funding_type_id,
        quota_type_id=quota_type_id,
        places=20,
        tuition_per_year=Decimal("0"),
    )
    _insert_id(connection, CompetitionPool, **fields)
    _expect_rejected(connection, lambda: _insert_id(connection, CompetitionPool, **fields))


def test_requirement_drafts_may_be_incomplete_but_cannot_be_published(connection: Connection) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    program_id = _program(connection, university_id)
    offering_id = _offering(connection, university_id, program_id, campaign_id)
    empty_set_id = _insert_id(
        connection, RequirementSet, offering_id=offering_id, name="Empty draft"
    )
    assert connection.scalar(
        select(RequirementSet.status).where(RequirementSet.id == empty_set_id)
    ) == "draft"
    _expect_rejected(
        connection,
        lambda: connection.execute(
            update(RequirementSet).where(RequirementSet.id == empty_set_id).values(status="published")
        ),
    )

    exam_id = _insert_id(connection, Exam, code="math", name="Mathematics")
    incomplete_set_id = _insert_id(
        connection, RequirementSet, offering_id=offering_id, name="Incomplete AND"
    )
    root_id = _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=incomplete_set_id,
        node_type="operator",
        operator_type="and",
    )
    _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=incomplete_set_id,
        parent_node_id=root_id,
        exam_id=exam_id,
        node_type="exam",
    )
    _expect_rejected(
        connection,
        lambda: connection.execute(
            update(RequirementSet)
            .where(RequirementSet.id == incomplete_set_id)
            .values(status="published")
        ),
    )


def test_requirement_tree_supports_and_or_example(connection: Connection) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    program_id = _program(connection, university_id)
    offering_id = _offering(connection, university_id, program_id, campaign_id)
    requirement_set_id = _insert_id(
        connection, RequirementSet, offering_id=offering_id, name="Core EGE requirements"
    )
    root_id = _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=requirement_set_id,
        node_type="operator",
        operator_type="and",
    )
    for code, name in (("rus", "Russian"), ("math", "Mathematics")):
        exam_id = _insert_id(connection, Exam, code=code, name=name)
        _insert_id(
            connection,
            RequirementNode,
            requirement_set_id=requirement_set_id,
            parent_node_id=root_id,
            exam_id=exam_id,
            node_type="exam",
            min_score=Decimal("40"),
        )

    or_id = _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=requirement_set_id,
        parent_node_id=root_id,
        node_type="operator",
        operator_type="or",
    )
    for code, name in (("physics", "Physics"), ("informatics", "Informatics")):
        exam_id = _insert_id(connection, Exam, code=code, name=name)
        _insert_id(
            connection,
            RequirementNode,
            requirement_set_id=requirement_set_id,
            parent_node_id=or_id,
            exam_id=exam_id,
            node_type="exam",
        )

    connection.execute(
        update(RequirementSet)
        .where(RequirementSet.id == requirement_set_id)
        .values(status="published")
    )
    assert connection.scalar(
        select(RequirementSet.status).where(RequirementSet.id == requirement_set_id)
    ) == "published"
    _expect_rejected(
        connection,
        lambda: connection.execute(
            delete(RequirementNode).where(RequirementNode.requirement_set_id == requirement_set_id)
        ),
    )


def test_requirement_tree_supports_at_least_and_rejects_cycles(connection: Connection) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    program_id = _program(connection, university_id)
    offering_id = _offering(connection, university_id, program_id, campaign_id)
    requirement_set_id = _insert_id(
        connection, RequirementSet, offering_id=offering_id, name="At least two sciences"
    )
    root_id = _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=requirement_set_id,
        node_type="operator",
        operator_type="at_least",
        min_count=2,
    )
    for code in ("physics", "informatics", "chemistry"):
        exam_id = _insert_id(connection, Exam, code=code, name=code.title())
        _insert_id(
            connection,
            RequirementNode,
            requirement_set_id=requirement_set_id,
            parent_node_id=root_id,
            exam_id=exam_id,
            node_type="exam",
        )
    connection.execute(
        update(RequirementSet)
        .where(RequirementSet.id == requirement_set_id)
        .values(status="published")
    )

    insufficient_set_id = _insert_id(
        connection, RequirementSet, offering_id=offering_id, name="Insufficient AT_LEAST"
    )
    insufficient_root_id = _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=insufficient_set_id,
        node_type="operator",
        operator_type="at_least",
        min_count=2,
    )
    insufficient_exam_id = _insert_id(
        connection, Exam, code="geography", name="Geography"
    )
    _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=insufficient_set_id,
        parent_node_id=insufficient_root_id,
        exam_id=insufficient_exam_id,
        node_type="exam",
    )
    _expect_rejected(
        connection,
        lambda: connection.execute(
            update(RequirementSet)
            .where(RequirementSet.id == insufficient_set_id)
            .values(status="published")
        ),
    )

    cycle_set_id = _insert_id(
        connection, RequirementSet, offering_id=offering_id, name="Cyclic draft"
    )
    cycle_root_id = _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=cycle_set_id,
        node_type="operator",
        operator_type="and",
    )
    exam_id = _insert_id(connection, Exam, code="biology", name="Biology")
    child_id = _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=cycle_set_id,
        parent_node_id=cycle_root_id,
        exam_id=exam_id,
        node_type="exam",
    )
    connection.execute(
        update(RequirementNode)
        .where(RequirementNode.id == cycle_root_id)
        .values(parent_node_id=child_id)
    )
    extra_root_exam_id = _insert_id(connection, Exam, code="history", name="History")
    _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=cycle_set_id,
        exam_id=extra_root_exam_id,
        node_type="exam",
    )
    _expect_rejected(
        connection,
        lambda: connection.execute(
            update(RequirementSet).where(RequirementSet.id == cycle_set_id).values(status="published")
        ),
    )


def test_single_exam_scores_are_limited_to_zero_through_one_hundred(connection: Connection) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    program_id = _program(connection, university_id)
    offering_id = _offering(connection, university_id, program_id, campaign_id)
    profile_id = _insert_id(connection, UserProfile)
    exam_id = _insert_id(connection, Exam, code="exam", name="Exam")
    _insert(connection, UserExam, profile_id=profile_id, exam_id=exam_id, score=Decimal("100"))
    _expect_rejected(
        connection,
        lambda: connection.execute(
            insert(UserExam).values(profile_id=profile_id, exam_id=_insert_id(
                connection, Exam, code="exam_2", name="Exam 2"
            ), score=Decimal("100.001"))
        ),
    )

    requirement_set_id = _insert_id(
        connection, RequirementSet, offering_id=offering_id, name="Score boundary"
    )
    boundary_exam_id = _insert_id(connection, Exam, code="exam_3", name="Exam 3")
    _insert_id(
        connection,
        RequirementNode,
        requirement_set_id=requirement_set_id,
        exam_id=boundary_exam_id,
        node_type="exam",
        min_score=Decimal("100"),
    )
    second_requirement_set_id = _insert_id(
        connection, RequirementSet, offering_id=offering_id, name="Invalid score"
    )
    _expect_rejected(
        connection,
        lambda: _insert_id(
            connection,
            RequirementNode,
            requirement_set_id=second_requirement_set_id,
            exam_id=boundary_exam_id,
            node_type="exam",
            min_score=Decimal("100.001"),
        ),
    )

    olympiad_id = _insert_id(connection, Olympiad, name="Test Olympiad", level=1)
    olympiad_profile_id = _insert_id(
        connection, OlympiadProfile, olympiad_id=olympiad_id, name="Math", subject="math"
    )
    result_type_id = _insert_id(
        connection, OlympiadResultType, code="winner", name="Winner"
    )
    benefit_type_id = _insert_id(connection, BenefitType, code="bvi", name="No entrance exams")
    _insert(
        connection,
        OlympiadBenefit,
        olympiad_profile_id=olympiad_profile_id,
        offering_id=offering_id,
        result_type_id=result_type_id,
        benefit_type_id=benefit_type_id,
        confirmation_score=Decimal("100"),
    )
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            OlympiadBenefit,
            olympiad_profile_id=olympiad_profile_id,
            offering_id=offering_id,
            result_type_id=result_type_id,
            benefit_type_id=_insert_id(connection, BenefitType, code="other", name="Other"),
            confirmation_score=Decimal("100.001"),
        ),
    )


def test_admission_statistic_uses_snapshot_dates_and_keeps_aggregate_scores_unbounded(
    connection: Connection,
) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    program_id = _program(connection, university_id)
    offering_id = _offering(connection, university_id, program_id, campaign_id)
    funding_type_id = _insert_id(connection, FundingType, code="budget", name="Budget")
    quota_type_id = _insert_id(connection, QuotaType, code="general", name="General")
    pool_id = _insert_id(
        connection,
        CompetitionPool,
        offering_id=offering_id,
        funding_type_id=funding_type_id,
        quota_type_id=quota_type_id,
        places=10,
        tuition_per_year=Decimal("0"),
    )
    _insert(
        connection,
        AdmissionStatistic,
        pool_id=pool_id,
        snapshot_date=date(2026, 12, 1),
        passing_score=Decimal("245"),
        average_score=Decimal("230"),
        enrolled_count=8,
    )
    _insert(
        connection,
        AdmissionStatistic,
        pool_id=pool_id,
        snapshot_date=date(2026, 12, 2),
        passing_score=Decimal("245"),
    )
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            AdmissionStatistic,
            pool_id=pool_id,
            snapshot_date=date(2026, 12, 1),
            passing_score=Decimal("245"),
        ),
    )
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            AdmissionStatistic,
            pool_id=pool_id,
            snapshot_date=date(2027, 1, 1),
            passing_score=Decimal("-1"),
        ),
    )
    columns = connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'admission_statistic'"
        )
    ).scalars().all()
    assert "snapshot_date" in columns
    assert "year" not in columns


def test_achievement_policy_external_identities_and_campaign_quotas(connection: Connection) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    profile_id = _insert_id(connection, UserProfile, principal_id="andromeda-user-001")
    achievement_type_id = _insert_id(
        connection, AchievementType, code="gto_gold", name="GTO gold badge"
    )
    policy_id = _insert_id(
        connection,
        AchievementPolicy,
        campaign_id=campaign_id,
        achievement_type_id=achievement_type_id,
        additional_points=Decimal("3.500"),
        max_awards_per_profile=1,
    )
    assert policy_id
    achievement_id = _insert_id(
        connection,
        UserAchievement,
        profile_id=profile_id,
        achievement_type_id=achievement_type_id,
        achieved_on=date(2026, 5, 12),
        external_reference="certificate-123",
    )
    assert achievement_id
    _insert(
        connection,
        UserExternalIdentity,
        profile_id=profile_id,
        provider="max",
        provider_subject="max-user-987",
    )
    _insert(
        connection,
        UserExternalIdentity,
        profile_id=profile_id,
        provider="web",
        provider_subject="web-account-123",
    )
    quota_type_id = _insert_id(connection, QuotaType, code="special", name="Special quota")
    _insert(
        connection,
        UserQuota,
        profile_id=profile_id,
        campaign_id=campaign_id,
        quota_type_id=quota_type_id,
    )

    duplicate_subject_profile_id = _insert_id(connection, UserProfile)
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            UserExternalIdentity,
            profile_id=duplicate_subject_profile_id,
            provider="max",
            provider_subject="max-user-987",
        ),
    )


def _rule_version(
    connection: Connection,
    *,
    program_scope_id: uuid.UUID | None = None,
    offering_scope_id: uuid.UUID | None = None,
) -> uuid.UUID:
    rule_type_id = _insert_id(
        connection,
        PolicyRuleType,
        code=f"type_{uuid.uuid4().hex}",
        name="Points",
    )
    rule_id = _insert_id(
        connection, PolicyRule, code=f"rule_{uuid.uuid4().hex}", name="Additional points", rule_type_id=rule_type_id
    )
    version_id = _insert_id(
        connection,
        PolicyRuleVersion,
        rule_id=rule_id,
        version=1,
        expression="award_points()",
        valid_from=date(2027, 1, 1),
        status="draft",
    )
    if program_scope_id is not None:
        _insert(connection, PolicyRuleProgramScope, rule_version_id=version_id, program_id=program_scope_id)
    if offering_scope_id is not None:
        _insert(connection, PolicyRuleOfferingScope, rule_version_id=version_id, offering_id=offering_scope_id)
    connection.execute(
        update(PolicyRuleVersion).where(PolicyRuleVersion.id == version_id).values(status="published")
    )
    return version_id


def test_global_program_and_offering_rule_scopes_are_explicit_and_campaign_checked(
    connection: Connection,
) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    other_campaign_id = _campaign(connection, university_id, 2028)
    program_a = _program(connection, university_id, "program_a")
    program_b = _program(connection, university_id, "program_b")
    offering_a = _offering(connection, university_id, program_a, campaign_id)
    offering_b = _offering(connection, university_id, program_b, campaign_id)
    _offering(
        connection,
        university_id,
        program_a,
        other_campaign_id,
        study_form="part_time",
    )

    # Program and offering rows can be combined; a version with no rows is global.
    scoped_version_id = _rule_version(
        connection, program_scope_id=program_a, offering_scope_id=offering_b
    )
    assert connection.scalar(
        select(PolicyRuleProgramScope.program_id).where(
            PolicyRuleProgramScope.rule_version_id == scoped_version_id
        )
    ) == program_a
    assert connection.scalar(
        select(PolicyRuleOfferingScope.offering_id).where(
            PolicyRuleOfferingScope.rule_version_id == scoped_version_id
        )
    ) == offering_b

    rule_set_id = _insert_id(
        connection,
        RuleSet,
        campaign_id=campaign_id,
        name="Scoped rules",
        version=1,
        status="draft",
    )
    rule_id = connection.scalar(
        select(PolicyRuleVersion.rule_id).where(PolicyRuleVersion.id == scoped_version_id)
    )
    _insert(
        connection,
        RuleSetMember,
        rule_set_id=rule_set_id,
        rule_version_id=scoped_version_id,
        rule_id=rule_id,
    )

    # A global published version is scoped by its containing campaign rule set.
    global_version_id = _rule_version(connection)
    global_rule_id = connection.scalar(
        select(PolicyRuleVersion.rule_id).where(PolicyRuleVersion.id == global_version_id)
    )
    _insert(
        connection,
        RuleSetMember,
        rule_set_id=rule_set_id,
        rule_version_id=global_version_id,
        rule_id=global_rule_id,
    )

    only_a_version = _rule_version(connection, offering_scope_id=offering_a)
    only_a_rule_id = connection.scalar(
        select(PolicyRuleVersion.rule_id).where(PolicyRuleVersion.id == only_a_version)
    )
    other_rule_set_id = _insert_id(
        connection,
        RuleSet,
        campaign_id=other_campaign_id,
        name="Other campaign rules",
        version=1,
        status="draft",
    )
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            RuleSetMember,
            rule_set_id=other_rule_set_id,
            rule_version_id=only_a_version,
            rule_id=only_a_rule_id,
        ),
    )
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            PolicyRuleOfferingScope,
            rule_version_id=only_a_version,
            offering_id=offering_b,
        ),
    )

    draft_type_id = _insert_id(
        connection,
        PolicyRuleType,
        code=f"draft_{uuid.uuid4().hex}",
        name="Draft rule",
    )
    draft_rule_id = _insert_id(
        connection,
        PolicyRule,
        code=f"draft_{uuid.uuid4().hex}",
        name="Draft rule",
        rule_type_id=draft_type_id,
    )
    draft_version_id = _insert_id(
        connection,
        PolicyRuleVersion,
        rule_id=draft_rule_id,
        version=1,
        expression="draft()",
        valid_from=date(2027, 1, 1),
        status="draft",
    )
    _insert(
        connection,
        PolicyRuleOfferingScope,
        rule_version_id=draft_version_id,
        offering_id=offering_b,
    )
    connection.execute(delete(PolicyRuleVersion).where(PolicyRuleVersion.id == draft_version_id))
    assert connection.scalar(
        select(PolicyRuleOfferingScope.offering_id).where(
            PolicyRuleOfferingScope.rule_version_id == draft_version_id
        )
    ) is None


def test_published_rule_versions_and_rule_sets_are_immutable(connection: Connection) -> None:
    university_id = _university(connection)
    campaign_id = _campaign(connection, university_id)
    version_id = _rule_version(connection)
    rule_id = connection.scalar(
        select(PolicyRuleVersion.rule_id).where(PolicyRuleVersion.id == version_id)
    )
    _expect_rejected(
        connection,
        lambda: connection.execute(
            update(PolicyRuleVersion)
            .where(PolicyRuleVersion.id == version_id)
            .values(expression="changed()")
        ),
    )
    rule_set_id = _insert_id(
        connection,
        RuleSet,
        campaign_id=campaign_id,
        name="Immutable set",
        version=1,
        status="draft",
    )
    member = dict(rule_set_id=rule_set_id, rule_version_id=version_id, rule_id=rule_id)
    _insert(connection, RuleSetMember, **member)
    connection.execute(
        update(RuleSet).where(RuleSet.id == rule_set_id).values(status="published")
    )
    _expect_rejected(
        connection,
        lambda: connection.execute(
            update(RuleSet).where(RuleSet.id == rule_set_id).values(name="Changed")
        ),
    )
    _expect_rejected(
        connection,
        lambda: connection.execute(delete(RuleSetMember).where(RuleSetMember.rule_set_id == rule_set_id)),
    )


def test_ontology_property_and_link_assertions_enforce_object_types(connection: Connection) -> None:
    university_type_id = _insert_id(
        connection,
        OntologyObjectType,
        api_name="university",
        display_name="University",
        backing_table="university",
    )
    pool_type_id = _insert_id(
        connection,
        OntologyObjectType,
        api_name="competition_pool",
        display_name="Competition pool",
        backing_table="competition_pool",
    )
    property_id = _insert_id(
        connection,
        OntologyPropertyType,
        object_type_id=pool_type_id,
        api_name="tuition",
        data_type="decimal",
    )
    university_ref = _insert_id(
        connection,
        ObjectRef,
        object_type_id=university_type_id,
        primary_key_value=str(_new_id()),
    )
    pool_ref = _insert_id(
        connection,
        ObjectRef,
        object_type_id=pool_type_id,
        primary_key_value=str(_new_id()),
    )
    artifact_id = _source_artifact(connection)
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            FactAssertion,
            object_ref_id=university_ref,
            object_type_id=university_type_id,
            property_type_id=property_id,
            source_artifact_id=artifact_id,
            value="1.25",
            valid_from=datetime(2027, 1, 1, tzinfo=timezone.utc),
            confidence=Decimal("0.9"),
        ),
    )

    integer_property_id = _insert_id(
        connection,
        OntologyPropertyType,
        object_type_id=pool_type_id,
        api_name="places",
        data_type="integer",
    )
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            FactAssertion,
            object_ref_id=pool_ref,
            object_type_id=pool_type_id,
            property_type_id=integer_property_id,
            source_artifact_id=artifact_id,
            value="not-an-integer",
            valid_from=datetime(2027, 1, 1, tzinfo=timezone.utc),
            confidence=Decimal("0.9"),
        ),
    )
    _insert(
        connection,
        FactAssertion,
        object_ref_id=pool_ref,
        object_type_id=pool_type_id,
        property_type_id=integer_property_id,
        source_artifact_id=artifact_id,
        value="120",
        valid_from=datetime(2027, 1, 1, tzinfo=timezone.utc),
        confidence=Decimal("0.9"),
    )

    program_type_id = _insert_id(
        connection,
        OntologyObjectType,
        api_name="program",
        display_name="Program",
    )
    link_type_id = _insert_id(
        connection,
        OntologyLinkType,
        source_type_id=university_type_id,
        target_type_id=program_type_id,
        api_name="offers_program",
        cardinality="one_to_many",
    )
    program_ref = _insert_id(
        connection,
        ObjectRef,
        object_type_id=program_type_id,
        primary_key_value=str(_new_id()),
    )
    _expect_rejected(
        connection,
        lambda: _insert(
            connection,
            LinkAssertion,
            link_type_id=link_type_id,
            source_type_id=university_type_id,
            target_type_id=program_type_id,
            source_object_id=program_ref,
            target_object_id=university_ref,
            source_artifact_id=artifact_id,
            valid_from=datetime(2027, 1, 1, tzinfo=timezone.utc),
            confidence=Decimal("0.9"),
        ),
    )
