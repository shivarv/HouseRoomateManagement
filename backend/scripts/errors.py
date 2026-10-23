"""Read the saved error log (error_logs, kept 30 days).

    python -m scripts.errors                      # the last day's errors, newest first
    python -m scripts.errors --since 7d           # the last week
    python -m scripts.errors --house <household id>
    python -m scripts.errors --id req_8f3k2a      # one error in full, with its stack

Uses DATABASE_URL like the app: point it at Neon to read production's errors.
"""

import argparse
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ErrorLog


def _since(text: str) -> datetime:
    m = re.fullmatch(r"(\d+)([hd])", text)
    if not m:
        raise SystemExit("--since looks like 12h or 7d")
    n, unit = int(m.group(1)), m.group(2)
    return datetime.now(UTC) - (timedelta(hours=n) if unit == "h" else timedelta(days=n))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", default="1d")
    parser.add_argument("--house", help="household id")
    parser.add_argument("--id", help="a request ref (req_…): show it in full")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.id:
            rows = db.scalars(select(ErrorLog).where(ErrorLog.request_id == args.id).order_by(ErrorLog.created_at)).all()
            if not rows:
                raise SystemExit(f"No error with ref {args.id} (they're kept 30 days).")
            for e in rows:
                print(f"{e.created_at:%Y-%m-%d %H:%M:%S} {e.level} {e.logger}\n  {e.method or ''} {e.path or ''} → {e.status or ''}")
                print(f"  user {e.user_id or '-'} · house {e.household_name or '-'} ({e.household_id or '-'}) · version {e.app_version or '-'}")
                print(f"  {e.message}")
                if e.context:
                    print(f"  context {e.context}")
                if e.stack:
                    print("\n" + e.stack)
            return
        query = select(ErrorLog).where(ErrorLog.created_at >= _since(args.since))
        if args.house:
            query = query.where(ErrorLog.household_id == uuid.UUID(args.house))
        rows = db.scalars(query.order_by(ErrorLog.created_at.desc()).limit(args.limit)).all()
        if not rows:
            print("No errors. 🎉")
        for e in rows:
            where = f"{e.method} {e.path}" if e.path else e.logger
            print(f"{e.created_at:%m-%d %H:%M} {e.request_id or '-':<15} {e.household_name or '-':<18.18} {where:<55.55} {e.error_type or ''} {e.message[:80]}")


if __name__ == "__main__":
    main()
