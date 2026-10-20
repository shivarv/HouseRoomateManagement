from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, chores, health, households
from app.core.config import settings
from app.services.errors import ServiceError

API_PREFIX = "/api/v1"

app = FastAPI(title="House Roommate Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
def handle_service_error(_: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


for router in (health.router, auth.router, households.router, chores.router):
    app.include_router(router, prefix=API_PREFIX)
