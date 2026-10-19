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
│   │   └── routes/        # One module per resource: auth.py, households.py, chores.py, expenses.py
│   ├── core/
│   │   ├── config.py      # Settings loaded from env (.env at repo root)
│   │   └── security.py    # Password hashing, JWT encode/decode
│   ├── db/
│   │   ├── session.py     # Engine, SessionLocal, get_db()
│   │   └── base.py        # DeclarativeBase; imports all models for Alembic
│   ├── models/            # SQLAlchemy ORM models (tables)
│   ├── schemas/           # Pydantic request/response models (API shapes)
│   └── services/          # Business logic; routes call services, services use the DB session
├── alembic/
│   └── versions/          # Migration scripts
├── tests/                 # pytest tests (mirrors app/ layout)
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
- **services** hold business rules (e.g. splitting an expense between members).
- **models** describe tables. Schema changes go through an Alembic migration — never edit the DB by hand.
- **schemas** are the public API contract; keep them in sync with [docs/API.md](../docs/API.md).

## Planned data model (initial)

| Table               | Purpose                                     |
| ------------------- | ------------------------------------------- |
| `users`             | Account: email, hashed password, name       |
| `households`        | A shared house                              |
| `household_members` | User ↔ household, with role (owner/member)  |
| `chores`            | Recurring/one-off tasks assigned to members |
| `expenses`          | Shared purchases/bills paid by a member     |
| `expense_splits`    | Each member's share of an expense           |

All tables use UUID primary keys and `created_at` / `updated_at` timestamps (UTC).

## Local setup

```bash
# from repo root
cp .env.example .env
docker compose up -d db

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

alembic upgrade head                      # apply migrations
uvicorn app.main:app --reload --port 8000 # run API
```

- API: http://localhost:8000/api/v1
- Interactive docs (Swagger): http://localhost:8000/docs
- Health check: `GET /api/v1/health`

## Common commands

```bash
alembic revision --autogenerate -m "add chores table"   # new migration
alembic upgrade head                                     # apply
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
