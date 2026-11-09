import os
from pathlib import Path
from types import SimpleNamespace

# Settings are read once at import time, so they must be set before the app is imported.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/valitrack_test")
os.environ["SECRET_KEY"] = "test-secret-key-for-the-automated-tests"
os.environ["FAST_HASHING"] = "true"
os.environ["DEMO_MODE"] = "true"
os.environ["DEMO_RESET_TOKEN"] = "test-reset-token"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.seed.demo import ALL_TABLES  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "Test-Password-123"


@pytest.fixture(scope="session", autouse=True)
def database():
    """Build the schema once with the real migrations (the triggers and views are part of what is tested)."""
    name = get_settings().sqlalchemy_url.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in name:
        pytest.exit(f'Refusing to run the tests on database "{name}". Its name must contain "test".')
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_tables(database):
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL valitrack.allow_reset = 'on'"))
        connection.execute(text(f"TRUNCATE {ALL_TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def people(db):
    """One person per role, plus a second QA manager for the segregation-of-duties tests."""
    password_hash = hash_password(PASSWORD)
    made = {}
    for key, role, department in [
        ("admin", "admin", "IT"),
        ("ve", "validation_engineer", "Quality Assurance"),
        ("tester", "tester", "Production"),
        ("qa", "qa_manager", "Quality Assurance"),
        ("qa2", "qa_manager", "Quality Assurance"),
        ("owner", "system_owner", "Regulatory Affairs"),
        ("auditor", "auditor", "Quality Assurance"),
        ("tester2", "tester", "R&D"),
    ]:
        user = User(username=f"{key}.user", full_name=f"{key.upper()} Person", email=f"{key}@example.com",
                    role=role, department=department, password_hash=password_hash)
        db.add(user)
        made[key] = user
    db.commit()
    return SimpleNamespace(**made)


class Api:
    """A signed-in client. It sends the CSRF header for you, like the web app does."""

    def __init__(self, username: str):
        self.client = TestClient(app)
        response = self.client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
        assert response.status_code == 200, response.text
        self.csrf = response.json()["csrf_token"]

    def call(self, method: str, url: str, **kwargs):
        headers = {"X-CSRF-Token": self.csrf, **kwargs.pop("headers", {})}
        return self.client.request(method, url, headers=headers, **kwargs)

    def get(self, url, **kw):
        return self.call("GET", url, **kw)

    def post(self, url, json=None, **kw):
        return self.call("POST", url, json=json if json is not None else {}, **kw)

    def put(self, url, json=None, **kw):
        return self.call("PUT", url, json=json, **kw)

    def patch(self, url, json=None, **kw):
        return self.call("PATCH", url, json=json, **kw)


@pytest.fixture
def api(people):
    """api("qa.user") returns a client signed in as that person."""
    cache: dict[str, Api] = {}

    def make(key: str) -> Api:
        if key not in cache:
            cache[key] = Api(getattr(people, key).username)
        return cache[key]

    return make
