from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import app.services.audit  # noqa: F401  (registers the session hooks that write the audit trail)
from app.api import (
    routes_accounts,
    routes_changes,
    routes_execution,
    routes_insight,
    routes_operations,
    routes_validation,
)
from app.core.config import BACKEND_DIR, get_settings
from app.core.errors import DomainError

API_DESCRIPTION = (
    "ValiTrack API. Software validation and change control tracker: applications, requirements and risk, "
    "IQ/OQ/PQ test execution, change control with electronic signatures and a hash-chained audit trail."
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ValiTrack", version="1.0.0", description=API_DESCRIPTION,
        docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse({"detail": error.message}, status_code=error.status_code)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/") and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response

    for module in (routes_accounts, routes_validation, routes_execution, routes_changes,
                   routes_operations, routes_insight):
        app.include_router(module.router)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React app from the same server, so the whole product is one process."""
    settings = get_settings()
    static_dir = Path(settings.static_dir) if settings.static_dir else BACKEND_DIR / "static"
    index = static_dir / "index.html"
    if not index.exists():
        return
    assets = static_dir / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found."}, status_code=404)
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
