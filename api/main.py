"""FastAPI application entrypoint, startup wiring, and top-level exception handlers."""
from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.dependencies import Repositories
from api.routes import router
from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import close_connection, get_ardhi_connection, get_ecocrop_connection, get_hwsd_connection
from ardhi.db.ecocrop import EcoCropRepository
from ardhi.db.hwsd import HwsdRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ardhi_conn = get_ardhi_connection()
    hwsd_conn = get_hwsd_connection()
    ecocrop_conn = get_ecocrop_connection()

    app.state.repositories = Repositories(
        ardhi=ArdhiRepository(ardhi_conn),
        hwsd=HwsdRepository(hwsd_conn),
        ecocrop=EcoCropRepository(ecocrop_conn),
    )

    try:
        yield
    finally:
        close_connection(ardhi_conn)
        close_connection(hwsd_conn)
        close_connection(ecocrop_conn)


@asynccontextmanager
async def noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(
    repositories: Repositories | None = None,
    lifespan_enabled: bool = True,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(
        title="Backend API",
        version="1.0.0",
        lifespan=lifespan if lifespan_enabled else noop_lifespan,
    )
    app.include_router(router)

    if repositories is not None:
        app.state.repositories = repositories

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"status": "error", "detail": str(exc)})

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError):
        return JSONResponse(status_code=404, content={"status": "error", "detail": str(exc)})

    return app


app = create_app()
