"""The demo data must load through the services, keep the audit chain valid and tell the planned story."""

import threading

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.main import app
from app.models import (
    Application,
    AppVersion,
    ChangeRequest,
    Deviation,
    ESignature,
    SupportTicket,
    TestRun,
    User,
)
from app.seed.demo import DEMO_LOGINS, DEMO_PASSWORD, reset_and_seed, seed_if_empty
from app.services import dashboard
from app.services.gate import evaluate_release_gate


def versions_of(db, name):
    application = db.scalar(select(Application).where(Application.name == name))
    return {v.version: v for v in db.scalars(select(AppVersion).where(AppVersion.application_id == application.id))}


def test_demo_data_tells_the_planned_story(db):
    reset_and_seed(db)

    assert db.scalar(select(func.count()).select_from(Application)) == 6
    assert db.scalar(select(func.count()).select_from(User)) == 14
    assert db.scalar(select(func.count()).select_from(SupportTicket)) == 10
    assert db.scalar(select(func.count()).select_from(ESignature)) > 60

    chain = db.execute(text("SELECT entries, first_broken_seq FROM verify_audit_chain()")).one()
    assert chain.entries > 300 and chain.first_broken_seq is None

    # DocuControl: 3.2 is live, 3.3 is in testing with one failed test that needs attention
    docu = versions_of(db, "DocuControl")
    assert docu["3.2"].status == "validated" and docu["3.3"].status == "in_validation"
    gate = evaluate_release_gate(db, docu["3.3"].id)
    assert not gate.ready_for_report
    failing = {c.key for c in gate.failing()}
    assert {"executed", "deviations", "report_approved"} <= failing
    assert "urs_approved" not in failing  # requirements are inherited from 3.2

    # SupplierHub: first validation in progress, with an overdue deviation
    sup = versions_of(db, "SupplierHub")["1.0"]
    assert sup.status == "in_validation"
    overdue = db.scalar(select(Deviation).where(Deviation.application_id == sup.application_id))
    assert overdue.status == "in_progress" and overdue.due_date < __import__("datetime").date.today()

    # TrainMate: 4.0 was superseded by 4.0.1 through a released change
    tm = versions_of(db, "TrainMate")
    assert tm["4.0"].status == "superseded" and tm["4.0.1"].status == "validated"
    released = db.scalar(select(ChangeRequest).where(ChangeRequest.status == "released"))
    assert released.title.startswith("Security patch")

    # YieldCalc: the requirements are incomplete, so the gate cannot open
    yield_gate = evaluate_release_gate(db, versions_of(db, "YieldCalc")["1.1"].id)
    assert not yield_gate.passed and "risk_rated" in {c.key for c in yield_gate.failing()}

    # PatchGuard: infrastructure, validated with IQ only
    assert versions_of(db, "PatchGuard")["2.3"].status == "validated"

    statuses = {s for (s,) in db.execute(text("SELECT DISTINCT status FROM change_requests"))}
    assert {"submitted", "impact_assessment", "pending_approval", "testing", "released"} <= statuses
    assert db.scalar(select(func.count()).select_from(TestRun)) > 25

    board = {row["name"]: row for row in dashboard.build_dashboard(db)["board"]}
    assert board["DocuControl"]["stage"] == "testing" and board["PatchGuard"]["stage"] == "validated"
    assert board["YieldCalc"]["stage"] == "requirements"


def test_reset_can_be_repeated_and_restarts_the_numbering(db):
    reset_and_seed(db)
    reset_and_seed(db)
    assert db.scalar(select(func.min(Application.id))) == 1
    assert db.scalar(select(func.min(ChangeRequest.id))) == 1
    code = db.scalar(select(ChangeRequest.code).where(ChangeRequest.id == 1))
    assert code == "CR-0001"
    assert db.execute(text("SELECT first_broken_seq FROM verify_audit_chain()")).scalar() is None


def test_seed_does_nothing_when_data_exists(db):
    reset_and_seed(db)
    assert seed_if_empty() is False


def test_demo_logins_work_over_the_api(db):
    reset_and_seed(db)
    for username in DEMO_LOGINS:
        response = TestClient(app).post("/api/auth/login", json={"username": username, "password": DEMO_PASSWORD})
        assert response.status_code == 200, username
    accounts = TestClient(app).get("/api/demo/accounts").json()
    assert accounts["enabled"] and len(accounts["accounts"]) == len(DEMO_LOGINS)


def test_scheduled_reset_endpoint_reloads_the_demo(db):
    reset_and_seed(db)
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "eva.qa", "password": DEMO_PASSWORD})
    assert login.status_code == 200
    response = client.post("/api/demo/reset", headers={"X-Reset-Token": "test-reset-token"})
    assert response.status_code == 200 and response.json() == {"status": "started"}
    for thread in threading.enumerate():  # the reset runs in its own thread: wait for it
        if thread.name == "demo-reset":
            thread.join(timeout=120)
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Application)) == 6


def test_the_app_resets_its_own_demo_only_at_night_and_only_once_a_day(db, people):
    from datetime import timedelta

    from app.models import AuditEntry
    from app.services.demo_scheduler import VIENNA, needs_reset
    from helpers import make_application

    make_application(db, people)
    loaded = db.scalar(select(func.min(AuditEntry.occurred_at))).astimezone(VIENNA)
    next_night = (loaded + timedelta(days=1)).replace(hour=3, minute=30)
    assert needs_reset(db, next_night) is True
    assert needs_reset(db, next_night.replace(hour=12)) is False  # daytime: leave the visitors alone
    assert needs_reset(db, loaded.replace(hour=3, minute=30)) is False  # data from today is fresh enough


def test_an_empty_database_is_left_to_the_start_script(db):
    from datetime import datetime

    from app.services.demo_scheduler import VIENNA, needs_reset

    assert needs_reset(db, datetime(2026, 11, 10, 3, 30, tzinfo=VIENNA)) is False
