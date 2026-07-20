from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.db import init_models
from app.fetcher import Fetcher
from app.proxy import ProxyPool
from app.config import logger, SOURCES
from app.routes import endpoints


def _load_proxies_from_env() -> list[str]:
    raw = os.getenv("PROXY_LIST", "")
    return [p.strip() for p in raw.split(",") if p.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    proxy_pool = ProxyPool(proxies=_load_proxies_from_env(), allow_direct_fallback=True)
    app.state.proxy_pool = proxy_pool
    app.state.fetcher = Fetcher(proxy_pool=proxy_pool)
    logger.info("Started with %d proxies in pool", len(proxy_pool.proxies))

    if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":  #only for local dev. In prod Alembic is used
        await init_models()
        logger.info("Tables created (AUTO_CREATE_TABLES=true)")

    yield


app = FastAPI(title="Marketplace Scraper", lifespan=lifespan)

app.include_router(endpoints.router)


@app.get("/health")
async def health():
    pool: ProxyPool = app.state.proxy_pool
    return {
        "status": "ok",
        "sources": list(SOURCES),
        "proxy_pool": pool.snapshot(),
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled error or %s", request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
