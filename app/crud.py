from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ProductRecord, ScrapeRequestRecord, ListingQueryRecord
from app.models import ListingItem, ProductDetail


_LISTING_FIELDS = (
    "title", "url", "price", "currency", "rating",
    "reviews_count", "image_url", "listing_scraped_at",
)


_DETAIL_FIELDS = (
    "title", "url", "price", "currency", "rating", "reviews_count",
    "description", "bullet_points", "attributes", "images",
    "in_stock", "detail_scraped_at", "raw_html",
)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _upsert(
    session: AsyncSession,
    values: dict | list,
    fields: tuple[str, ...],
) -> None:
    stmt = insert(ProductRecord).values(values)

    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "external_id"],
        set_={field: stmt.excluded[field] for field in fields},
    )

    await session.execute(stmt)


async def upsert_listing_items(session: AsyncSession, items: list[ListingItem]) -> None:
    if not items:
        return

    values = [
        {
            "source": item.source,
            "external_id": item.external_id,
            "title": item.title,
            "url": str(item.url),
            "price": item.price,
            "currency": item.currency,
            "rating": item.rating,
            "reviews_count": item.reviews_count,
            "image_url": str(item.image_url) if item.image_url else None,
            "listing_scraped_at": utc_now(),
        }
        for item in items
    ]
    await _upsert(
        session,
        values,
        _LISTING_FIELDS,
    )


async def upsert_product_detail(
    session: AsyncSession, product: ProductDetail, raw_html: str | None = None
) -> None:
    values = {
        "source": product.source,
        "external_id": product.external_id,
        "title": product.title,
        "url": str(product.url),
        "price": product.price,
        "currency": product.currency,
        "rating": product.rating,
        "reviews_count": product.reviews_count,
        "description": product.description,
        "bullet_points": product.bullet_points,
        "attributes": product.attributes,
        "images": [str(img) for img in product.images],
        "in_stock": product.in_stock,
        "detail_scraped_at": utc_now(),
        "raw_html": raw_html,
    }
    await _upsert(
        session,
        values,
        _DETAIL_FIELDS,
    )


async def get_fresh_product(
    session: AsyncSession,
    source: str,
    external_id: str,
    max_age: timedelta,
) -> ProductDetail | None:
    result = await session.execute(
        select(ProductRecord).where(
            ProductRecord.source == source,
            ProductRecord.external_id == external_id,
        )
    )
    record = result.scalar_one_or_none()

    if record is None or record.detail_scraped_at is None:
        return None

    age = utc_now() - record.detail_scraped_at
    if age > max_age:
        return None

    return ProductDetail(
        source=record.source,
        external_id=record.external_id,
        title=record.title,
        url=record.url,
        price=record.price,
        currency=record.currency,
        rating=record.rating,
        reviews_count=record.reviews_count,
        description=record.description,
        bullet_points=record.bullet_points or [],
        attributes=record.attributes or {},
        images=record.images or [],
        in_stock=record.in_stock,
        scraped_at=record.detail_scraped_at,
    )


async def upsert_listing_query(
    session: AsyncSession, source: str, query: str, page: int, external_ids: list[str]
) -> None:
    stmt = insert(ListingQueryRecord).values(
        source=source, query=query, page=page,
        external_ids=external_ids, scraped_at=utc_now(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "query", "page"],
        set_={"external_ids": stmt.excluded.external_ids, "scraped_at": stmt.excluded.scraped_at},
    )
    await session.execute(stmt)


async def get_fresh_listing(
    session: AsyncSession, source: str, query: str, page: int, max_age: timedelta,
) -> list[ListingItem] | None:
    result = await session.execute(
        select(ListingQueryRecord).where(
            ListingQueryRecord.source == source,
            ListingQueryRecord.query == query,
            ListingQueryRecord.page == page,
        )
    )
    query_record = result.scalar_one_or_none()
    if query_record is None:
        return None

    if utc_now() - query_record.scraped_at > max_age:
        return None

    if not query_record.external_ids:
        return []

    rows = await session.execute(
        select(ProductRecord).where(
            ProductRecord.source == source,
            ProductRecord.external_id.in_(query_record.external_ids),
        )
    )
    by_id = {r.external_id: r for r in rows.scalars().all()}

    items: list[ListingItem] = []
    for external_id in query_record.external_ids:
        record = by_id.get(external_id)
        if record is None:
            return None
        items.append(
            ListingItem(
                source=record.source,
                external_id=record.external_id,
                title=record.title,
                url=record.url,
                price=record.price,
                currency=record.currency,
                rating=record.rating,
                reviews_count=record.reviews_count,
                image_url=record.image_url,
                scraped_at=record.listing_scraped_at or query_record.scraped_at,
            )
        )
    return items


async def log_scrape_request(
    session: AsyncSession,
    *,
    source: str,
    url: str,
    status_code: int | None,
    latency_ms: int | None,
    impersonate_profile: str | None,
    proxy: str | None,
    attempt: int | None,
    was_blocked: bool,
    error: str | None = None,
) -> None:
    await session.execute(
        insert(ScrapeRequestRecord).values(
            source=source,
            url=url,
            status_code=status_code,
            latency_ms=latency_ms,
            impersonate_profile=impersonate_profile,
            proxy=proxy,
            attempt=attempt,
            was_blocked=was_blocked,
            error=error,
        )
    )