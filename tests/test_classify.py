import pytest

from fincas.classify import classify


@pytest.mark.parametrize("title,desc,kind", [
    ("Caserío a reformar en Aia", "", "caserio"),
    ("Baserria salgai", "", "caserio"),
    ("Borda con terreno", "", "borda"),
    ("Terreno rústico de 5.000 m2", "", "terreno_rustico"),
    ("Venta de huerta en Orio", "", "huerta"),
    ("Finca rústica con txabola", "", "finca_rustica"),
    ("Parcela", "Suelo no urbanizable con caseta de aperos", "caseta"),
    ("Piso en finca rehabilitada", "", None),
    ("Finca de 2 ha con borda", "", "finca_rustica"),
    ("Piso en Zarautz", "con vistas al monte", None),
    ("Parcela", "terreno urbano edificable", None),
])
def test_classify(title, desc, kind):
    assert classify(title, desc) == kind
