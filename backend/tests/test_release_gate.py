"""The release gate: it must say no for the right reason and yes only when everything is in order."""

import pytest

from app.core.errors import Conflict, Invalid
from app.models import AppVersion, Deviation
from app.services import applications, deviations, report_docs, requirements
from app.services.gate import evaluate_release_gate
from conftest import PASSWORD
from helpers import (
    add_requirements,
    add_test,
    approve_all,
    approve_report,
    execute,
    execute_all,
    full_setup,
    make_application,
    validate,
)


def checks(db, version):
    result = evaluate_release_gate(db, version.id)
    return result, {c.key: c for c in result.checks}


def test_an_empty_application_fails_every_check_that_needs_content(db, people):
    _, version = make_application(db, people)
    result, by_key = checks(db, version)
    assert not result.passed and not result.ready_for_report
    assert not by_key["urs_approved"].passed and "No requirements" in by_key["urs_approved"].detail
    assert not by_key["coverage"].passed
    assert not by_key["required_types"].passed


def test_a_requirement_without_a_test_is_named(db, people):
    application, version = make_application(db, people)
    reqs = add_requirements(db, people, application)
    add_test(db, people, application, "OQ", [reqs[0]])
    _, by_key = checks(db, version)
    assert not by_key["coverage"].passed
    assert reqs[1].code in by_key["coverage"].detail and reqs[2].code in by_key["coverage"].detail


def test_unrated_requirements_block_the_gate_and_the_urs_approval(db, people):
    application, version = make_application(db, people)
    requirements.create_requirement(db, people.ve, application, {"title": "No rating", "description": "No rating yet"})
    db.commit()
    _, by_key = checks(db, version)
    assert not by_key["risk_rated"].passed
    with pytest.raises(Conflict):
        applications.approve_urs(db, people.qa, PASSWORD, version)


def test_draft_tests_do_not_count_as_coverage(db, people):
    setup = full_setup(db, people)
    _, by_key = checks(db, setup.version)
    assert not by_key["coverage"].passed  # the tests exist but nobody approved them
    approve_all(db, people, setup)
    _, by_key = checks(db, setup.version)
    assert by_key["coverage"].passed


def test_unscripted_testing_is_not_enough_for_medium_or_high_risk(db, people):
    application, version = make_application(db, people)
    reqs = add_requirements(db, people, application)
    with pytest.raises(Invalid):
        add_test(db, people, application, "OQ", [reqs[0]], style="unscripted")
    db.rollback()
    add_test(db, people, application, "OQ", [reqs[2]], style="unscripted")  # low risk is fine


def test_the_gate_asks_for_the_test_types_of_the_gamp_category(db, people):
    setup = full_setup(db, people, gamp=1)  # category 1 only needs IQ
    approve_all(db, people, setup)
    execute(db, people, setup.version, setup.tests[0])
    _, by_key = checks(db, setup.version)
    assert by_key["required_types"].passed
    assert "IQ" in by_key["required_types"].label and "OQ" not in by_key["required_types"].label


def test_category_four_needs_iq_oq_and_pq_to_pass(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    execute(db, people, setup.version, setup.tests[0])
    execute(db, people, setup.version, setup.tests[1])
    _, by_key = checks(db, setup.version)
    assert not by_key["required_types"].passed and "PQ" in by_key["required_types"].detail


def test_a_failed_test_blocks_the_gate_and_opens_a_deviation(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    execute(db, people, setup.version, setup.tests[0])
    execute(db, people, setup.version, setup.tests[1], fail_step=2)
    execute(db, people, setup.version, setup.tests[2])
    result, by_key = checks(db, setup.version)
    assert not by_key["executed"].passed and "did not pass" in by_key["executed"].detail
    assert not by_key["deviations"].passed
    assert not result.ready_for_report


def test_the_gate_opens_after_a_retest_and_the_deviation_is_closed(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    execute(db, people, setup.version, setup.tests[0])
    execute(db, people, setup.version, setup.tests[1], fail_step=2)
    execute(db, people, setup.version, setup.tests[2])
    deviation = db.query(Deviation).one()
    deviations.update_deviation(db, people.ve, deviation, {
        "root_cause": "Typo in the configuration", "corrective_action": "Corrected the setting"}, "Analysis done")
    deviations.resolve_deviation(db, people.ve, deviation)
    deviations.close_deviation(db, people.qa, PASSWORD, deviation, "Fix verified by the retest")
    execute(db, people, setup.version, setup.tests[1])  # the retest passes
    db.commit()
    result, _ = checks(db, setup.version)
    assert result.ready_for_report


def test_tests_of_high_risk_requirements_must_be_reviewed(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    for test in setup.tests:
        execute(db, people, setup.version, test, review=False)
    _, by_key = checks(db, setup.version)
    assert not by_key["reviewed"].passed
    assert "TC-002" in by_key["reviewed"].detail  # the OQ test covers the high-risk requirement


def test_changing_a_requirement_after_approval_is_detected(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    _, by_key = checks(db, setup.version)
    assert by_key["urs_approved"].passed
    requirements.update_requirement(db, people.ve, setup.reqs[0], {"description": "Changed wording"}, "Clarified")
    db.commit()
    _, by_key = checks(db, setup.version)
    assert not by_key["urs_approved"].passed and "changed after" in by_key["urs_approved"].detail


def test_the_gate_is_closed_until_a_report_is_approved_for_exactly_this_state(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    execute_all(db, people, setup)
    result, by_key = checks(db, setup.version)
    assert result.ready_for_report and not result.passed
    assert not by_key["report_approved"].passed
    approve_report(db, people, setup.version)
    result, _ = checks(db, setup.version)
    assert result.passed


def test_an_approved_report_becomes_stale_when_something_changes(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    execute_all(db, people, setup)
    approve_report(db, people, setup.version)
    execute(db, people, setup.version, setup.tests[0])  # a new run changes the state
    result, by_key = checks(db, setup.version)
    assert not result.passed and "out of date" in by_key["report_approved"].detail


def test_release_is_refused_while_the_gate_is_closed(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    with pytest.raises(Conflict) as error:
        applications.release_version(db, people.qa, PASSWORD, setup.version)
    assert "gate" in error.value.message.lower()


def test_a_report_cannot_be_approved_while_tests_are_open(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    document = report_docs.generate_report(db, people.ve, setup.version)
    db.commit()
    assert document.gate_passed is False
    with pytest.raises(Conflict):
        report_docs.approve_report(db, people.qa, PASSWORD, document)


def test_the_complete_lifecycle_validates_the_version(db, people):
    setup = validate(db, people, full_setup(db, people))
    db.refresh(setup.version)
    assert setup.version.status == "validated" and setup.version.validated_at is not None
    assert evaluate_release_gate(db, setup.version.id).passed


def test_only_one_version_can_be_live_and_the_old_one_is_superseded(db, people):
    setup = validate(db, people, full_setup(db, people))
    live = db.get(AppVersion, setup.version.id)
    assert live.status == "validated"
    new_version = applications.create_version(db, people.ve, setup.application, "1.1")
    db.commit()
    assert new_version.status == "in_validation"
    with pytest.raises(Conflict):  # a second version in validation at the same time is refused
        applications.create_version(db, people.ve, setup.application, "1.2")
