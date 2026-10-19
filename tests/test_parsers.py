from pathlib import Path

from fincas.models import Listing
from fincas.sources import cocampo

FX = Path(__file__).parent / "fixtures"


def read(*p):
    return (FX.joinpath(*p)).read_text(encoding="utf-8")


def test_cocampo_list():
    items, total = cocampo.parse_list(read("cocampo", "list_fincas_rusticas.html"))
    assert total == 21 and len(items) == 21
    by_id = {l.source_id: l for l in items}
    l = by_id["8307ccbd-313a-422e-a1ff-3c6dd4bca975"]
    assert l.price == 45000
    assert l.municipality == "Aretxabaleta"
    assert l.url == "https://www.cocampo.com/es/es/propiedades/8307ccbd-313a-422e-a1ff-3c6dd4bca975/"
    assert abs(l.surface_m2 - 1050) < 1
    # precio "a consultar" (1 €) → None
    assert by_id["6d925241-f7bd-51a7-b4d2-2322c5e2030d"].price is None
    assert by_id["6d925241-f7bd-51a7-b4d2-2322c5e2030d"].municipality == "Ezquioga-Ichaso"


def test_cocampo_detail():
    l = Listing("cocampo", "x", "u", "Finca rústica de 0,105 ha en venta en Aretxabaleta, Guipúzcoa")
    cocampo.parse_detail(read("cocampo", "detail_aretxabaleta.html"), l)
    assert (l.lat, l.lon) == (43.024219, -2.513563)
    assert "txabola" in l.description
    assert l.price == 45000


def test_moldatu_list():
    from fincas.sources import moldatu

    items, shown, total = moldatu.parse_list(read("moldatu", "list_fincas_rusticas.html"))
    assert (shown, total) == (3, 3)
    lezo = items[0]
    assert lezo.source_id == "1772555"
    assert lezo.price == 60000 and lezo.municipality == "Lezo"
    assert lezo.title == "Finca rústica en Lezo"
    assert lezo.url.startswith("https://www.inmuebles.moldatuhome.com/")

    items, shown, total = moldatu.parse_list(read("moldatu", "list_casas_chalets.html"))
    assert (len(items), shown, total) == (12, 12, 30)
    zeanuri = next(l for l in items if l.municipality == "Zeanuri")
    assert "CASERÍO" in zeanuri.description


def test_moldatu_municipality_links_stay_robots_safe():
    from fincas.sources import moldatu

    links = moldatu.municipality_links(read("moldatu", "home.html"), "casas-chalets", 3)
    assert any(l.endswith("casas-chalets-en-venta-en-segura-3-1-014918.html") for l in links)
    assert all("?" not in l for l in links)
