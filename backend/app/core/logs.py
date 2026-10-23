"""Logging for the whole backend.

- Every request gets a short id (`req_…`, returned as the X-Request-ID header and shown to the user
  as the "ref" on a 500), and every log line written while handling it carries that id, the user,
  the house, the method and the path — from the middleware down to any service.
- Lines go to stdout as one JSON object each, so Render's log search can filter by house or ref.
- Errors (log.error / log.exception, and every unexpected 500) are also saved in the error_logs
  table with the stack, in their own database session, so they're kept even when the request's
  own transaction failed. Saving can never crash the app or loop; it falls back to stdout.
- Records older than RETENTION_DAYS are deleted (at most once an hour, when a new one is saved).

Secrets never get in: passwords, tokens, the Authorization header and API keys are scrubbed, and
request bodies aren't recorded at all.
"""

import contextvars
import json
import logging
import os
import re
import secrets
import sys
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

RETENTION_DAYS = 30
APP_VERSION = (os.environ.get("RENDER_GIT_COMMIT") or "")[:12] or None
_SECRET = re.compile(r"pass(word)?|token|secret|authorization|api[_-]?key|cookie", re.I)


@dataclass
class RequestContext:
    """Filled in as the request goes along (the user once they're known, the house from the URL).

    One shared object per request: code running in worker threads updates the same one.
    """

    request_id: str
    method: str
    path: str
    query: dict = field(default_factory=dict)
    user_id: uuid.UUID | None = None
    household_id: uuid.UUID | None = None
    household_name: str | None = None
    status: int | None = None

    def fields(self) -> dict:
        return {
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
            "user_id": str(self.user_id) if self.user_id else None,
            "household_id": str(self.household_id) if self.household_id else None,
            "household_name": self.household_name,
        }


_current: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar("request_context", default=None)


def new_request_id() -> str:
    return f"req_{secrets.token_hex(5)}"


def start_request(method: str, path: str, query: dict) -> RequestContext:
    ctx = RequestContext(request_id=new_request_id(), method=method, path=path, query=scrub(query))
    _current.set(ctx)
    return ctx


def current() -> RequestContext | None:
    return _current.get()


def set_user(user_id: uuid.UUID) -> None:
    if ctx := _current.get():
        ctx.user_id = user_id


def scrub(data):
    """A copy with anything secret-looking replaced."""
    if isinstance(data, dict):
        return {k: "[removed]" if _SECRET.search(str(k)) else scrub(v) for k, v in data.items()}
    if isinstance(data, list):
        return [scrub(v) for v in data]
    return data


# --- JSON lines on stdout -------------------------------------------------------------------

_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if ctx := _current.get():
            line.update({k: v for k, v in ctx.fields().items() if v is not None})
        extra = {k: v for k, v in vars(record).items() if k not in _STANDARD and not k.startswith("_")}
        if extra:
            line.update(scrub(extra))
        if record.exc_info:
            line["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            line["stack"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


# --- Saved error records --------------------------------------------------------------------

_saving = threading.local()  # set while a record is being saved, so the save can't log itself
_last_purge: datetime | None = None
_purge_lock = threading.Lock()


class DatabaseErrorHandler(logging.Handler):
    """Saves ERROR and above to error_logs. Never raises."""

    def __init__(self):
        super().__init__(level=logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_saving, "busy", False) or record.name.startswith(("sqlalchemy", "alembic")):
            return
        _saving.busy = True
        try:
            save_error(record)
        except Exception:  # the database is down, the table is missing…: stdout still has it
            sys.stderr.write(f"Couldn't save an error record: {traceback.format_exc()}\n")
        finally:
            _saving.busy = False


def save_error(record: logging.LogRecord) -> None:
    from app.db.session import SessionLocal
    from app.models import ErrorLog

    ctx = _current.get()
    if ctx and ctx.household_name is None:
        find_household(ctx)
    stack = "".join(traceback.format_exception(*record.exc_info)) if record.exc_info else None
    with SessionLocal() as db:
        db.add(
            ErrorLog(
                level=record.levelname,
                logger=record.name[:200],
                message=record.getMessage()[:5000],
                request_id=ctx.request_id if ctx else None,
                method=ctx.method if ctx else None,
                path=ctx.path[:500] if ctx else None,
                status=ctx.status if ctx else None,
                user_id=ctx.user_id if ctx else None,
                household_id=ctx.household_id if ctx else None,
                household_name=ctx.household_name if ctx else None,
                error_type=(record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else None),
                stack=stack[-20000:] if stack else None,
                context={"query": ctx.query} if ctx and ctx.query else None,
                app_version=APP_VERSION,
            )
        )
        db.commit()
        _purge_old(db)


def _purge_old(db) -> None:
    """Delete records past RETENTION_DAYS, at most once an hour per process."""
    global _last_purge
    from sqlalchemy import delete

    from app.models import ErrorLog

    now = datetime.now(UTC)
    with _purge_lock:
        if _last_purge and now - _last_purge < timedelta(hours=1):
            return
        _last_purge = now
    db.execute(delete(ErrorLog).where(ErrorLog.created_at < now - timedelta(days=RETENTION_DAYS)))
    db.commit()


# --- Which house a request was about ---------------------------------------------------------

_UUID = r"[0-9a-fA-F-]{36}"
_HOUSE_PATH = re.compile(rf"/households/({_UUID})")
_ITEM_PATH = re.compile(rf"/api/v1/([a-z-]+)/({_UUID})")


def house_from_path(ctx: RequestContext) -> None:
    """The cheap part, on every request: /households/{id}/…"""
    if m := _HOUSE_PATH.search(ctx.path):
        ctx.household_id = uuid.UUID(m.group(1))


def find_household(ctx: RequestContext) -> None:
    """Only when something went wrong: look the house up from the item in the URL
    (/members/{id}, /bills/{id}, …) and fill in its name. Best effort, never raises."""
    from app.db.session import SessionLocal
    from app.models import (
        Bill,
        BillPayment,
        ChatMessage,
        Chore,
        ChoreLog,
        ChoreSwap,
        ChoreTask,
        GroceryCategory,
        GroceryPreset,
        Household,
        HouseholdInvite,
        HouseholdMember,
        HelpRequest,
        ShoppingItem,
    )

    models = {
        "members": HouseholdMember, "bills": Bill, "bill-payments": BillPayment, "chat-messages": ChatMessage,
        "chores": Chore, "chore-logs": ChoreLog, "swaps": ChoreSwap, "tasks": ChoreTask,
        "grocery-categories": GroceryCategory, "grocery-presets": GroceryPreset, "email-invites": HouseholdInvite,
        "help-requests": HelpRequest, "shopping": ShoppingItem,
    }  # fmt: skip
    try:
        with SessionLocal() as db:
            if ctx.household_id is None and (m := _ITEM_PATH.search(ctx.path)) and m.group(1) in models:
                item = db.get(models[m.group(1)], uuid.UUID(m.group(2)))
                for owner in (item, getattr(item, "chore", None), getattr(item, "bill", None)):
                    if owner is not None and getattr(owner, "household_id", None):
                        ctx.household_id = owner.household_id
                        break
            if ctx.household_id and (house := db.get(Household, ctx.household_id)):
                ctx.household_name = house.name
    except Exception:  # noqa: S110 - context is a nice-to-have; the error itself still gets saved
        pass


# --- Setup ----------------------------------------------------------------------------------


def configure(save_to_database: bool = True) -> None:
    """Called once at startup. INFO and up as JSON on stdout; ERROR and up also saved."""
    root = logging.getLogger()
    root.handlers.clear()
    out = logging.StreamHandler(sys.stdout)
    out.setFormatter(JsonFormatter())
    root.addHandler(out)
    if save_to_database:
        root.addHandler(DatabaseErrorHandler())
    root.setLevel(logging.INFO)
    # Uvicorn's own lines in the same format; its access log is replaced by ours (with ref, house, time).
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # Client libraries log whole URLs (query strings included): keep them quiet.
    for name in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
