from fincas.geo.geocode import Geocoder
from fincas.models import Listing


def test_coast_distance(coast):
    assert coast.distance_km(43.287, -2.17) < 0.5          # Zarautz, en la costa
    assert 15 < coast.distance_km(43.135, -2.078) < 20     # Tolosa, interior


def test_municipality_lookup(munis):
    assert munis.find("Donostia").name_es.startswith("Donostia")
    assert munis.find("San Sebastián").name_es.startswith("Donostia")
    assert munis.find("Barrio Urkizu, Tolosa (Gipuzkoa)").name_es == "Tolosa"
    assert munis.find("Madrid") is None


def test_locate_falls_back_to_centroid(store, munis):
    g = Geocoder(None, store, munis)
    l = Listing("x", "1", "u", "Borda", municipality="Azpeitia")
    assert g.locate(l)
    assert l.geo_approx and l.geo_method == "municipality"


def test_locate_uses_listing_coords(store, munis):
    g = Geocoder(None, store, munis)
    l = Listing("x", "1", "u", "Borda", lat=43.25, lon=-2.15)
    assert g.locate(l) and not l.geo_approx


def test_filters_and_score(enricher, munis):
    near = Listing("x", "1", "u", "Borda", price=150000, kind="borda", lat=43.27, lon=-2.17,
                   municipality="Zarautz")
    enricher.measure(near)
    enricher.score(near)
    assert enricher.passes(near) and near.surf_spot == "Zarautz"

    inland = Listing("x", "2", "u", "Borda", price=150000, kind="borda", lat=43.045, lon=-2.103,
                     municipality="Abaltzisketa")
    enricher.measure(inland)
    enricher.score(inland)
    assert not enricher.passes(inland)
    assert near.score > inland.score

    pricey = Listing("x", "3", "u", "Borda", price=300000, kind="borda", lat=43.27, lon=-2.17)
    enricher.measure(pricey)
    assert not enricher.passes(pricey)


def test_price_on_request(enricher, cfg):
    l = Listing("x", "4", "u", "Borda", price=None, kind="borda", lat=43.27, lon=-2.17)
    enricher.measure(l)
    cfg["filters"]["include_price_on_request"] = True
    assert enricher.passes(l)
    cfg["filters"]["include_price_on_request"] = False
    assert not enricher.passes(l)
