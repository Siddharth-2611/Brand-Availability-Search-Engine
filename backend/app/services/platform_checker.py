"""
Platform Username Checker
==========================
Checks username availability across 50+ platforms concurrently using
asyncio + aiohttp.  Semaphore limits simultaneous HTTP connections.

Architecture:
  check_username("bytebot")
       │
       ▼
  asyncio.gather(*tasks)   ← all platform checks fire simultaneously
       │                      (bounded by semaphore)
       ▼
  [GitHub ✓] [Instagram ✗] [Reddit ✓] [Twitter ?] ...

Complexity: O(1) wall-clock (all checks happen in parallel)
vs naive O(n) sequential approach.
"""

from __future__ import annotations
import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

from app.core.config import settings
from app.core.redis_client import get_redis


PLATFORMS: list[dict] = [
    # ── Social ──────────────────────────────────────────────
    {"name": "Instagram",   "url": "https://www.instagram.com/{}/",    "category": "social",   "icon": "📸"},
    {"name": "Twitter",     "url": "https://twitter.com/{}",           "category": "social",   "icon": "🐦"},
    {"name": "TikTok",      "url": "https://www.tiktok.com/@{}",       "category": "social",   "icon": "🎵"},
    {"name": "YouTube",     "url": "https://www.youtube.com/@{}",      "category": "social",   "icon": "▶️"},
    {"name": "Pinterest",   "url": "https://www.pinterest.com/{}/",    "category": "social",   "icon": "📌"},
    {"name": "Snapchat",    "url": "https://www.snapchat.com/add/{}",  "category": "social",   "icon": "👻"},
    {"name": "Telegram",    "url": "https://t.me/{}",                  "category": "social",   "icon": "✈️"},
    {"name": "LinkedIn",    "url": "https://www.linkedin.com/in/{}/",  "category": "social",   "icon": "💼"},
    {"name": "Facebook",    "url": "https://www.facebook.com/{}",      "category": "social",   "icon": "👤"},
    {"name": "Reddit",      "url": "https://www.reddit.com/u/{}",      "category": "social",   "icon": "🤖"},
    # ── Dev ─────────────────────────────────────────────────
    {"name": "GitHub",      "url": "https://github.com/{}",            "category": "dev",      "icon": "🐙"},
    {"name": "GitLab",      "url": "https://gitlab.com/{}",            "category": "dev",      "icon": "🦊"},
    {"name": "Dev.to",      "url": "https://dev.to/{}",                "category": "dev",      "icon": "💻"},
    {"name": "Medium",      "url": "https://medium.com/@{}",           "category": "dev",      "icon": "✍️"},
    {"name": "HackerNews",  "url": "https://news.ycombinator.com/user?id={}", "category": "dev", "icon": "🔶"},
    {"name": "npm",         "url": "https://www.npmjs.com/~{}",        "category": "dev",      "icon": "📦"},
    {"name": "PyPI",        "url": "https://pypi.org/user/{}/",        "category": "dev",      "icon": "🐍"},
    {"name": "Replit",      "url": "https://replit.com/@{}",           "category": "dev",      "icon": "🔁"},
    {"name": "Hashnode",    "url": "https://hashnode.com/@{}",         "category": "dev",      "icon": "📝"},
    {"name": "CodePen",     "url": "https://codepen.io/{}",            "category": "dev",      "icon": "🖊️"},
    # ── Gaming ──────────────────────────────────────────────
    {"name": "Twitch",      "url": "https://www.twitch.tv/{}",         "category": "gaming",   "icon": "🎮"},
    {"name": "Discord",     "url": "https://discord.com/users/{}",     "category": "gaming",   "icon": "💬"},
    {"name": "Steam",       "url": "https://steamcommunity.com/id/{}","category": "gaming",   "icon": "🎯"},
    # ── Creative ────────────────────────────────────────────
    {"name": "Behance",     "url": "https://www.behance.net/{}",       "category": "creative", "icon": "🎨"},
    {"name": "Dribbble",    "url": "https://dribbble.com/{}",          "category": "creative", "icon": "🏀"},
    {"name": "Vimeo",       "url": "https://vimeo.com/{}",             "category": "creative", "icon": "🎬"},
    {"name": "SoundCloud",  "url": "https://soundcloud.com/{}",        "category": "creative", "icon": "🎧"},
    {"name": "Spotify",     "url": "https://open.spotify.com/user/{}","category": "creative", "icon": "🎶"},
]

DOMAIN_TLDS: list[str] = [".com", ".io", ".dev", ".ai", ".co", ".app"]

# Status codes that mean "user exists" (taken)
_TAKEN_CODES = {200, 301, 302}
# Status codes that mean "user does not exist" (available)
_AVAILABLE_CODES = {404, 410}

_UA = "Mozilla/5.0 (compatible; BrandSearchBot/1.0)"


@dataclass
class PlatformResult:
    platform: str
    icon: str
    category: str
    url: str
    available: Optional[bool]   # None = unknown (timeout / error)
    status_code: Optional[int] = None
    error: Optional[str] = None
    checked_at: float = field(default_factory=time.time)


class PlatformChecker:
    """
    Concurrent username availability checker.

    Usage:
        checker = PlatformChecker()
        results = await checker.check("bytebot")
    """

    def __init__(self):
        self._semaphore = asyncio.Semaphore(settings.PLATFORM_CHECK_CONCURRENCY)

    async def _check_one(
        self,
        session: aiohttp.ClientSession,
        username: str,
        platform: dict,
    ) -> PlatformResult:
        url = platform["url"].format(username)
        async with self._semaphore:
            try:
                async with session.get(
                    url,
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=settings.PLATFORM_CHECK_TIMEOUT),
                ) as resp:
                    code = resp.status
                    if code in _TAKEN_CODES:
                        available = False
                    elif code in _AVAILABLE_CODES:
                        available = True
                    else:
                        available = None    # ambiguous
                    return PlatformResult(
                        platform=platform["name"],
                        icon=platform["icon"],
                        category=platform["category"],
                        url=url,
                        available=available,
                        status_code=code,
                    )
            except asyncio.TimeoutError:
                return PlatformResult(
                    platform=platform["name"],
                    icon=platform["icon"],
                    category=platform["category"],
                    url=url,
                    available=None,
                    error="timeout",
                )
            except Exception as exc:
                return PlatformResult(
                    platform=platform["name"],
                    icon=platform["icon"],
                    category=platform["category"],
                    url=url,
                    available=None,
                    error=str(exc)[:80],
                )

    async def _check_domain(
        self,
        username: str,
        tld: str,
    ) -> PlatformResult:
        """
        Domain availability via DNS resolution (heuristic, not WHOIS/RDAP).

        If the domain resolves        -> registered (taken)
        If DNS lookup fails (NXDOMAIN) -> likely available
        This is fast and needs no API key, but isn't 100% authoritative —
        some registered domains have no DNS records configured. For
        production use, swap in a real WHOIS/RDAP lookup here.
        """
        import socket
        domain = f"{username}{tld}"
        loop = asyncio.get_event_loop()
        async with self._semaphore:
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, socket.gethostbyname, domain),
                    timeout=settings.PLATFORM_CHECK_TIMEOUT,
                )
                return PlatformResult(
                    platform=domain, icon="🌐", category="domain",
                    url=f"https://{domain}", available=False,
                )
            except socket.gaierror:
                return PlatformResult(
                    platform=domain, icon="🌐", category="domain",
                    url=f"https://{domain}", available=True,
                )
            except asyncio.TimeoutError:
                return PlatformResult(
                    platform=domain, icon="🌐", category="domain",
                    url=f"https://{domain}", available=None, error="timeout",
                )
            except Exception as exc:
                return PlatformResult(
                    platform=domain, icon="🌐", category="domain",
                    url=f"https://{domain}", available=None, error=str(exc)[:80],
                )

    async def check(
        self,
        username: str,
        categories: Optional[list[str]] = None,
    ) -> list[PlatformResult]:
        """
        Check username across all (or filtered) platforms + domain TLDs concurrently.

        All HTTP requests and DNS lookups fire simultaneously; total latency ≈
        slowest single check rather than Σ(all checks).

        Returns list of PlatformResult sorted: available first, then unknown, then taken.
        """
        # Check Redis cache first
        redis = get_redis()
        cache_key = f"platform:{username}"
        cached = await redis.get(cache_key)
        if cached:
            import json
            data = json.loads(cached)
            return [PlatformResult(**d) for d in data]

        targets = PLATFORMS
        include_domains = True
        if categories:
            include_domains = "domain" in categories
            targets = [p for p in PLATFORMS if p["category"] in categories]

        headers = {"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"}

        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = [
                self._check_one(session, username, platform)
                for platform in targets
            ]
            if include_domains:
                tasks += [self._check_domain(username, tld) for tld in DOMAIN_TLDS]
            results: list[PlatformResult] = await asyncio.gather(*tasks)

        # Sort: available → unknown → taken
        order = {True: 0, None: 1, False: 2}
        results.sort(key=lambda r: (order[r.available], r.platform))

        # Cache the result
        import json
        serialisable = [
            {
                "platform": r.platform, "icon": r.icon, "category": r.category,
                "url": r.url, "available": r.available,
                "status_code": r.status_code, "error": r.error, "checked_at": r.checked_at,
            }
            for r in results
        ]
        await redis.set(cache_key, json.dumps(serialisable), ex=settings.CACHE_TTL_USERNAME)

        return results

    def availability_summary(self, results: list[PlatformResult]) -> dict:
        available = sum(1 for r in results if r.available is True)
        taken     = sum(1 for r in results if r.available is False)
        unknown   = sum(1 for r in results if r.available is None)
        return {
            "total": len(results),
            "available": available,
            "taken": taken,
            "unknown": unknown,
            "availability_score": round(available / max(len(results), 1), 2),
        }


# Module-level singleton
platform_checker = PlatformChecker()
