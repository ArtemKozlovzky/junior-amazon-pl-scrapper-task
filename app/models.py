from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, HttpUrl

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ListingItem(BaseModel):
    source: str  # "amazon_pl", "allegro_pl", ...
    external_id: str
    title: str
    url: HttpUrl | str
    price: Decimal | None
    currency: str | None
    rating: float | None  # 0.0–5.0, normalized when parsed
    reviews_count: int | None
    image_url: HttpUrl | None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductDetail(BaseModel):
    source: str
    external_id: str
    title: str
    url: HttpUrl
    price: Decimal | None
    currency: str | None
    rating: float | None
    reviews_count: int | None
    description: str | None
    bullet_points: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    images: list[HttpUrl] = Field(default_factory=list)
    in_stock: bool | None
    scraped_at: datetime = Field(default_factory=utcnow)
