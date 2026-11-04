import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    auth,
    bills,
    chat,
    chores,
    health,
    help,
    households,
    reports,
    shopping,
    swaps,
    voice,
)
from app.core import logs
from app.core.config import settings
from app.services.errors import ServiceError

API_PREFIX = "/api/v1"

logs.configure()
app = FastAPI(title="House Roommate Management API")
log = logging.getLogger("app.requests")


# Registered before CORS so CORS wraps it: an unexpected crash still returns a JSON 500 with
# CORS headers, and the web app shows an error instead of a bare "Failed to fetch".
@app.middleware("http")
async def request_context_and_errors(request: Request, call_next):
    """Gives the request its ref and context (see app.core.logs), logs one line when it's done,
    and turns an unexpected crash into a JSON 500 that tells the user its ref."""
    ctx = logs.start_request(request.method, request.url.path, dict(request.query_params))
    logs.house_from_path(ctx)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        ctx.status = 500
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        response = JSONResponse(
            status_code=500,
            content={
                "detail": f"Something went wrong on the server (ref {ctx.request_id})",
                "error_id": ctx.request_id,
            },
        )
    ctx.status = response.status_code
    response.headers["X-Request-ID"] = ctx.request_id
    if request.url.path != f"{API_PREFIX}/health":  # Render checks it every few seconds
        log.info(
            "%s %s %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={"status": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000)},
        )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.exception_handler(ServiceError)
def handle_service_error(request: Request, exc: ServiceError):
    """Expected refusals (400/403/404/409): one info line, not saved as an error."""
    logging.getLogger("app.refused").info("%s: %s", type(exc).__name__, exc.detail, extra={"status": exc.status_code})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


for router in (
    health.router,
    auth.router,
    households.router,
    chores.router,
    swaps.router,
    help.router,
    shopping.router,
    bills.router,
    chat.router,
    reports.router,
    voice.router,
):
    app.include_router(router, prefix=API_PREFIX)
