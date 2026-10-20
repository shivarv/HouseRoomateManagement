import os
from datetime import date

import pytest

# Point the app at the test database before anything imports app.core.config.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://roommate:roommate@localhost:5434/roommate_test",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.models  # noqa: E402, F401
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import clock  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))


class FakeClock:
    def __init__(self, today: date):
        self.today = today

    def __call__(self, timezone: str) -> date:
        return self.today


@pytest.fixture
def fake_today(monkeypatch):
    fake = FakeClock(date(2026, 10, 19))
    monkeypatch.setattr(clock, "today_in", fake)
    return fake


@pytest.fixture
def client():
    return TestClient(app)


def register(client: TestClient, email: str, name: str) -> dict:
    res = client.post(
        "/api/v1/auth/register", json={"email": email, "name": name, "password": "password123"}
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
