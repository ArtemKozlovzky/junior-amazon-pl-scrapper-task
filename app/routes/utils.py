from __future__ import annotations

import asyncio
import random

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.fetcher import Fetcher, FetchError, CaptchaDetected, UpstreamTimeout, FetchResult
from app.sources.base import SourceParser
from app.models import ListingItem
from app.config import logger, SOURCES, FRESHNESS_MAX_AGE

PAGINATION_DELAY_RANGE = (1.0, 2.0)
DEFAULT_MAX_PAGES = 10


def get_fetcher(request: Request) -> Fetcher:
    return request.app.state.fetcher

def _normalize_source(source: str) -> str:
    return source.replace("-", "_")


def _get_source(source: str) -> SourceParser:
    parser = SOURCES.get(_normalize_source(source))
    if parser is None:
        available = ", ".join(name.replace("_", "-") for name in SOURCES)
        raise HTTPException(
            status_code=404,
            detail=f"Unsupported source={source!r}. Available: {available}",
        )
    return parser

async def _fetch(
    url: str,
    fetcher: Fetcher,
    session: AsyncSession,
    source: str,
) -> FetchResult:
    try:
        result = await fetcher.get(url, source=source)
    except CaptchaDetected as exc:
        await _log_fetch_failure(session, source, url, exc, was_blocked=True)
        raise HTTPException(status_code=502, detail=f"Source returned CAPTCHA: {exc}")
    except UpstreamTimeout as exc:
        await _log_fetch_failure(session, source, url, exc, was_blocked=False)
        raise HTTPException(status_code=504, detail=f"Request timed out: {exc}")
    except FetchError as exc:
        await _log_fetch_failure(session, source, url, exc, was_blocked=False)
        raise HTTPException(
            status_code=502,
            detail=f"Source is unavailable or blocked the request: {exc}",
        )

    await _log_fetch_success(session, source, result)
    return result


async def _log_fetch_success(session: AsyncSession, source: str, result: FetchResult) -> None:
    try:
        await crud.log_scrape_request(
            session, source=source, url=result.url, status_code=result.status_code,
            latency_ms=result.latency_ms, impersonate_profile=result.impersonate_profile,
            proxy=result.proxy_used, attempt=result.attempts, was_blocked=result.was_blocked,
        )
        await session.commit()
    except Exception:
        logger.exception("Failed to write scrape_requests log")


async def _log_fetch_failure(
    session: AsyncSession, source: str, url: str, exc: Exception, *, was_blocked: bool
) -> None:
    try:
        await crud.log_scrape_request(
            session, source=source, url=url, status_code=None, latency_ms=None,
            impersonate_profile=None, proxy=None, attempt=None,
            was_blocked=was_blocked, error=str(exc),
        )
        await session.commit()
    except Exception:
        logger.exception("Failed to write scrape_requests log")


async def _scrape_listing(
    source: str, query: str, page: int, session: AsyncSession, fetcher: Fetcher,
    force_refresh: bool = False,
) -> list[ListingItem]:
    parser = _get_source(source)
    normalized_source = _normalize_source(source)

    if not force_refresh:
        cached = await crud.get_fresh_listing(session, normalized_source, query, page, FRESHNESS_MAX_AGE)
        if cached is not None:
            return cached

    url = parser.build_search_url(query, page=page)

    result = await _fetch(url, fetcher, session, normalized_source)

    items = parser.parse_listing(result.text)

    try:
        await crud.upsert_listing_items(session, items)
        await crud.upsert_listing_query(
            session, normalized_source, query, page, [i.external_id for i in items]
        )
        await session.commit()
    except Exception:
        logger.exception("Failed to save data in database")

    return items


async def _scrape_listing_paginated(
    source: str,
    query: str,
    max_pages: int,
    session: AsyncSession,
    fetcher: Fetcher,
    force_refresh: bool = False,
) -> list[ListingItem]:
    seen_ids: set[str] = set()
    all_items: list[ListingItem] = []

    for page in range(1, max_pages + 1):
        page_items = await _scrape_listing(
            source, query, page, session, fetcher, force_refresh=force_refresh
        )

        if not page_items:
            logger.info(
                "Pagination stopped for query=%r: page %d returned no results "
                "(last page reached)",
                query, page,
            )
            break

        for item in page_items:
            if item.external_id in seen_ids:
                continue
            seen_ids.add(item.external_id)
            all_items.append(item)

        if page < max_pages:
            delay = random.uniform(*PAGINATION_DELAY_RANGE)
            logger.debug("Sleeping %.2fs before fetching page %d", delay, page + 1)
            await asyncio.sleep(delay)

    return all_items