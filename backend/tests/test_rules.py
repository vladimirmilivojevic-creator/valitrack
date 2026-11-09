"""The small rule tables: risk levels, GAMP categories, and that the database agrees with the Python code."""

import itertools

import pytest
from sqlalchemy import select

from app.core.permissions import ROLE_PERMISSIONS, ROLES, has_permission
from app.models import Application, Requirement
from app.services import gamp, requirements, risk
from helpers import make_application


def test_risk_levels_at_the_boundaries():
    assert risk.risk_level(1, 1, 1) == "low"
    assert risk.risk_level(2, 2, 1) == "low"          # 4
    assert risk.risk_level(2, 3, 1) == "medium"       # 6
    assert risk.risk_level(2, 2, 2) == "medium"       # 8
    assert risk.risk_level(3, 2, 2) == "high"         # 12
    assert risk.risk_level(3, 3, 3) == "high"         # 27
    assert risk.risk_level(None, 2, 2) is None


def test_database_and_python_calculate_the_same_risk(db, people):
    """The risk level is a generated column in the database. This test keeps it equal to the Python rule."""
    application, _ = make_application(db, people)
    for s, p, d in itertools.product((1, 2, 3), repeat=3):
        requirements.create_requirement(db, people.ve, application, {
            "title": f"S{s} P{p} D{d}", "description": "Works as specified", "severity": s, "probability": p, "detectability": d})
    db.commit()
    rows = db.scalars(select(Requirement).where(Requirement.application_id == application.id)).all()
    assert len(rows) == 27
    for row in rows:
        assert row.rpn == risk.rpn(row.severity, row.probability, row.detectability)
        assert row.risk_level == risk.risk_level(row.severity, row.probability, row.detectability)


def test_unrated_requirement_has_no_risk_level(db, people):
    application, _ = make_application(db, people)
    requirement = requirements.create_requirement(db, people.ve, application, {"title": "No rating", "description": "No rating yet"})
    db.commit()
    assert requirement.risk_level is None and requirement.rpn is None


@pytest.mark.parametrize("flags", list(itertools.product((False, True), repeat=3)))
def test_application_risk_class_matches_the_database(db, people, flags):
    application, _ = make_application(db, people, name=f"App {flags}", flags=flags)
    stored = db.scalar(select(Application.risk_class).where(Application.id == application.id))
    assert stored == risk.application_risk_class(*flags)


def test_gamp_categories_ask_for_more_tests_as_configuration_grows():
    assert gamp.required_test_types(1) == ("IQ",)
    assert gamp.required_test_types(3) == ("IQ", "OQ")
    assert gamp.required_test_types(4) == ("IQ", "OQ", "PQ")
    assert gamp.required_test_types(5) == ("IQ", "OQ", "PQ")
    assert 2 not in gamp.GAMP_CATEGORIES  # category 2 was removed in the second edition of GAMP 5


def test_validation_approach_mentions_category_and_risk():
    text = gamp.validation_approach(4, "high")
    assert "GAMP category 4" in text and "high risk" in text


def test_every_role_is_known_and_the_auditor_cannot_change_anything():
    assert set(ROLE_PERMISSIONS) == set(ROLES)
    assert ROLE_PERMISSIONS["auditor"] == set()
    assert not has_permission("tester", "change.approve")
    assert has_permission("qa_manager", "change.release")
