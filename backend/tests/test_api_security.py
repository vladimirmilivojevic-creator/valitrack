"""Login, sessions, CSRF protection and the rule that nothing changes without the right permission."""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from conftest import PASSWORD

CHANGING = {"POST", "PUT", "PATCH", "DELETE"}


def test_every_data_route_needs_a_login(people):
    client = TestClient(app)
    open_routes = {"/api/health", "/api/health/db", "/api/auth/login", "/api/auth/logout", "/api/demo/accounts",
                   "/api/demo/reset", "/api/docs", "/api/openapi.json"}
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in open_routes or not route.path.startswith("/api"):
            continue
        method = sorted(route.methods - {"HEAD", "OPTIONS"})[0]
        path = route.path.replace("{key}", "validation-status")
        for name in ("application_id", "version_id", "test_case_id", "requirement_id", "run_id", "step_no",
                     "change_id", "deviation_id", "document_id", "evidence_id", "item_id", "session_id",
                     "ticket_id", "user_id"):
            path = path.replace("{" + name + "}", "1")
        path = path.replace("{department}", "IT")
        response = client.request(method, path, json={} if method in CHANGING else None)
        assert response.status_code == 401, f"{method} {route.path} answered {response.status_code} without a login"


def test_a_changing_request_without_the_csrf_token_is_refused(people):
    client = TestClient(app)
    client.post("/api/auth/login", json={"username": people.ve.username, "password": PASSWORD})
    response = client.post("/api/applications", json={})
    assert response.status_code == 403 and "security token" in response.json()["detail"]
    assert client.get("/api/applications").status_code == 200  # reading needs no token


def test_a_wrong_csrf_token_is_refused(people):
    client = TestClient(app)
    client.post("/api/auth/login", json={"username": people.ve.username, "password": PASSWORD})
    response = client.post("/api/applications", json={}, headers={"X-CSRF-Token": "wrong"})
    assert response.status_code == 403


def test_the_session_cookie_cannot_be_read_by_scripts(people):
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": people.ve.username, "password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_me_returns_the_user_and_the_permissions(people, api):
    me = api("qa").get("/api/auth/me").json()
    assert me["user"]["username"] == people.qa.username
    assert "change.release" in me["permissions"] and "app.write" not in me["permissions"]
    assert "password_hash" not in me["user"]


def test_logout_ends_the_session(people):
    client = TestClient(app)
    client.post("/api/auth/login", json={"username": people.qa.username, "password": PASSWORD})
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_a_deactivated_user_loses_access(people, api):
    session = api("tester")
    assert session.get("/api/auth/me").status_code == 200
    assert api("admin").patch(f"/api/users/{people.tester.id}", json={"is_active": False}).status_code == 200
    assert session.get("/api/auth/me").status_code == 401


def test_the_auditor_cannot_change_anything(people, api):
    """Walk through every changing route as the read-only auditor: none may succeed."""
    auditor = api("auditor")
    skipped = {"/api/auth/login", "/api/auth/logout", "/api/auth/change-password", "/api/demo/reset"}
    checked = 0
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in skipped or not route.path.startswith("/api"):
            continue
        for method in sorted(route.methods & CHANGING):
            path = route.path
            for name in ("application_id", "version_id", "test_case_id", "requirement_id", "run_id", "step_no",
                         "change_id", "deviation_id", "document_id", "item_id", "session_id", "ticket_id",
                         "user_id"):
                path = path.replace("{" + name + "}", "1")
            path = path.replace("{department}", "IT")
            if method == "DELETE":
                path += "?reason=testing+the+rules"
            response = auditor.call(method, path, json={})
            assert response.status_code >= 400, f"{method} {route.path} was allowed for the auditor"
            checked += 1
    assert checked > 40


def test_a_tester_cannot_write_requirements_or_approve(people, api):
    tester = api("tester")
    assert tester.post("/api/applications/1/requirements",
                       json={"title": "t", "description": "d"}).status_code in (403, 404)
    assert tester.post("/api/users", json={"username": "x", "full_name": "x", "email": "x@example.com",
                                           "role": "admin", "department": "IT",
                                           "password": "Some-Password-12"}).status_code == 403


def test_users_list_never_contains_password_hashes(people, api):
    text = api("tester").get("/api/users").text
    assert "password" not in text and "argon2" not in text


def test_health_does_not_touch_the_database():
    """The uptime monitor calls this often. It must stay independent of the database."""
    route = next(r for r in app.routes if isinstance(r, APIRoute) and r.path == "/api/health")
    assert route.dependant.dependencies == []
    assert TestClient(app).get("/api/health").json() == {"status": "ok"}
    assert TestClient(app).get("/api/health/db").json()["database"] == "reachable"


def test_demo_accounts_are_listed_in_demo_mode(people):
    response = TestClient(app).get("/api/demo/accounts").json()
    assert response["enabled"] is True and response["password"]


def test_demo_reset_needs_the_token(people):
    client = TestClient(app)
    assert client.post("/api/demo/reset").status_code == 403
    assert client.post("/api/demo/reset", headers={"X-Reset-Token": "wrong"}).status_code == 403


@pytest.mark.parametrize("path", ["/api/docs", "/api/openapi.json"])
def test_api_documentation_is_published(path):
    assert TestClient(app).get(path).status_code == 200
