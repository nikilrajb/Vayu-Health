from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import ROOT

from app import __version__
from app.api import router
from app.config import get_settings
from app.data import ensure_sample_files


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_sample_files()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Vayu Health API",
        description=(
            "24-hour PM2.5 / PM10 forecasting, public-health alerts, "
            "and industrial emission-reduction recommendations."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)

    @application.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "vayu-health", "version": __version__}

    web_dir = ROOT / "frontend" / "dist"
    if web_dir.exists():
        application.mount(
            "/", StaticFiles(directory=web_dir, html=True), name="website"
        )
    return application


app = create_app()
