"""Application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from cache_service.api import router
from cache_service.db import engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await engine.dispose()


app = FastAPI(
    title="Caching Service",
    description=(
        "Generates payloads from two lists of strings and caches the expensive "
        "part - the transformer call - so repeated work is never repeated."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
