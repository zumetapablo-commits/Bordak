from fincas.geo.geocode import Geocoder
from fincas.models import Listing
from fincas.pipeline import run
from fincas.sources.base import Source, parse_price


class FakeSource(Source):
    name = "fake"

    def __init__(self, items):
        self.items = items
        self.details = 0

    def fetch_list(self, client):
        for it in self.items:
            yield Listing(**it)

    def fetch_detail(self, client, l):
        self.details += 1


def item(i, price, title="Borda en Zarautz", muni="Zarautz"):
    return dict(source="fake", source_id=str(i), url=f"https://f.test/{i}", title=title,
                price=price, municipality=muni)


def go(src, store, enricher, munis, cfg, seed=False):
    return run([src], None, store, Geocoder(None, store, munis), enricher, cfg, seed=seed)


def test_only_new_hits_are_notified(store, enricher, munis, cfg):
    src = FakeSource([item(1, 100000), item(2, 400000), item(3, 90000, "Piso céntrico"),
                      item(4, 120000, muni="Abaltzisketa")])
    r = go(src, store, enricher, munis, cfg)
    assert [l.source_id for l in r.new_hits] == ["1"]
    assert src.details == 3  # el de 400.000 € no pide ficha
    store.mark_notified(r.new_hits)

    r2 = go(FakeSource([item(1, 100000), item(5, 80000, "Huerta")]), store, enricher, munis, cfg)
    assert [l.source_id for l in r2.new_hits] == ["5"]


def test_price_drop_into_range_notifies(store, enricher, munis, cfg):
    go(FakeSource([item(1, 300000)]), store, enricher, munis, cfg)
    r = go(FakeSource([item(1, 240000)]), store, enricher, munis, cfg)
    assert [l.source_id for l in r.new_hits] == ["1"]


def test_seed_marks_without_notifying(store, enricher, munis, cfg):
    r = go(FakeSource([item(1, 100000)]), store, enricher, munis, cfg, seed=True)
    assert r.new_hits == []
    r = go(FakeSource([item(1, 95000)]), store, enricher, munis, cfg)
    assert r.new_hits == []  # ya notificado (seed) aunque cambie el precio


def test_broken_source_does_not_stop_others(store, enricher, munis, cfg):
    class Broken(Source):
        name = "broken"

        def fetch_list(self, client):
            raise RuntimeError("boom")
            yield

    for _ in range(3):
        r = run([Broken(), FakeSource([])], None, store, Geocoder(None, store, munis), enricher, cfg)
    assert any("3 fallos" in w for w in r.warnings)


def test_parse_price():
    assert parse_price("185.000 €") == 185000
    assert parse_price("Precio: 1.250.000,00 €") == 1250000
    assert parse_price("95000€") == 95000
    assert parse_price("Consultar") is None


def test_failed_email_is_retried(store, enricher, munis, cfg):
    r = go(FakeSource([item(1, 100000)]), store, enricher, munis, cfg)
    assert len(r.new_hits) == 1
    # el envío falló: no se llamó a mark_notified → sigue pendiente en la siguiente pasada
    go(FakeSource([item(1, 100000)]), store, enricher, munis, cfg)
    assert [l.source_id for l in store.pending_notifications()] == ["1"]
    store.mark_notified(store.pending_notifications())
    assert store.pending_notifications() == []


def test_empty_source_warns_only_when_it_drops_to_zero(store, enricher, munis, cfg):
    assert go(FakeSource([]), store, enricher, munis, cfg).warnings == []
    go(FakeSource([item(1, 100000)]), store, enricher, munis, cfg)
    r = go(FakeSource([]), store, enricher, munis, cfg)
    assert any("antes 1" in w for w in r.warnings)
