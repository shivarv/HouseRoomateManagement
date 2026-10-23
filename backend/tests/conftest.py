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


def confirm_email(client: TestClient, email: str) -> dict:
    """What opening the emailed link does: confirms the address and signs in. Returns the response."""
    from sqlalchemy import select

    from app.core.security import create_email_token
    from app.db.session import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        token = create_email_token(user.id, user.email)
    res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert res.status_code == 200, res.text
    return res.json()


def sign_up(client: TestClient, body: dict) -> dict:
    """Sign up and open the emailed link: `{access_token, user}`, like logging in."""
    res = client.post("/api/v1/auth/register", json={"password": "password123", **body})
    assert res.status_code == 201, res.text
    return confirm_email(client, body["email"])


def register(client: TestClient, email: str, name: str) -> dict:
    token = sign_up(client, {"email": email, "name": name})["access_token"]
    return {"Authorization": f"Bearer {token}"}
