"""Cliente HTTP "educado": respeta robots.txt y espacia las peticiones por host."""
from __future__ import annotations

import logging
import time
from typing import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    pass


class PoliteClient:
    def __init__(
        self,
        user_agent: str,
        min_interval_s: float = 1.0,
        timeout_s: float = 30,
        retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.user_agent = user_agent
        self.min_interval_s = min_interval_s
        self.retries = retries
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self.request_log: list[tuple[str, float]] = []  # (host, instante) para verificar el ritmo
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Language": "es-ES,es;q=0.9,eu;q=0.8"},
            timeout=timeout_s,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- ritmo -----------------------------------------------------------
    def _throttle(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            wait = self.min_interval_s - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        now = self._clock()
        self._last[host] = now
        self.request_log.append((host, now))

    def _raw_get(self, url: str, **kw) -> httpx.Response:
        host = urlsplit(url).netloc
        for attempt in range(self.retries + 1):
            self._throttle(host)
            try:
                resp = self._client.get(url, **kw)
            except httpx.TransportError as e:
                if attempt == self.retries:
                    raise
                log.warning("Error de red en %s (%s), reintento %d", url, e, attempt + 1)
                self._sleep(2 ** attempt)
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                retry_after = resp.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1)
                log.warning("%s -> %d, esperando %.0fs", url, resp.status_code, delay)
                self._sleep(delay)
                continue
            return resp
        raise RuntimeError("unreachable")

    # --- robots.txt ------------------------------------------------------
    def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(base)
        if rp is None:
            rp = RobotFileParser(base + "/robots.txt")
            try:
                resp = self._raw_get(base + "/robots.txt")
                if resp.status_code >= 500:
                    rp.disallow_all = True  # RFC 9309: servidor caído => no rastrear
                elif resp.status_code >= 400:
                    rp.allow_all = True  # no hay robots.txt
                else:
                    rp.parse(resp.text.splitlines())
            except httpx.TransportError:
                rp.disallow_all = True
            self._robots[base] = rp
        return rp

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(self.user_agent, url)

    def get(self, url: str, check_robots: bool = True, **kw) -> httpx.Response:
        # check_robots=False solo para APIs con política de uso propia (Nominatim),
        # nunca para las webs que se rastrean.
        if check_robots and not self.allowed(url):
            raise RobotsDisallowed(url)
        resp = self._raw_get(url, **kw)
        resp.raise_for_status()
        return resp
