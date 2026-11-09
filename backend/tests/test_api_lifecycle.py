"""The whole validation lifecycle through the HTTP API, as the web app uses it.

Every call that changes something must leave at least one entry in the audit trail.
"""

import pytest

from app.models import AuditEntry
from conftest import PASSWORD


class Session:
    def __init__(self, db):
        self.db = db

    def call(self, client, method, url, expect=200, **kwargs):
        before = self.db.query(AuditEntry).count()
        response = client.call(method, url, **kwargs)
        assert response.status_code == expect, f"{method} {url}: {response.status_code} {response.text}"
        if method != "GET":
            after = self.db.query(AuditEntry).count()
            assert after > before, f"{method} {url} wrote no audit entry"
        return response.json() if response.headers.get("content-type", "").startswith("application/json") else None


def test_lifecycle_from_new_application_to_validated_version(db, people, api):
    ve, qa, tester = api("ve"), api("qa"), api("tester")
    s = Session(db)

    app = s.call(ve, "POST", "/api/applications", 201, json={
        "name": "Lifecycle App", "description": "Used in the test", "vendor": "Vendor", "department": "Production",
        "owner_id": people.owner.id, "gamp_category": 3, "intended_use": "Testing",
        "product_quality_impact": True, "initial_version": "1.0"})
    version_id = app["working_version"]["id"]

    ratings = [(3, 2, 2), (1, 1, 1)]
    requirement_ids = []
    for number, (severity, probability, detectability) in enumerate(ratings, start=1):
        created = s.call(ve, "POST", f"/api/applications/{app['id']}/requirements", 201, json={
            "title": f"Requirement {number}", "description": "Works", "severity": severity,
            "probability": probability, "detectability": detectability})
        requirement_ids.append(created["id"])
    assert created["code"] == "URS-002" and created["risk_level"] == "low"

    test_ids = []
    for test_type, covers in (("IQ", [requirement_ids[1]]), ("OQ", requirement_ids)):
        created = s.call(ve, "POST", f"/api/applications/{app['id']}/test-cases", 201, json={
            "test_type": test_type, "title": f"{test_type} check", "objective": "Check", "requirement_ids": covers,
            "steps": [{"action": "Do it", "expected_result": "Done"}]})
        test_ids.append(created["id"])

    gate = s.call(ve, "GET", f"/api/versions/{version_id}/gate")
    assert gate["passed"] is False

    s.call(qa, "POST", f"/api/versions/{version_id}/approve-urs", json={"password": PASSWORD})
    for test_id in test_ids:
        s.call(qa, "POST", f"/api/test-cases/{test_id}/approve", json={"password": PASSWORD})

    for test_id in test_ids:
        run = s.call(tester, "POST", "/api/runs", 201, json={"test_case_id": test_id, "version_id": version_id})
        s.call(tester, "PUT", f"/api/runs/{run['id']}/steps/1",
               json={"result": "passed", "actual_result": "It worked"})
        evidence = tester.call("POST", f"/api/runs/{run['id']}/steps/1/evidence",
                               files={"file": ("log.txt", b"all good", "text/plain")})
        assert evidence.status_code == 201
        assert evidence.json()["steps"][0]["evidence"][0]["sha256"]
        completed = s.call(tester, "POST", f"/api/runs/{run['id']}/complete", json={"password": PASSWORD})
        assert completed["run"]["result"] == "passed"
        s.call(qa, "POST", f"/api/runs/{run['id']}/review", json={"password": PASSWORD})

    report = s.call(ve, "POST", f"/api/versions/{version_id}/reports", 201)
    assert report["gate_passed"] is True
    s.call(qa, "POST", f"/api/report-documents/{report['id']}/approve", json={"password": PASSWORD})
    pdf = qa.get(f"/api/report-documents/{report['id']}/pdf")
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")

    released = s.call(qa, "POST", f"/api/versions/{version_id}/release", json={"password": PASSWORD})
    assert released["version"]["status"] == "validated"
    final = ve.get(f"/api/applications/{app['id']}").json()
    assert final["live_version"]["version"] == "1.0" and final["working_version"] is None

    signatures = ve.get("/api/signatures", params={"entity_type": "requirements_baseline", "entity_id": version_id})
    assert signatures.json()[0]["meaning"] == "Approved"
    assert ve.get("/api/audit/verify").json()["intact"] is True


def test_segregation_of_duties_is_enforced_over_the_api(people, api, db):
    ve, qa, tester = api("ve"), api("qa"), api("tester")
    app = ve.post("/api/applications", json={
        "name": "SoD App", "description": "d", "vendor": "v", "department": "IT", "owner_id": people.owner.id,
        "gamp_category": 3, "intended_use": "u", "initial_version": "1.0"}).json()
    version_id = app["working_version"]["id"]
    req = ve.post(f"/api/applications/{app['id']}/requirements", json={
        "title": "t", "description": "d", "severity": 1, "probability": 1, "detectability": 1}).json()
    test = ve.post(f"/api/applications/{app['id']}/test-cases", json={
        "test_type": "IQ", "title": "t", "objective": "o", "requirement_ids": [req["id"]],
        "steps": [{"action": "a", "expected_result": "e"}]}).json()
    # the author cannot approve their own test case, the tester cannot approve at all
    assert ve.post(f"/api/test-cases/{test['id']}/approve", json={"password": PASSWORD}).status_code == 403
    assert tester.post(f"/api/test-cases/{test['id']}/approve", json={"password": PASSWORD}).status_code == 403
    assert qa.post(f"/api/versions/{version_id}/approve-urs", json={"password": "wrong"}).status_code == 403
    assert qa.post(f"/api/versions/{version_id}/approve-urs", json={"password": PASSWORD}).status_code == 200
    assert qa.post(f"/api/test-cases/{test['id']}/approve", json={"password": PASSWORD}).status_code == 200

    run = tester.post("/api/runs", json={"test_case_id": test["id"], "version_id": version_id}).json()
    tester.put(f"/api/runs/{run['id']}/steps/1", json={"result": "passed", "actual_result": "ok"})
    assert api("tester2").put(f"/api/runs/{run['id']}/steps/1",
                              json={"result": "failed", "actual_result": "x"}).status_code == 403  # not their run
    tester.post(f"/api/runs/{run['id']}/complete", json={"password": PASSWORD})
    assert tester.post(f"/api/runs/{run['id']}/review", json={"password": PASSWORD}).status_code == 403
    assert qa.post(f"/api/runs/{run['id']}/review", json={"password": PASSWORD}).status_code == 200
    assert qa.post(f"/api/runs/{run['id']}/review", json={"password": PASSWORD}).status_code == 409  # only once


def test_evidence_rules(people, api):
    ve, qa, tester = api("ve"), api("qa"), api("tester")
    app = ve.post("/api/applications", json={
        "name": "Evidence App", "description": "d", "vendor": "v", "department": "IT", "owner_id": people.owner.id,
        "gamp_category": 1, "intended_use": "u", "initial_version": "1.0"}).json()
    version_id = app["working_version"]["id"]
    req = ve.post(f"/api/applications/{app['id']}/requirements", json={
        "title": "t", "description": "d", "severity": 1, "probability": 1, "detectability": 1}).json()
    test = ve.post(f"/api/applications/{app['id']}/test-cases", json={
        "test_type": "IQ", "title": "t", "objective": "o", "requirement_ids": [req["id"]],
        "steps": [{"action": "a", "expected_result": "e"}]}).json()
    qa.post(f"/api/versions/{version_id}/approve-urs", json={"password": PASSWORD})
    qa.post(f"/api/test-cases/{test['id']}/approve", json={"password": PASSWORD})
    run = tester.post("/api/runs", json={"test_case_id": test["id"], "version_id": version_id}).json()
    url = f"/api/runs/{run['id']}/steps/1/evidence"
    too_big = tester.call("POST", url, files={"file": ("big.txt", b"x" * (2 * 1024 * 1024 + 1), "text/plain")})
    assert too_big.status_code == 422
    wrong_type = tester.call("POST", url, files={"file": ("virus.exe", b"MZ", "application/x-msdownload")})
    assert wrong_type.status_code == 422
    ok = tester.call("POST", url, files={"file": ("a.png", b"\x89PNG\r\n", "image/png")})
    assert ok.status_code == 201
    evidence_id = ok.json()["steps"][0]["evidence"][0]["id"]
    download = tester.get(f"/api/evidence/{evidence_id}")
    assert download.content == b"\x89PNG\r\n"
    assert download.headers["x-content-type-options"] == "nosniff" and "sandbox" in download.headers["content-security-policy"]
    # after completion nothing can be added any more
    tester.put(f"/api/runs/{run['id']}/steps/1", json={"result": "passed", "actual_result": "ok"})
    tester.post(f"/api/runs/{run['id']}/complete", json={"password": PASSWORD})
    late = tester.call("POST", url, files={"file": ("late.txt", b"late", "text/plain")})
    assert late.status_code == 409


@pytest.mark.parametrize("bad", [
    {"severity": 4}, {"probability": 0}, {"detectability": 9},
])
def test_ratings_outside_one_to_three_are_refused(people, api, bad):
    ve = api("ve")
    app = ve.post("/api/applications", json={
        "name": "Rating App", "description": "d", "vendor": "v", "department": "IT", "owner_id": people.owner.id,
        "gamp_category": 3, "intended_use": "u"}).json()
    response = ve.post(f"/api/applications/{app['id']}/requirements", json={"title": "t", "description": "d", **bad})
    assert response.status_code == 422
