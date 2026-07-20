from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import TypedDict


PRIOR_SUCCESS = 5.0
PRIOR_TOTAL = 10.0

BASE_COOLDOWN_SECONDS = 30.0
MAX_COOLDOWN_SECONDS = 900.0
COOLDOWN_MULTIPLIER = 2.0


@dataclass
class ProxyStats:
    url: str
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    cooldown_until: float = 0.0
    last_used: float = 0.0

    @property
    def score(self) -> float:
        return (self.successes + PRIOR_SUCCESS) / (
            self.successes + self.failures + PRIOR_TOTAL
        )

    def is_in_cooldown(self, now: float) -> bool:
        return self.cooldown_until > now


@dataclass
class ProxyPool:
    proxies: list[str]
    allow_direct_fallback: bool = False

    _stats: dict[str, ProxyStats] = field(default_factory=dict, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        for proxy in self.proxies:
            self._stats[proxy] = ProxyStats(url=proxy)

    async def get_proxy(self) -> str | None:
        if not self.proxies:
            return None

        async with self._lock:
            now = time.monotonic()
            available = [s for s in self._stats.values() if not s.is_in_cooldown(now)]

            if not available:
                if self.allow_direct_fallback:
                    return None
                soonest = min(self._stats.values(), key=lambda s: s.cooldown_until)
                return soonest.url

            weights = [s.score for s in available]
            chosen = random.choices(available, weights=weights, k=1)[0]
            chosen.last_used = now
            return chosen.url

    async def mark_success(self, proxy_url: str | None) -> None:
        if proxy_url is None or proxy_url not in self._stats:
            return
        async with self._lock:
            stats = self._stats[proxy_url]
            stats.successes += 1
            stats.consecutive_failures = 0
            stats.cooldown_until = 0.0

    async def mark_failure(self, proxy_url: str | None) -> None:
        if proxy_url is None or proxy_url not in self._stats:
            return
        async with self._lock:
            stats = self._stats[proxy_url]
            stats.failures += 1
            stats.consecutive_failures += 1

            cooldown = min(
                BASE_COOLDOWN_SECONDS * (COOLDOWN_MULTIPLIER ** (stats.consecutive_failures - 1)),
                MAX_COOLDOWN_SECONDS,
            )
            stats.cooldown_until = time.monotonic() + cooldown


    class ProxySnapshot(TypedDict):
        url: str
        score: float
        successes: int
        failures: int
        in_cooldown: bool
        cooldown_remaining: float

    def snapshot(self) -> list[ProxySnapshot]:
        now = time.monotonic()
        return [
            {
                "url": s.url,
                "score": round(s.score, 3),
                "successes": s.successes,
                "failures": s.failures,
                "in_cooldown": s.is_in_cooldown(now),
                "cooldown_remaining": max(0.0, round(s.cooldown_until - now, 1)),
            }
            for s in self._stats.values()
        ]