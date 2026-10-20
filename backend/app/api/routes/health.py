from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
