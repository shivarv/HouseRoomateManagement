# Backend — Python API

REST API for House Roommate Management. Owns all business logic and is the only component
that talks to PostgreSQL.

## Stack

| Concern        | Choice                                  |
| -------------- | --------------------------------------- |
| Language       | Python 3.12+                            |
| Web framework  | FastAPI                                 |
| ORM            | SQLAlchemy 2.x                          |
| DB driver      | psycopg 3                               |
| Migrations     | Alembic                                 |
| Validation     | Pydantic v2 / pydantic-settings         |
| Auth           | JWT bearer tokens                       |
| Tests          | pytest + httpx                          |
| Lint / format  | ruff                                    |

## Folder structure

```
backend/
├── app/
│   ├── main.py            # FastAPI app factory, middleware (CORS), router registration
│   ├── api/
│   │   ├── deps.py        # Shared dependencies: DB session, current user
│   │   └── routes/        # health.py, auth.py, households.py (+ members, invites), chores.py (+ tasks, schedule)
│   ├── core/
│   │   ├── config.py      # Settings loaded from env (.env at repo root)
│   │   └── security.py    # Password hashing, JWT encode/decode
│   ├── db/
│   │   ├── session.py     # Engine, SessionLocal, get_db()
│   │   └── base.py        # DeclarativeBase + UUID / timestamp mixins
│   ├── models/            # SQLAlchemy ORM models (tables); __init__ imports all for Alembic
│   ├── schemas/           # Pydantic request/response models (API shapes)
│   └── services/          # Business logic; routes call services, services use the DB session
│       ├── rotation.py    #   pure round-robin math (no DB) — the core of chore assignment
│       ├── chores.py      #   chores + rotation changes
│       ├── tasks.py       #   today's tasks, schedule, mark done
│       ├── households.py  #   households, members, invites
│       └── clock.py       #   "today" in a household's timezone (patched in tests)
├── alembic/
│   └── versions/          # Migration scripts
├── scripts/seed_demo.py   # demo household with 8 roommates
├── tests/                 # pytest: rotation math + API flows against a real Postgres test DB
├── alembic.ini
└── pyproject.toml
```

### Layering rules

```
routes  ──▶  services  ──▶  models / DB session
  │              │
  └── schemas ◀──┘   (Pydantic in/out; ORM objects never leak out of the API)
```

- **routes** handle HTTP only: parse input, call a service, return a schema. No SQL here.
- **services** hold business rules (e.g. who is on duty today) and raise `services.errors.*`, which become HTTP errors.
- **models** describe tables. Schema changes go through an Alembic migration — never edit the DB by hand.
- **schemas** are the public API contract; keep them in sync with [docs/API.md](../docs/API.md).

## Data model

| Table               | Purpose                                     |
| ------------------- | ------------------------------------------- |
| `users`                  | Account: email, hashed password, name                          |
| `households`             | A shared house (incl. timezone for "today")                    |
| `household_members`      | Person in a house: display name, role, optional linked `user_id` |
| `chores`                 | Chore definition: name, frequency, rotation start date         |
| `chore_rotation_members` | Ordered round-robin list of members per chore                  |
| `chore_tasks`            | One row per chore per day: assignee + status (history)         |
| `expenses` *(planned)*        | Shared purchases/bills paid by a member            |
| `expense_splits` *(planned)*  | Each member's share of an expense                  |

All tables use UUID primary keys and `created_at` / `updated_at` timestamps (UTC).

## Local setup

```bash
# from repo root
cp .env.example .env
docker compose up -d db

cd backend
python3 -m venv .venv && source .venv/bin/activate    # Python 3.12+
pip install -e ".[dev]"

alembic upgrade head                       # create tables
python -m scripts.seed_demo                # optional: demo house + logins (password123)
uvicorn app.main:app --reload --port 8001  # run API
```

- API: http://localhost:8001/api/v1
- Interactive docs (Swagger): http://localhost:8001/docs
- Health check: `GET /api/v1/health`

Demo logins after seeding: `ann@example.com` (admin), `bea@example.com`, `cy@example.com`, all `password123`.

## Common commands

```bash
alembic revision --autogenerate -m "add chores table"   # new migration
alembic upgrade head                                     # apply
docker compose exec db createdb -U roommate roommate_test  # once, for tests
pytest                                                   # tests
ruff check . && ruff format .                            # lint + format
```

## Configuration

Read from the repo-root `.env` (see [.env.example](../.env.example)):

| Variable                      | Description                          |
| ----------------------------- | ------------------------------------ |
| `DATABASE_URL`                | SQLAlchemy URL for PostgreSQL        |
| `CORS_ORIGINS`                | Comma-separated allowed web origins  |
| `JWT_SECRET`                  | Secret for signing access tokens     |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime                |
