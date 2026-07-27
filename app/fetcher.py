from __future__ import annotations

import asyncio
import random
import time
import logging
from dataclasses import dataclass

from typing import TYPE_CHECKING

from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.exceptions import Timeout as CurlTimeout

from app.proxy import ProxyPool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.cookies import CookieStore

logger = logging.getLogger(__name__)

IMPERSONATE_PROFILES = (
    "chrome124",
    "chrome120",
    "chrome110",
    "safari17_0",
)

DEFAULT_HEADERS = {
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

RETRYABLE_STATUS_CODES = {429, 503, 500, 502, 504}

CAPTCHA_MARKERS = (
    "api-services-support@amazon.com",
    "/errors/validateCaptcha",
    "Enter the characters you see below",
)

NOT_FOUND_MARKERS = (
    "Nie znaleziono strony",
    "Przepraszamy! Nie mogliśmy znaleźć tej strony",
    "Looking for something?",
    "Sorry, we couldn't find that page",
)


class FetchError(Exception):
    pass


class CaptchaDetected(FetchError):
    pass


class UpstreamTimeout(FetchError):
    pass


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    proxy_used: str | None
    not_found: bool = False
    attempts: int = 1
    latency_ms: int = 0
    impersonate_profile: str = ""
    was_blocked: bool = False
    cookie_set_id: int | None = None


class Fetcher:
    def __init__(
        self,
        proxy_pool: ProxyPool | None = None,
        max_retries: int = 3,
        timeout: float = 20.0,
        cookie_store: "CookieStore | None" = None,
        session_factory: "async_sessionmaker | None" = None,
    ):
        self.proxy_pool = proxy_pool or ProxyPool(proxies=[], allow_direct_fallback=True)
        self.max_retries = max_retries
        self.timeout = timeout
        self.impersonate = random.choice(IMPERSONATE_PROFILES)
        self.cookie_store = cookie_store
        self.session_factory = session_factory

    async def get(
        self,
        url: str,
        params: dict | None = None,
        extra_headers: dict | None = None,
        source: str | None = None,
    ) -> FetchResult:
        headers = {**DEFAULT_HEADERS, **(extra_headers or {})}
        last_error: Exception | None = None
        started = time.monotonic()
        was_blocked = False

        cookie_id, cookie_dict, impersonate = await self._acquire_cookies(source)

        async with AsyncSession() as session:
            for attempt in range(1, self.max_retries + 1):
                proxy_url = await self.proxy_pool.get_proxy()

                try:
                    resp: Response = await session.get(
                        url,
                        params=params,
                        headers=headers,
                        impersonate=impersonate,
                        proxy=proxy_url,
                        timeout=self.timeout,
                        cookies=cookie_dict,
                    )
                except CurlTimeout as exc:
                    last_error = exc
                    was_blocked = False
                    await self.proxy_pool.mark_failure(proxy_url)
                    logger.warning(
                        "fetch attempt %d/%d timed out: %s [proxy=%s]",
                        attempt, self.max_retries, exc, proxy_url,
                    )
                    await self._backoff(attempt)
                    continue
                except Exception as exc:
                    last_error = exc
                    await self.proxy_pool.mark_failure(proxy_url)
                    logger.warning(
                        "fetch attempt %d/%d failed (network): %s [proxy=%s]",
                        attempt, self.max_retries, exc, proxy_url,
                    )
                    await self._backoff(attempt)
                    continue

                if resp.status_code in RETRYABLE_STATUS_CODES:
                    last_error = FetchError(f"status={resp.status_code}")
                    await self.proxy_pool.mark_failure(proxy_url)
                    logger.warning(
                        "fetch attempt %d/%d got retryable status=%s [proxy=%s]",
                        attempt, self.max_retries, resp.status_code, proxy_url,
                    )
                    await self._backoff(attempt)
                    continue

                if resp.status_code == 200 and self._looks_like_captcha(resp.text):
                    last_error = CaptchaDetected("captcha page returned")
                    was_blocked = True
                    await self.proxy_pool.mark_failure(proxy_url)
                    await self._mark_cookie(cookie_id, burned=True)
                    logger.warning(
                        "fetch attempt %d/%d got captcha page [proxy=%s]",
                        attempt, self.max_retries, proxy_url,
                    )
                    await self._backoff(attempt)
                    continue

                if resp.status_code == 200:
                    await self.proxy_pool.mark_success(proxy_url)
                    await self._mark_cookie(cookie_id, burned=False)

                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    text=resp.text,
                    proxy_used=proxy_url,
                    not_found=self._looks_like_not_found(resp.text),
                    attempts=attempt,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    impersonate_profile=impersonate,
                    was_blocked=was_blocked,
                    cookie_set_id=cookie_id,
                )

            if isinstance(last_error, CurlTimeout):
                raise UpstreamTimeout(
                    f"All {self.max_retries} attempts timed out for {url}"
                ) from last_error

            raise FetchError(
                f"All {self.max_retries} attempts failed for {url}: {last_error}"
            ) from last_error

    async def _acquire_cookies(
        self, source: str | None
    ) -> tuple[int | None, dict | None, str]:
        if not source or self.cookie_store is None or self.session_factory is None:
            return None, None, self.impersonate
        try:
            async with self.session_factory() as db:
                record = await self.cookie_store.acquire(db, source)
                await db.commit()
            if record is None:
                return None, None, self.impersonate
            cookie_dict = {c["name"]: c["value"] for c in record.cookies}
            return record.id, cookie_dict, record.impersonate_profile or self.impersonate
        except Exception:
            logger.exception("cookie acquire failed; proceeding without cookies")
            return None, None, self.impersonate

    async def _mark_cookie(self, cookie_id: int | None, *, burned: bool) -> None:
        if cookie_id is None or self.cookie_store is None or self.session_factory is None:
            return
        try:
            async with self.session_factory() as db:
                if burned:
                    await self.cookie_store.mark_burned(db, cookie_id)
                else:
                    await self.cookie_store.mark_success(db, cookie_id)
                await db.commit()
        except Exception:
            logger.exception("cookie bookkeeping failed [id=%s]", cookie_id)

    @staticmethod
    def _looks_like_captcha(html: str) -> bool:
        return any(marker in html for marker in CAPTCHA_MARKERS)

    @staticmethod
    def _looks_like_not_found(html: str) -> bool:
        return any(marker in html for marker in NOT_FOUND_MARKERS)

    @staticmethod
    async def _backoff(attempt: int) -> None:
        wait = min(2 ** attempt, 30) + random.uniform(0, 1.5)
        await asyncio.sleep(wait)