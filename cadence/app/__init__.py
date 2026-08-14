from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .web.routes.habits import router as habit_router
from .web.routes.days import router as day_router
from .web.routes.auth import (
    InvalidSessionError,
    _clear_auth_cookies,
    router as auth_router,
)
from .web.routes.continuity import router as continuity_router
from .web.routes.contexts import router as context_router
from .web.routes.dev_ai import router as dev_ai_router
from .web.routes.data_portability import router as data_portability_router
from .services.runtime_lock import RuntimeLock
from .services.rate_limit import auth_rate_limiter


logger = logging.getLogger("cadence.app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await auth_rate_limiter.startup()
    try:
        with RuntimeLock(settings.resolved_runtime_lock_path):
            yield
    finally:
        await auth_rate_limiter.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cadence",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
        max_age=600,
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
            "form-action 'self'; object-src 'none'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if request.url.path.startswith("/api/auth/") or request.url.path == "/api/account/export":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception):
        logger.exception(
            "Unhandled request error: %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @app.exception_handler(InvalidSessionError)
    async def handle_invalid_session(request: Request, _error: Exception):
        response = JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"},
        )
        _clear_auth_cookies(response)
        return response

    app.include_router(auth_router, prefix="/api")
    app.include_router(habit_router, prefix="/api")
    app.include_router(day_router, prefix="/api")
    app.include_router(continuity_router, prefix="/api")
    app.include_router(context_router, prefix="/api")
    app.include_router(dev_ai_router, prefix="/api")
    app.include_router(data_portability_router, prefix="/api")

    @app.get("/healthz", include_in_schema=False)
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    if settings.serve_frontend:
        frontend_dir = settings.resolved_frontend_dist_dir
        index_file = frontend_dir / "index.html"
        assets_dir = frontend_dir / "assets"
        if index_file.is_file():
            if assets_dir.is_dir():
                app.mount(
                    "/assets",
                    StaticFiles(directory=assets_dir),
                    name="frontend-assets",
                )

            @app.get("/{path:path}", include_in_schema=False)
            async def serve_frontend(path: str):
                if path == "healthz" or path.startswith("api/"):
                    raise HTTPException(status_code=404)
                return FileResponse(index_file)

    return app


app = create_app()
