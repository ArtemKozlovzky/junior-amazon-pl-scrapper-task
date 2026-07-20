from app import crud
from fastapi import APIRouter, Depends, HTTPException, Query
from app.models import ListingItem, ProductDetail
from app.config import logger, FRESHNESS_MAX_AGE
from app.db import get_db_session, AsyncSession
from app.routes.utils import (
    _scrape_listing,
    _scrape_listing_paginated,
    _get_source,
    _fetch,
    _normalize_source,
    get_fetcher,
    Fetcher,
)

router = APIRouter(prefix="/sources/{source}", tags=["Amazon PL"])

@router.get("/listing", response_model=list[ListingItem])
async def get_listing(
    source: str,
    query: str = Query(..., min_length=1, description="Search query / category"),
    page: int = Query(1, ge=1, le=20),
    max_pages: int = Query(
        1, ge=1, le=10
    ),
    force_refresh: bool = Query(False, description="Ignore cache and scrape again"),
    session: AsyncSession = Depends(get_db_session),
    fetcher: Fetcher = Depends(get_fetcher)
):
    if max_pages > 1:
        return await _scrape_listing_paginated(source, query, max_pages, session, fetcher, force_refresh)
    return await _scrape_listing(source, query, page, session, fetcher, force_refresh)


@router.get("/search", response_model=list[ListingItem])
async def search(
    source: str,
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, le=20),
    max_pages: int = Query(
        1, ge=1, le=10
    ),
    force_refresh: bool = Query(False, description="Ignore cache and scrape again"),
    session: AsyncSession = Depends(get_db_session),
    fetcher: Fetcher = Depends(get_fetcher)
):
    if max_pages > 1:
        return await _scrape_listing_paginated(source, q, max_pages, session, fetcher, force_refresh)
    return await _scrape_listing(source, q, page, session, fetcher, force_refresh)


@router.get("/products/{external_id}", response_model=ProductDetail)
async def get_product(
    source: str,
    external_id: str,
    force_refresh: bool = Query(False, description="Ignore cache and scrape again"),
    session: AsyncSession = Depends(get_db_session),
    fetcher: Fetcher = Depends(get_fetcher)
):
    parser = _get_source(source)

    normalized_source = _normalize_source(source)

    if not force_refresh:
        cached = await crud.get_fresh_product(session, normalized_source, external_id, FRESHNESS_MAX_AGE)
        if cached is not None:
            return cached

    url = parser.build_product_url(external_id)

    result = await _fetch(url, fetcher, session, normalized_source)

    if result.status_code == 404 or result.not_found:
        raise HTTPException(status_code=404, detail="Product not found")

    product = parser.parse_product(result.text, external_id)

    try:
        await crud.upsert_product_detail(session, product, raw_html=result.text)
        await session.commit()
    except Exception:
        logger.exception("Failed to save product card in database")

    return product