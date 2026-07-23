from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.fetcher import Fetcher
from app.proxy import ProxyPool
from app.cookies import CookieStore
from app.config import (
    logger, SOURCES, _load_proxies_from_env,
    COOKIES_ENABLED, COOKIE_TARGET_POOL_SIZE, COOKIE_TTL,
)
from app.routes import endpoints
from app.db import init_models, SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    proxy_pool = ProxyPool(proxies=_load_proxies_from_env(), allow_direct_fallback=True)
    app.state.proxy_pool = proxy_pool

    cookie_store = CookieStore(target_pool_size=COOKIE_TARGET_POOL_SIZE, ttl=COOKIE_TTL)
    app.state.cookie_store = cookie_store

    app.state.fetcher = Fetcher(
        proxy_pool=proxy_pool,
        cookie_store=cookie_store if COOKIES_ENABLED else None,
        session_factory=SessionLocal if COOKIES_ENABLED else None,
    )
    logger.info(
        "Started with %d proxies in pool (cookies_enabled=%s)",
        len(proxy_pool.proxies), COOKIES_ENABLED,
    )
    if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
        await init_models()
        logger.info("Tables created (AUTO_CREATE_TABLES=true)")
    yield


app = FastAPI(title="Marketplace Scraper", lifespan=lifespan)

app.include_router(endpoints.router)


@app.get("/health")
async def health():
    pool: ProxyPool = app.state.proxy_pool
    store: CookieStore = app.state.cookie_store
    cookie_pool = {}
    try:
        async with SessionLocal() as db:
            for source in SOURCES:
                cookie_pool[source] = await store.count_active(db, source)
    except Exception:
        logger.exception("health: failed to count active cookie sets")
        cookie_pool = None
    return {
        "status": "ok",
        "sources": list(SOURCES),
        "proxy_pool": pool.snapshot(),
        "cookie_pool_active": cookie_pool,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled error or %s", request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
