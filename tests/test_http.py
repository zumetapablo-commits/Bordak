import httpx
import pytest

from fincas.http import PoliteClient, RobotsDisallowed


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def make(handler, clock):
    return PoliteClient("testbot", 1.0, transport=httpx.MockTransport(handler),
                        clock=clock.now, sleep=clock.sleep)


def handler(req):
    if req.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nDisallow: /privado/\n")
    return httpx.Response(200, text="ok")


def test_respects_robots():
    with make(handler, FakeClock()) as c:
        assert c.get("https://a.test/fincas").text == "ok"
        with pytest.raises(RobotsDisallowed):
            c.get("https://a.test/privado/x")


def test_missing_robots_allows_all():
    def h(req):
        return httpx.Response(404) if req.url.path == "/robots.txt" else httpx.Response(200, text="ok")
    with make(h, FakeClock()) as c:
        assert c.get("https://b.test/privado/x").text == "ok"


def test_rate_limit_per_host():
    clock = FakeClock()
    with make(handler, clock) as c:
        for i in range(3):
            c.get(f"https://a.test/p{i}")
            c.get(f"https://b.test/p{i}")
        for host in ("a.test", "b.test"):
            times = [t for h, t in c.request_log if h == host]
            assert len(times) == 4  # robots + 3
            assert all(b - a >= 1.0 for a, b in zip(times, times[1:]))
