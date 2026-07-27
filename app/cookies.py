from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CookieSetRecord
from app.proxy import PRIOR_SUCCESS, PRIOR_TOTAL

ACTIVE = "active"
USED = "used"
EXPIRED = "expired"
BURNED = "burned"

ACQUIRE_CANDIDATE_LIMIT = 20


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _score(record: CookieSetRecord) -> float:
    return (record.success_count + PRIOR_SUCCESS) / (
        record.success_count + record.failure_count + PRIOR_TOTAL
    )


class CookieStore:

    def __init__(
        self,
        target_pool_size: int = 5,
        ttl: timedelta = timedelta(hours=6),
    ):
        self.target_pool_size = target_pool_size
        self.ttl = ttl

    async def acquire(self, session: AsyncSession, source: str) -> CookieSetRecord | None:
        stmt = (
            select(CookieSetRecord)
            .where(
                CookieSetRecord.source == source,
                CookieSetRecord.status == ACTIVE,
                (
                    CookieSetRecord.expires_at.is_(None)
                    | (CookieSetRecord.expires_at > utc_now())
                ),
            )
            .order_by(CookieSetRecord.last_used_at.asc().nulls_first())
            .limit(ACQUIRE_CANDIDATE_LIMIT)
            .with_for_update(skip_locked=True)
        )
        rows = (await session.execute(stmt)).scalars().all()
        if not rows:
            return None

        weights = [_score(r) for r in rows]
        chosen = random.choices(rows, weights=weights, k=1)[0]
        chosen.last_used_at = utc_now()
        await session.flush()
        return chosen

    async def mark_success(self, session: AsyncSession, cookie_id: int) -> None:
        await session.execute(
            update(CookieSetRecord)
            .where(CookieSetRecord.id == cookie_id)
            .values(
                success_count=CookieSetRecord.success_count + 1,
                consecutive_failures=0,
                last_used_at=utc_now(),
            )
        )

    async def mark_burned(self, session: AsyncSession, cookie_id: int) -> None:
        await session.execute(
            update(CookieSetRecord)
            .where(CookieSetRecord.id == cookie_id)
            .values(
                status=BURNED,
                failure_count=CookieSetRecord.failure_count + 1,
                consecutive_failures=CookieSetRecord.consecutive_failures + 1,
            )
        )

    async def add(
        self,
        session: AsyncSession,
        source: str,
        *,
        cookies: list[dict],
        minting_proxy: str | None,
        user_agent: str | None,
        impersonate_profile: str | None,
        expires_at: datetime | None,
    ) -> CookieSetRecord:
        record = CookieSetRecord(
            source=source,
            cookies=cookies,
            status=ACTIVE,
            minting_proxy=minting_proxy,
            user_agent=user_agent,
            impersonate_profile=impersonate_profile,
            expires_at=expires_at,
        )
        session.add(record)
        await session.flush()
        return record

    async def count_active(
        self,
        session: AsyncSession,
        source: str,
        min_remaining: timedelta = timedelta(0),
    ) -> int:
        threshold = utc_now() + min_remaining
        result = await session.execute(
            select(func.count())
            .select_from(CookieSetRecord)
            .where(
                CookieSetRecord.source == source,
                CookieSetRecord.status == ACTIVE,
                (
                    CookieSetRecord.expires_at.is_(None)
                    | (CookieSetRecord.expires_at > threshold)
                ),
            )
        )
        return int(result.scalar_one())

    async def prune_expired(self, session: AsyncSession, source: str | None = None) -> int:
        stmt = update(CookieSetRecord).where(
            CookieSetRecord.status == ACTIVE,
            CookieSetRecord.expires_at.isnot(None),
            CookieSetRecord.expires_at <= utc_now(),
        )
        if source is not None:
            stmt = stmt.where(CookieSetRecord.source == source)
        result = await session.execute(stmt.values(status=EXPIRED))
        return result.rowcount or 0
