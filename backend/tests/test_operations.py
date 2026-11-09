"""Training, support tickets, deviations, users and the dashboard."""

from datetime import date

import pytest
from sqlalchemy import text

from app.core.errors import Conflict, Forbidden, Invalid
from app.models import Deviation, TrainingRecord
from app.services import applications, dashboard, deviations, support, training
from conftest import PASSWORD
from helpers import execute, full_setup, validate


@pytest.fixture
def live(db, people):
    return validate(db, people, full_setup(db, people))


def matrix(db):
    rows = db.execute(text("SELECT full_name, training_status FROM vw_training_compliance")).all()
    return {name: status for name, status in rows}


def test_training_matrix_shows_who_is_trained_on_the_live_version(db, people, live):
    applications.set_application_users(db, people.ve, live.application, [
        {"user_id": people.tester.id}, {"user_id": people.tester2.id}])
    session = training.create_session(db, people.ve, live.application, {
        "app_version_id": live.version.id, "title": "Intro", "session_type": "classroom",
        "trainer_id": people.ve.id, "session_date": date(2026, 3, 1),
        "attendee_ids": [people.tester.id, people.tester2.id]})
    training.complete_session(db, people.ve, PASSWORD, session, [people.tester.id])
    db.commit()
    status = matrix(db)
    assert status[people.tester.full_name] == "trained"
    assert status[people.tester2.full_name] == "not_trained"  # invited but absent


def test_only_invited_people_can_be_marked_present(db, people, live):
    session = training.create_session(db, people.ve, live.application, {
        "app_version_id": live.version.id, "title": "Intro", "session_type": "online",
        "trainer_id": people.ve.id, "session_date": date(2026, 3, 1), "attendee_ids": [people.tester.id]})
    with pytest.raises(Invalid):
        training.complete_session(db, people.ve, PASSWORD, session, [people.tester2.id])
    with pytest.raises(Invalid):
        training.complete_session(db, people.ve, PASSWORD, session, [])


def test_a_completed_session_cannot_be_completed_again(db, people, live):
    session = training.create_session(db, people.ve, live.application, {
        "app_version_id": live.version.id, "title": "Intro", "session_type": "online",
        "trainer_id": people.ve.id, "session_date": date(2026, 3, 1), "attendee_ids": [people.tester.id]})
    training.complete_session(db, people.ve, PASSWORD, session, [people.tester.id])
    db.commit()
    with pytest.raises(Conflict):
        training.complete_session(db, people.ve, PASSWORD, session, [people.tester.id])
    assert db.query(TrainingRecord).count() == 1


def test_training_needs_the_training_permission(db, people, live):
    with pytest.raises(Forbidden):
        training.create_session(db, people.tester, live.application, {
            "app_version_id": live.version.id, "title": "x", "session_type": "online",
            "trainer_id": people.ve.id, "session_date": date(2026, 3, 1)})


# ---------------------------------------------------------------- support

def test_ticket_lifecycle(api, people, live):
    tester, ve = api("tester"), api("ve")
    created = tester.post("/api/tickets", json={
        "application_id": live.application.id, "summary": "Cannot log in", "description": "Error 500",
        "category": "access"})
    assert created.status_code == 201
    ticket = created.json()
    assert ticket["code"].startswith("TCK-") and ticket["status"] == "open"
    assert tester.patch(f"/api/tickets/{ticket['id']}", json={"status": "resolved"}).status_code == 403  # not their job
    assert ve.patch(f"/api/tickets/{ticket['id']}", json={"status": "resolved"}).status_code == 422  # needs resolution
    assigned = ve.patch(f"/api/tickets/{ticket['id']}", json={"assignee_id": people.ve.id}).json()
    assert assigned["status"] == "in_progress"
    done = ve.patch(f"/api/tickets/{ticket['id']}", json={"status": "resolved", "resolution": "Reset the account"})
    assert done.json()["resolved_at"] is not None
    commented = tester.post(f"/api/tickets/{ticket['id']}/comments", json={"body": "Works now, thanks"})
    assert commented.json()["comments"][-1]["body"] == "Works now, thanks"
    closed = ve.patch(f"/api/tickets/{ticket['id']}", json={"status": "closed"})
    assert closed.status_code == 200
    assert tester.post(f"/api/tickets/{ticket['id']}/comments", json={"body": "Hello?"}).status_code == 409


def test_a_ticket_can_link_a_change_of_the_same_application(db, people, live):
    ticket = support.create_ticket(db, people.tester, {
        "application_id": live.application.id, "summary": "s", "description": "d", "category": "defect"})
    db.commit()
    with pytest.raises(Invalid):
        support.update_ticket(db, people.ve, ticket, {"change_id": 999})


# ---------------------------------------------------------------- deviations

def test_manual_deviation_workflow(db, people, live):
    deviation = deviations.create_deviation(db, people.tester, {
        "application_id": live.application.id, "title": "Wrong label", "description": "Label shows 1.1",
        "severity": "minor"})
    db.commit()
    assert deviation.code.startswith("DEV-") and deviation.source == "manual"
    with pytest.raises(Conflict):
        deviations.resolve_deviation(db, people.ve, deviation)  # no root cause yet
    deviations.update_deviation(db, people.ve, deviation, {
        "root_cause": "Typo", "corrective_action": "Fixed the label"}, "Analysis")
    deviations.resolve_deviation(db, people.ve, deviation)
    with pytest.raises(Forbidden):
        deviations.close_deviation(db, people.ve, PASSWORD, deviation, "Looks fine")  # only QA closes
    deviations.close_deviation(db, people.qa, PASSWORD, deviation, "Verified in the test system")
    db.commit()
    assert deviation.status == "closed" and deviation.closed_at is not None
    with pytest.raises(Conflict):
        deviations.update_deviation(db, people.ve, deviation, {"title": "New"}, "Late change")


def test_accepting_a_deviation_needs_a_justification(db, people, live):
    deviation = deviations.create_deviation(db, people.tester, {
        "application_id": live.application.id, "title": "Cosmetic", "description": "Misaligned button"})
    db.commit()
    with pytest.raises(Invalid):
        deviations.accept_deviation(db, people.qa, PASSWORD, deviation, "ok")
    deviations.accept_deviation(db, people.qa, PASSWORD, deviation, "No impact on the intended use.")
    db.commit()
    assert deviation.status == "accepted"


def test_a_failed_run_opens_a_deviation_with_the_failing_step(db, people):
    from helpers import approve_all

    setup = full_setup(db, people)
    approve_all(db, people, setup)
    execute(db, people, setup.version, setup.tests[1], fail_step=2)
    deviation = db.query(Deviation).one()
    assert deviation.source == "test_failure" and "step 2" in deviation.description
    assert deviation.severity == "major"  # the test covers a high-risk requirement


# ---------------------------------------------------------------- users and dashboard

def test_user_administration(api, people):
    admin = api("admin")
    created = admin.post("/api/users", json={
        "username": "New.Person", "full_name": "New Person", "email": "new@example.com", "role": "tester",
        "department": "IT", "password": "A-good-password-1"})
    assert created.status_code == 201 and created.json()["username"] == "new.person"
    duplicate = admin.post("/api/users", json={
        "username": "new.person", "full_name": "Other", "email": "o@example.com", "role": "tester",
        "department": "IT", "password": "A-good-password-1"})
    assert duplicate.status_code == 409
    bad_role = admin.post("/api/users", json={
        "username": "x.y", "full_name": "X", "email": "x@example.com", "role": "king", "department": "IT",
        "password": "A-good-password-1"})
    assert bad_role.status_code == 422
    assert admin.patch(f"/api/users/{people.admin.id}", json={"is_active": False}).status_code == 409


def test_a_user_can_change_their_own_password(api, people):
    tester = api("tester")
    assert tester.post("/api/auth/change-password", json={
        "current_password": "wrong", "new_password": "A-brand-new-pass-1"}).status_code == 403
    assert tester.post("/api/auth/change-password", json={
        "current_password": PASSWORD, "new_password": "A-brand-new-pass-1"}).status_code == 200


def test_dashboard_shows_the_lifecycle_stage(db, people, live):
    board = dashboard.build_dashboard(db)["board"]
    assert board[0]["stage"] == "validated" and board[0]["live_version"] == "1.0"
    applications.create_version(db, people.ve, live.application, "1.1")
    db.commit()
    board = dashboard.build_dashboard(db)["board"]
    assert board[0]["working_version"] == "1.1" and board[0]["stage"] in ("requirements", "testing")


def test_dashboard_and_meta_endpoints(api, live):
    auditor = api("auditor")
    data = auditor.get("/api/dashboard").json()
    assert set(data) == {"board", "attention", "activity"}
    meta = auditor.get("/api/meta").json()
    assert "Quality Assurance" in meta["departments"] and meta["gamp"]["4"]["required_tests"] == ["IQ", "OQ", "PQ"]
