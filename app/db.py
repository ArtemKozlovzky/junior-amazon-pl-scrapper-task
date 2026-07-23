from __future__ import annotations

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import database_url

engine = create_async_engine(database_url, pool_pre_ping=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

class Base(DeclarativeBase):
    pass


class ProductRecord(Base):
    __tablename__ = "products"

    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    title: Mapped[str] = mapped_column(String(1024))
    url: Mapped[str] = mapped_column(String(2048))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullet_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    images: Mapped[list | None] = mapped_column(JSON, nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    listing_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detail_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScrapeRequestRecord(Base):
    __tablename__ = "scrape_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50))
    url: Mapped[str] = mapped_column(String(2048))
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impersonate_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    proxy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    was_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ListingQueryRecord(Base):
    __tablename__ = "listing_queries"

    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    query: Mapped[str] = mapped_column(String(512), primary_key=True)
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_ids: Mapped[list] = mapped_column(JSON)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CookieSetRecord(Base):
    __tablename__ = "cookie_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), index=True)

    cookies: Mapped[list] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(String(16), default="active", index=True)

    minting_proxy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    impersonate_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_cookie_sets_source_status_expires", "source", "status", "expires_at"),
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_models() -> None: # Only for local development and tests. Prod uses Alembic migrations
    if __debug__:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)