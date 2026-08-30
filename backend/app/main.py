"""FastAPI application factory and entrypoint."""

from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings
from app.routers.auth import router as auth_router
from app.routers.feedback import router as feedback_router
from app.routers.files import router as files_router
from app.routers.jobs import router as jobs_router
from app.routers.signing import router as signing_router
from app.routers.submissions import router as submissions_router
from app.routers.templates import router as templates_router
from app.routers.users import router as users_router

# frontend/dist, sibling of backend/ at the repo root. Built by `npm run build`
# in frontend/ — see Task 9. Not present until the SPA has been built at least
# once (e.g. a fresh checkout before `npm install && npm run build`), so
# mounting it below is conditional on the directory actually existing.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application.

    ``settings`` defaults to a fresh ``Settings()`` read from the process
    environment. It's stored on ``app.state.settings`` and read from there by
    the ``get_settings`` request dependency (see ``app.auth``), so tests can
    build an app wired to arbitrary config — e.g.
    ``create_app(Settings(dev_auth_bypass=True))`` — without touching env
    vars or the module-level ``app`` below.
    """
    app = FastAPI(title="Pumasi Sign")
    app.state.settings = settings or Settings()

    api_router = APIRouter(prefix="/api")

    @api_router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    app.include_router(auth_router)
    app.include_router(templates_router)
    app.include_router(files_router)
    app.include_router(feedback_router)
    app.include_router(submissions_router)
    app.include_router(signing_router)
    app.include_router(jobs_router)
    app.include_router(users_router)

    if FRONTEND_DIST.is_dir():
        # Serves the built SPA's static assets (JS/CSS bundles, favicon, ...)
        # and index.html for "/". Routes registered above always win for
        # "/api/..." paths since Starlette matches in registration order.
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="spa")

        @app.exception_handler(StarletteHTTPException)
        async def spa_fallback(request: Request, exc: StarletteHTTPException) -> FileResponse | Response:
            """Serve index.html for any non-API 404 so client-side routes (e.g. a
            deep-linked or refreshed `/templates/5/build`) resolve to the SPA
            instead of a bare 404. `/api/...` 404s are untouched — they should
            stay JSON, not fall back to the SPA shell.
            """
            if exc.status_code == 404 and not request.url.path.startswith("/api"):
                index_path = FRONTEND_DIST / "index.html"
                if index_path.is_file():
                    return FileResponse(index_path)
            return await http_exception_handler(request, exc)

    return app


app = create_app()
