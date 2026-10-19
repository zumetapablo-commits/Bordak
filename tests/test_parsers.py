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
