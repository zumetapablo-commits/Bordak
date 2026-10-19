from pathlib import Path

import pytest

from fincas.config import load_config
from fincas.geo.coast import Coastline
from fincas.geo.municipalities import Municipalities
from fincas.scoring import Enricher
from fincas.store import Store

TD = Path(__file__).parent / "data"


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def munis():
    return Municipalities(TD / "municipios.csv")


@pytest.fixture
def coast():
    return Coastline(TD / "coast.geojson")


@pytest.fixture
def enricher(cfg, coast, munis):
    return Enricher(cfg, coast, munis)


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()
