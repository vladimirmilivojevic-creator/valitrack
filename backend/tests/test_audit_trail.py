"""The audit trail must be append-only, chained, and impossible to write to without the database stamping it."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.errors import Conflict
from app.models import AuditEntry
from app.services import applications, audit
from helpers import make_application


def _verify(db):
    return db.execute(text("SELECT entries, first_broken_seq, head_hash FROM verify_audit_chain()")).one()


def test_changes_are_written_with_the_change_in_one_transaction(db, people):
    make_application(db, people)
    entries = db.query(AuditEntry).order_by(AuditEntry.seq).all()
    assert [e.action for e in entries] == ["create", "create"]  # the application and its first version
    assert entries[0].actor_name == people.ve.full_name
    assert entries[0].prev_hash == "0" * 64
    assert entries[1].prev_hash == entries[0].entry_hash


def test_chain_is_intact_after_many_entries(db, people):
    for number in range(5):
        make_application(db, people, name=f"App {number}")
    result = _verify(db)
    assert result.entries == 10
    assert result.first_broken_seq is None


def test_a_failed_transaction_leaves_no_audit_entry(db, people):
    application, version = make_application(db, people)
    before = db.query(AuditEntry).count()
    with pytest.raises(Conflict):
        applications.create_version(db, people.ve, application, "1.0")  # the version already exists
    db.rollback()
    assert db.query(AuditEntry).count() == before


def test_a_change_without_commit_is_not_audited(db, people):
    application, _ = make_application(db, people)
    before = db.query(AuditEntry).count()
    audit.record(db, people.ve, "update", "application", application.id, "x")
    db.rollback()
    assert db.query(AuditEntry).count() == before


def test_update_is_blocked(db, people):
    make_application(db, people)
    with pytest.raises((IntegrityError, DBAPIError)) as error:
        db.execute(text("UPDATE audit_log SET actor_name = 'Somebody else' WHERE seq = 1"))
    assert "append-only" in str(error.value)


def test_delete_is_blocked(db, people):
    make_application(db, people)
    with pytest.raises((IntegrityError, DBAPIError)) as error:
        db.execute(text("DELETE FROM audit_log"))
    assert "append-only" in str(error.value)


def test_truncate_is_blocked_outside_the_demo_reset(db, people):
    make_application(db, people)
    with pytest.raises((IntegrityError, DBAPIError)) as error:
        db.execute(text("TRUNCATE audit_log"))
    assert "append-only" in str(error.value)


def test_the_database_chooses_time_sequence_and_hash(db, people):
    """Values sent by the application for these columns are replaced by the trigger."""
    db.execute(text("""
        INSERT INTO audit_log (seq, occurred_at, actor_name, action, entity_type, entity_id, prev_hash, entry_hash)
        VALUES (999, '2001-01-01', 'Forger', 'create', 'x', '1', 'fake', 'fake')"""))
    db.commit()
    row = db.query(AuditEntry).one()
    assert row.seq == 1
    assert row.occurred_at.year >= 2025
    assert row.prev_hash == "0" * 64 and row.entry_hash != "fake"
    assert _verify(db).first_broken_seq is None


def test_tampering_with_an_old_entry_is_detected(db, people):
    """Even the database owner can switch the trigger off. The hash chain then shows the damage."""
    for number in range(4):
        make_application(db, people, name=f"App {number}")
    db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_change"))
    db.execute(text("UPDATE audit_log SET new_values = '{\"edited\": true}'::jsonb WHERE seq = 3"))
    db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_change"))
    db.commit()
    assert _verify(db).first_broken_seq == 3


def test_removing_an_entry_in_the_middle_is_detected(db, people):
    for number in range(3):
        make_application(db, people, name=f"App {number}")
    db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_change"))
    db.execute(text("DELETE FROM audit_log WHERE seq = 2"))
    db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_change"))
    db.commit()
    assert _verify(db).first_broken_seq == 3


def test_audit_api_lists_and_verifies(people, api):
    qa = api("qa")
    qa.post("/api/applications", json={
        "name": "Via API", "description": "d", "vendor": "v", "department": "IT", "owner_id": people.owner.id,
        "gamp_category": 3, "intended_use": "u"})  # a QA manager may not create applications
    ve = api("ve")
    created = ve.post("/api/applications", json={
        "name": "Via API", "description": "d", "vendor": "v", "department": "IT", "owner_id": people.owner.id,
        "gamp_category": 3, "intended_use": "u", "initial_version": "1.0"})
    assert created.status_code == 201, created.text
    listing = ve.get("/api/audit", params={"entity_type": "application"}).json()
    assert listing["total"] == 1 and listing["items"][0]["actor_name"] == people.ve.full_name
    verify = ve.get("/api/audit/verify").json()
    assert verify["intact"] is True and verify["entries"] >= 2
    csv = ve.get("/api/audit/export.csv")
    assert csv.status_code == 200 and "entry_hash" in csv.text.splitlines()[0]
