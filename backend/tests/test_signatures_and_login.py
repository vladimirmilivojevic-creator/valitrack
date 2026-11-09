import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.errors import Conflict, Forbidden
from app.main import app
from app.models import ESignature
from app.services import applications, signatures
from conftest import PASSWORD
from helpers import add_requirements, make_application


def _ready_for_urs_approval(db, people):
    application, version = make_application(db, people)
    add_requirements(db, people, application)
    return application, version


def _login(username: str, password: str):
    return TestClient(app).post("/api/auth/login", json={"username": username, "password": password})


def test_a_signature_records_who_what_and_when(db, people):
    _, version = _ready_for_urs_approval(db, people)
    signature = applications.approve_urs(db, people.qa, PASSWORD, version)
    db.commit()
    stored = db.get(ESignature, signature.id)
    assert stored.signer_name == people.qa.full_name
    assert stored.signer_role == "qa_manager"
    assert stored.meaning == "Approved"
    assert stored.entity_type == "requirements_baseline" and stored.entity_id == version.id
    assert len(stored.record_hash) == 64 and len(stored.signature_hash) == 64
    assert stored.signed_at is not None


def test_a_signature_needs_the_password_again(db, people):
    _, version = _ready_for_urs_approval(db, people)
    with pytest.raises(Forbidden):
        applications.approve_urs(db, people.qa, "wrong password", version)
    assert db.query(ESignature).count() == 0


def test_the_role_decides_which_meaning_a_person_may_sign(db, people):
    _ready_for_urs_approval(db, people)
    with pytest.raises(Forbidden):
        signatures.sign(db, people.tester, PASSWORD, meaning="Approved", entity_type="x", entity_id=1,
                        entity_label="x", record_hash="0" * 64)


def test_the_person_who_prepared_the_version_cannot_approve_it(db, people):
    application, version = make_application(db, people)
    add_requirements(db, people, application)
    version.created_by = people.qa.id
    db.commit()
    with pytest.raises(Conflict):
        applications.approve_urs(db, people.qa, PASSWORD, version)


def test_signatures_cannot_be_changed_or_deleted(db, people):
    _, version = _ready_for_urs_approval(db, people)
    applications.approve_urs(db, people.qa, PASSWORD, version)
    db.commit()
    with pytest.raises((IntegrityError, DBAPIError)):
        db.execute(text("UPDATE e_signatures SET meaning = 'Released'"))
    db.rollback()
    with pytest.raises((IntegrityError, DBAPIError)):
        db.execute(text("DELETE FROM e_signatures"))


def test_the_signature_hash_depends_on_the_signed_content(db, people):
    _, version = _ready_for_urs_approval(db, people)
    first = applications.approve_urs(db, people.qa, PASSWORD, version)
    second = signatures.sign(
        db, people.qa, PASSWORD, meaning="Approved", entity_type="requirements_baseline", entity_id=version.id,
        entity_label="again", record_hash="f" * 64)
    db.commit()
    assert first.record_hash != second.record_hash
    assert first.signature_hash != second.signature_hash


def test_account_is_locked_after_five_wrong_passwords(people):
    for _ in range(5):
        assert _login(people.tester.username, "nope").status_code == 401
    locked = _login(people.tester.username, PASSWORD)
    assert locked.status_code == 403
    assert "locked" in locked.json()["detail"]


def test_an_administrator_can_unlock_an_account(people, api):
    for _ in range(5):
        _login(people.tester.username, "nope")
    assert api("admin").post(f"/api/users/{people.tester.id}/unlock").status_code == 200
    assert _login(people.tester.username, PASSWORD).status_code == 200


def test_wrong_signature_passwords_also_count_towards_the_lockout(db, people):
    _, version = _ready_for_urs_approval(db, people)
    for _ in range(5):
        with pytest.raises(Forbidden):
            applications.approve_urs(db, people.qa, "wrong", version)
    db.refresh(people.qa)
    assert people.qa.locked_until is not None
    with pytest.raises(Forbidden) as error:
        applications.approve_urs(db, people.qa, PASSWORD, version)
    assert "locked" in error.value.message


def test_unknown_user_and_wrong_password_look_the_same(people):
    wrong_password = _login(people.qa.username, "x")
    unknown_user = _login("nobody", "x")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_password_rules(people, api):
    admin = api("admin")
    weak = admin.post(f"/api/users/{people.tester.id}/reset-password", json={"new_password": "short"})
    assert weak.status_code == 422
    assert admin.post(f"/api/users/{people.tester.id}/reset-password",
                      json={"new_password": "A-much-better-pass-1"}).status_code == 200
