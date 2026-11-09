"""Change control: the state machine, who may move it, and what a release does."""

from datetime import date

import pytest
from sqlalchemy import select

from app.core.errors import Conflict, Forbidden, Invalid
from app.models import AppVersion, TrainingRecord
from app.services import applications, changes, configuration, report_docs, training
from conftest import PASSWORD
from helpers import execute, full_setup, validate


@pytest.fixture
def live(db, people):
    """A validated application, so that changes make sense."""
    return validate(db, people, full_setup(db, people))


def new_change(db, people, live, *, change_type="bug_fix", target="1.1", affects_requirements=False):
    change = changes.create_change(db, people.tester, live.application, {
        "title": "Fix the thing", "change_type": change_type, "business_need": "Users complain",
        "description": "Fix the thing in the application", "target_version": target,
        "affects_requirements": affects_requirements})
    db.commit()
    return change


def assess_all(db, people, change, level="low", affects=False):
    for impact in list(change.impacts):
        changes.assess(db, people.ve, change, impact.department, level, affects, "Looked at it")
    db.commit()


def to_pending_approval(db, people, live):
    change = new_change(db, people, live)
    changes.submit(db, people.tester, change)
    changes.start_assessment(db, people.ve, change, ["IT", "Production"])
    assess_all(db, people, change)
    return change


def test_a_change_cannot_be_created_before_the_first_validation(db, people):
    setup = full_setup(db, people)
    with pytest.raises(Conflict) as error:
        changes.create_change(db, people.tester, setup.application, {
            "title": "t", "change_type": "patch", "business_need": "n", "description": "d", "target_version": "2"})
    assert "no validated version" in error.value.message


def test_the_target_version_must_be_new(db, people, live):
    with pytest.raises(Conflict):
        new_change(db, people, live, target="1.0")


def test_full_path_from_request_to_release(db, people, live):
    change = new_change(db, people, live)
    assert change.status == "draft" and change.code.startswith("CR-")
    changes.submit(db, people.tester, change)
    changes.start_assessment(db, people.ve, change, ["IT", "Production"])
    assert change.status == "impact_assessment"
    assert {i.department for i in change.impacts} == {"IT", "Production", "Quality Assurance"}
    assess_all(db, people, change)
    assert change.status == "pending_approval" and change.risk_level == "low"
    changes.approve(db, people.qa, PASSWORD, change)
    db.commit()
    assert change.status == "approved" and change.target_version_id is not None
    target = db.get(AppVersion, change.target_version_id)
    assert target.status == "in_validation" and target.urs_approved  # requirements are inherited
    changes.start_testing(db, people.ve, change)
    assert change.status == "testing"
    for test in live.tests:
        execute(db, people, target, test, change_id=change.id)
    changes.complete_testing(db, people.ve, change)
    assert change.status == "ready_for_release"
    document = report_docs.generate_report(db, people.ve, target)
    report_docs.approve_report(db, people.qa, PASSWORD, document)
    changes.release(db, people.qa, PASSWORD, change, "Released")
    db.commit()
    db.refresh(target)
    assert change.status == "released" and change.released_at is not None
    assert target.status == "validated"
    assert db.get(AppVersion, live.version.id).status == "superseded"


def test_the_requester_cannot_approve_their_own_change(db, people, live):
    change = new_change(db, people, live)
    changes.submit(db, people.tester, change)
    changes.start_assessment(db, people.ve, change, ["IT"])
    assess_all(db, people, change)
    change.requested_by = people.qa.id
    db.commit()
    with pytest.raises(Conflict):
        changes.approve(db, people.qa, PASSWORD, change)


def test_a_tester_cannot_approve(db, people, live):
    change = to_pending_approval(db, people, live)
    with pytest.raises(Forbidden):
        changes.approve(db, people.tester2, PASSWORD, change)


def test_high_risk_changes_need_the_system_owner_as_well(db, people, live):
    change = new_change(db, people, live, change_type="upgrade")
    changes.submit(db, people.tester, change)
    changes.start_assessment(db, people.ve, change, ["IT"])
    assess_all(db, people, change, level="high", affects=True)
    assert change.risk_level == "high" and change.requires_revalidation is True
    assert changes.required_meanings(change) == ["Approved", "Owner approved"]
    changes.approve(db, people.qa, PASSWORD, change)
    db.commit()
    assert change.status == "pending_approval"  # one signature is not enough
    with pytest.raises(Conflict):
        changes.approve(db, people.qa2, PASSWORD, change)  # the same meaning twice is refused
    changes.approve(db, people.owner, PASSWORD, change)
    db.commit()
    assert change.status == "approved"


def test_low_risk_changes_do_not_need_the_system_owner(db, people, live):
    change = to_pending_approval(db, people, live)
    with pytest.raises(Conflict):
        changes.approve(db, people.owner, PASSWORD, change)


def test_new_functions_are_at_least_medium_risk(db, people, live):
    change = new_change(db, people, live, change_type="enhancement")
    changes.submit(db, people.tester, change)
    changes.start_assessment(db, people.ve, change, ["IT"])
    assess_all(db, people, change, level="low")
    assert change.risk_level == "medium"


def test_the_state_machine_refuses_steps_in_the_wrong_order(db, people, live):
    change = new_change(db, people, live)
    with pytest.raises(Conflict):
        changes.start_assessment(db, people.ve, change, ["IT"])  # not submitted yet
    changes.submit(db, people.tester, change)
    with pytest.raises(Conflict):
        changes.approve(db, people.qa, PASSWORD, change)  # no impact assessment yet
    with pytest.raises(Conflict):
        changes.start_testing(db, people.ve, change)
    with pytest.raises(Conflict):
        changes.release(db, people.qa, PASSWORD, change)


def test_an_unknown_department_is_refused(db, people, live):
    change = new_change(db, people, live)
    changes.submit(db, people.tester, change)
    with pytest.raises(Invalid):
        changes.start_assessment(db, people.ve, change, ["Catering"])


def test_the_qa_manager_can_reject_and_the_reason_is_kept(db, people, live):
    change = to_pending_approval(db, people, live)
    changes.reject(db, people.qa, PASSWORD, change, "Not needed now")
    db.commit()
    assert change.status == "rejected" and change.decision_reason == "Not needed now"


def test_cancel_before_testing_retires_the_planned_version(db, people, live):
    change = new_change(db, people, live)
    changes.submit(db, people.tester, change)
    changes.start_assessment(db, people.ve, change, ["IT"])
    assess_all(db, people, change)
    changes.approve(db, people.qa, PASSWORD, change)
    db.commit()
    target_id = change.target_version_id
    changes.cancel(db, people.tester, change, "Vendor delayed the fix")
    db.commit()
    assert change.status == "cancelled"
    assert db.get(AppVersion, target_id).status == "retired"


def test_testing_cannot_finish_while_tests_are_open(db, people, live):
    change = to_pending_approval(db, people, live)
    changes.approve(db, people.qa, PASSWORD, change)
    changes.start_testing(db, people.ve, change)
    db.commit()
    with pytest.raises(Conflict) as error:
        changes.complete_testing(db, people.ve, change)
    assert "not finished" in error.value.message


def test_release_makes_people_who_were_trained_before_train_again(db, people, live):
    application = live.application
    applications.set_application_users(db, people.ve, application, [
        {"user_id": people.tester.id, "app_role": "user"}, {"user_id": people.tester2.id, "app_role": "user"}])
    session = training.create_session(db, people.ve, application, {
        "app_version_id": live.version.id, "title": "Intro", "session_type": "classroom",
        "trainer_id": people.ve.id, "session_date": date(2026, 1, 10), "attendee_ids": [people.tester.id]})
    training.complete_session(db, people.ve, PASSWORD, session, [people.tester.id])
    db.commit()
    change = to_pending_approval(db, people, live)
    changes.approve(db, people.qa, PASSWORD, change)
    changes.start_testing(db, people.ve, change)
    target = db.get(AppVersion, change.target_version_id)
    for test in live.tests:
        execute(db, people, target, test, change_id=change.id)
    changes.complete_testing(db, people.ve, change)
    document = report_docs.generate_report(db, people.ve, target)
    report_docs.approve_report(db, people.qa, PASSWORD, document)
    changes.release(db, people.qa, PASSWORD, change)
    db.commit()
    required = db.scalars(select(TrainingRecord).where(
        TrainingRecord.app_version_id == target.id, TrainingRecord.status == "required")).all()
    assert [r.user_id for r in required] == [people.tester.id]  # only the person trained before, tester2 never was


def test_configuration_of_a_validated_application_needs_an_approved_change(db, people, live):
    with pytest.raises(Conflict):
        configuration.create_item(db, people.admin, live.application, {"name": "Timeout", "value": "20"})
    change = to_pending_approval(db, people, live)
    with pytest.raises(Conflict):  # a change that is not yet approved is not enough
        configuration.create_item(db, people.admin, live.application,
                                  {"name": "Timeout", "value": "20", "change_request_id": change.id})
    changes.approve(db, people.qa, PASSWORD, change)
    db.commit()
    item = configuration.create_item(db, people.admin, live.application,
                                     {"name": "Timeout", "value": "20", "change_request_id": change.id})
    db.commit()
    assert item.last_change_request_id == change.id
    with pytest.raises(Conflict):
        configuration.update_item(db, people.admin, item, {"value": "30"}, "Longer sessions")  # no change given
    configuration.update_item(db, people.admin, item, {"value": "30", "change_request_id": change.id},
                              "Longer sessions")


def test_configuration_of_an_application_that_is_not_validated_yet_is_free(db, people):
    setup = full_setup(db, people)
    item = configuration.create_item(db, people.admin, setup.application, {"name": "Timeout", "value": "20"})
    configuration.update_item(db, people.admin, item, {"value": "25"}, "Tuning")
    db.commit()
    assert item.value == "25"


def test_regression_set_only_offers_approved_tests(db, people, live):
    change = to_pending_approval(db, people, live)
    changes.approve(db, people.qa, PASSWORD, change)
    with pytest.raises(Invalid):
        changes.start_testing(db, people.ve, change, [99999])
