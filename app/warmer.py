from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from urllib.parse import urlsplit

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import (
    logger,
    SOURCES,
    _load_proxies_from_env,
    COOKIE_TARGET_POOL_SIZE,
    COOKIE_TTL,
    WARMER_ENABLED,
    WARMER_HEADLESS,
    WARMER_REFRESH_INTERVAL,
    WARMER_REFRESH_MARGIN,
)
from app.cookies import CookieStore, utc_now
from app.db import SessionLocal
from app.fetcher import CAPTCHA_MARKERS
from app.proxy import ProxyPool

PROFILE_USER_AGENTS = {
    "chrome124": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "chrome120": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "chrome110": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
}
WARMER_PROFILES = list(PROFILE_USER_AGENTS)

WARM_QUERIES = ("laptop", "ekspresy do kawy", "słuchawki", "książka", "buty do biegania")

BLOCK_MARKERS = CAPTCHA_MARKERS + (
    "Wprowadź znaki",
    "Wpisz znaki, które widzisz poniżej",
)


def proxy_to_playwright(proxy_url: str | None) -> dict | None:
    if not proxy_url:
        return None
    if "://" not in proxy_url:
        proxy_url = "http://" + proxy_url
    parts = urlsplit(proxy_url)
    proxy: dict = {"server": f"{parts.scheme}://{parts.hostname}:{parts.port}"}
    if parts.username:
        proxy["username"] = parts.username
    if parts.password:
        proxy["password"] = parts.password
    return proxy


def compute_expires_at(cookies: list[dict], ttl) -> datetime:
    ttl_deadline = utc_now() + ttl
    real = [c["expires"] for c in cookies if c.get("expires", -1) and c["expires"] > 0]
    if real:
        earliest = datetime.fromtimestamp(min(real), tz=timezone.utc)
        return min(ttl_deadline, earliest)
    return ttl_deadline


def _looks_blocked(html: str) -> bool:
    return any(marker in html for marker in BLOCK_MARKERS)


async def mint_cookie_set(
    source: str,
    proxy_url: str | None,
    store: CookieStore,
    *,
    headless: bool,
) -> bool:
    from patchright.async_api import async_playwright

    profile = random.choice(WARMER_PROFILES)
    user_agent = PROFILE_USER_AGENTS[profile]
    proxy_cfg = proxy_to_playwright(proxy_url)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless, proxy=proxy_cfg)
            try:
                context = await browser.new_context(locale="pl-PL", user_agent=user_agent)
                page = await context.new_page()
                await page.goto(
                    "https://www.amazon.pl/", wait_until="domcontentloaded", timeout=45000
                )

                try:
                    await page.click("#sp-cc-accept", timeout=5000)
                except Exception:
                    pass

                if _looks_blocked(await page.content()):
                    logger.warning("warmer: block wall on landing [proxy=%s]", proxy_url)
                    return False

                try:
                    await page.fill("#twotabsearchtextbox", random.choice(WARM_QUERIES))
                    await page.press("#twotabsearchtextbox", "Enter")
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    if _looks_blocked(await page.content()):
                        logger.warning("warmer: block wall after search [proxy=%s]", proxy_url)
                        return False
                except Exception:
                    logger.debug("warmer: warm-up search skipped", exc_info=True)

                raw_cookies = await context.cookies()
                if not raw_cookies:
                    logger.warning("warmer: no cookies harvested [proxy=%s]", proxy_url)
                    return False

                expires_at = compute_expires_at(raw_cookies, store.ttl)
                async with SessionLocal() as db:
                    await store.add(
                        db,
                        source,
                        cookies=raw_cookies,
                        minting_proxy=proxy_url,
                        user_agent=user_agent,
                        impersonate_profile=profile,
                        expires_at=expires_at,
                    )
                    await db.commit()

                logger.info(
                    "warmer: minted %d cookies for %s [profile=%s proxy=%s expires=%s]",
                    len(raw_cookies), source, profile, proxy_url, expires_at.isoformat(),
                )
                return True
            finally:
                await browser.close()
    except Exception:
        logger.exception("warmer: mint failed [proxy=%s]", proxy_url)
        return False


async def warm_source(
    store: CookieStore,
    proxy_pool: ProxyPool,
    source: str,
    *,
    headless: bool,
    margin,
    target: int,
) -> None:
    async with SessionLocal() as db:
        pruned = await store.prune_expired(db, source)
        await db.commit()
        healthy = await store.count_active(db, source, min_remaining=margin)

    deficit = max(0, target - healthy)
    logger.info(
        "warmer: source=%s healthy=%d/%d deficit=%d pruned=%d",
        source, healthy, target, deficit, pruned,
    )

    for _ in range(deficit):
        proxy_url = await proxy_pool.get_proxy()
        ok = await mint_cookie_set(source, proxy_url, store, headless=headless)
        if ok:
            await proxy_pool.mark_success(proxy_url)
        else:
            await proxy_pool.mark_failure(proxy_url)


async def _amain() -> None:
    if not WARMER_ENABLED:
        logger.info("warmer: disabled (WARMER_ENABLED=false), exiting")
        return

    proxy_pool = ProxyPool(proxies=_load_proxies_from_env(), allow_direct_fallback=True)
    store = CookieStore(target_pool_size=COOKIE_TARGET_POOL_SIZE, ttl=COOKIE_TTL)

    async def job() -> None:
        for source in SOURCES:
            await warm_source(
                store, proxy_pool, source,
                headless=WARMER_HEADLESS,
                margin=WARMER_REFRESH_MARGIN,
                target=COOKIE_TARGET_POOL_SIZE,
            )

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        job,
        "interval",
        seconds=WARMER_REFRESH_INTERVAL,
        next_run_time=datetime.now(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "warmer: started (interval=%ss target=%d headless=%s proxies=%d)",
        WARMER_REFRESH_INTERVAL, COOKIE_TARGET_POOL_SIZE, WARMER_HEADLESS,
        len(proxy_pool.proxies),
    )

    await asyncio.Event().wait()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(_amain())
    except (KeyboardInterrupt, SystemExit):
        logger.info("warmer: shutting down")


if __name__ == "__main__":
    main()
