"""Error logging: every request has a ref; errors are saved with the user, house and stack."""

import json
import logging
from datetime import UTC, datetime, timedelta

from app.core import logs
from app.db.session import SessionLocal
from app.models import ErrorLog
from tests.conftest import register
from tests.test_chore_api import API, _setup_house


def _errors():
    with SessionLocal() as db:
        return db.query(ErrorLog).order_by(ErrorLog.created_at).all()


def test_a_crash_is_saved_with_its_ref_user_house_and_stack(client, fake_today, monkeypatch):
    from app.services import tasks

    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)
    monkeypatch.setattr(tasks, "sync", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom in sync")))
    res = client.get(f"{API}/households/{house['id']}/tasks/today?token=secret123&day=mon", headers=ann)
    assert res.status_code == 500

    [e] = _errors()
    assert e.request_id == res.json()["error_id"] and e.status == 500 and e.method == "GET"
    assert str(e.household_id) == house["id"] and e.household_name == "Maple St"
    assert e.user_id is not None and e.error_type == "RuntimeError"
    assert "boom in sync" in e.stack and "Traceback" in e.stack
    assert e.context == {"query": {"token": "[removed]", "day": "mon"}}  # secrets never saved


def test_the_house_is_found_from_the_item_in_the_url(client, fake_today, monkeypatch):
    from app.api.routes import households as routes

    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)
    member = client.get(f"{API}/households/{house['id']}", headers=ann).json()["members"][1]
    monkeypatch.setattr(routes.svc, "get_member", lambda *a: (_ for _ in ()).throw(KeyError("x")))
    assert client.patch(f"{API}/members/{member['id']}", json={"display_name": "B"}, headers=ann).status_code == 500
    [e] = _errors()
    assert str(e.household_id) == house["id"] and e.household_name == "Maple St"


def test_logged_errors_outside_a_crash_are_saved_too_and_refusals_are_not(client):
    ann = register(client, "ann@example.com", "Ann")
    # An expected refusal (404) isn't an error record.
    assert client.get(f"{API}/households/00000000-0000-0000-0000-000000000000", headers=ann).status_code == 404
    assert _errors() == []
    logging.getLogger("app.services.email").error("Couldn't send email to %s: %s", "bea@example.com", "Brevo 401")
    [e] = _errors()
    assert e.message == "Couldn't send email to bea@example.com: Brevo 401" and e.request_id is None


def test_saving_never_breaks_the_app(client, monkeypatch, capsys):
    monkeypatch.setattr(logs, "save_error", lambda record: (_ for _ in ()).throw(ConnectionError("db down")))
    logging.getLogger("app.test").error("something failed")  # doesn't raise
    assert "Couldn't save an error record" in capsys.readouterr().err


def test_log_lines_are_json_with_the_request_context():
    ctx = logs.start_request("GET", "/api/v1/households/abc", {"password": "x"})
    ctx.household_name = "Maple"
    record = logging.LogRecord("app.x", logging.INFO, __file__, 1, "hello %s", ("there",), None)
    line = json.loads(logs.JsonFormatter().format(record))
    assert line["message"] == "hello there" and line["request_id"] == ctx.request_id
    assert line["household_name"] == "Maple" and "password" not in json.dumps(line)


def test_records_older_than_30_days_are_deleted(client, monkeypatch):
    with SessionLocal() as db:
        db.add(ErrorLog(level="ERROR", logger="old", message="old", created_at=datetime.now(UTC) - timedelta(days=31)))
        db.add(ErrorLog(level="ERROR", logger="recent", message="recent", created_at=datetime.now(UTC) - timedelta(days=29)))
        db.commit()
    monkeypatch.setattr(logs, "_last_purge", None)
    logging.getLogger("app.test").error("new one")
    assert sorted(e.message for e in _errors()) == ["new one", "recent"]
