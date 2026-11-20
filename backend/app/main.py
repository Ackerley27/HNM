import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.database.session import (
    build_engine,
    build_session_factory,
    get_db,
    session_dependency,
)
from app.workers.collector import run_collector_worker


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    owns_engine = engine is None
    database_engine = engine or build_engine(settings.database_url)
    session_factory = build_session_factory(database_engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        worker_task: asyncio.Task[None] | None = None
        if settings.app_env != "test":
            worker_task = asyncio.create_task(
                run_collector_worker(settings, session_factory)
            )
        try:
            yield
        finally:
            if worker_task is not None:
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass
            if owns_engine:
                await asyncio.to_thread(database_engine.dispose)

    application = FastAPI(
        title="Hospital Network Monitoring API",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(api_router)
    application.dependency_overrides[get_db] = session_dependency(session_factory)
    application.state.database_engine = database_engine
    application.state.settings = settings

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
