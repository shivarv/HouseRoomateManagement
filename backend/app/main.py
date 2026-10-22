import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, chores, health, households, reports, swaps
from app.core.config import settings
from app.services.errors import ServiceError

API_PREFIX = "/api/v1"

app = FastAPI(title="House Roommate Management API")
log = logging.getLogger(__name__)


# Registered before CORS so CORS wraps it: an unexpected crash still returns a JSON 500 with
# CORS headers, and the web app shows an error instead of a bare "Failed to fetch".
@app.middleware("http")
async def unexpected_errors_as_json(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500, content={"detail": "Something went wrong on the server"}
        )


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


for router in (
    health.router,
    auth.router,
    households.router,
    chores.router,
    swaps.router,
    reports.router,
):
    app.include_router(router, prefix=API_PREFIX)
