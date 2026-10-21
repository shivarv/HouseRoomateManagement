from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    # Neon closes idle connections (scale to zero); check before reuse and recycle periodically.
    pool_pre_ping=True,
    pool_recycle=300,
    # Behind Neon's PgBouncer (transaction mode) a connection can change between statements,
    # so don't let psycopg create server-side prepared statements.
    connect_args={"prepare_threshold": None} if settings.uses_pgbouncer else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
