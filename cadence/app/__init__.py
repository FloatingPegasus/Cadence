from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .web.routes.habits import router as habit_router
from .web.routes.days import router as day_router
from .web.routes.auth import router as auth_router
from .web.routes.continuity import router as continuity_router
from .web.routes.contexts import router as context_router
from .web.routes.dev_ai import router as dev_ai_router
from .web.routes.data_portability import router as data_portability_router
from .services.runtime_lock import RuntimeLock


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with RuntimeLock(settings.resolved_runtime_lock_path):
        yield


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
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
