"""Localiza un anuncio: coordenadas propias → Nominatim (dirección) → centroide del municipio."""
from __future__ import annotations

import logging
from urllib.parse import urlencode

from ..http import PoliteClient
from ..models import Listing
from ..store import Store
from .municipalities import Municipalities

log = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Gipuzkoa con margen (lon_min, lat_min, lon_max, lat_max)
BBOX = (-2.62, 42.88, -1.70, 43.45)


def in_bbox(lat: float, lon: float) -> bool:
    return BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


class Geocoder:
    def __init__(self, client: PoliteClient | None, store: Store, munis: Municipalities):
        self.client = client
        self.store = store
        self.munis = munis

    def nominatim(self, query: str) -> tuple[float, float] | None:
        cached = self.store.geocode_get(query)
        if cached is not False:
            return cached
        if self.client is None:
            return None
        params = {
            "q": query, "format": "jsonv2", "limit": 1, "countrycodes": "es",
            "viewbox": ",".join(map(str, BBOX)), "bounded": 1,
        }
        try:
            data = self.client.get(f"{NOMINATIM}?{urlencode(params)}", check_robots=False).json()
        except Exception as e:  # noqa: BLE001 - la geocodificación no debe tumbar la ejecución
            log.warning("Nominatim falló para %r: %s", query, e)
            return None
        coords = (float(data[0]["lat"]), float(data[0]["lon"])) if data else None
        self.store.geocode_put(query, coords, data[0] if data else None)
        return coords

    def locate(self, l: Listing) -> bool:
        """Rellena lat/lon, geo_approx y geo_method. Devuelve False si no se pudo localizar."""
        if l.lat is not None and l.lon is not None and in_bbox(l.lat, l.lon):
            l.geo_method, l.geo_approx = "listing", False
            return True
        muni = self.munis.find(l.municipality)
        if l.address:
            q = ", ".join(p for p in (l.address, muni.name_es if muni else l.municipality, "Gipuzkoa") if p)
            coords = self.nominatim(q)
            # Solo se acepta si cae cerca del municipio declarado (evita homónimos)
            if coords and (muni is None or self.munis.nearest(*coords) is muni or _close(coords, muni)):
                l.lat, l.lon = coords
                l.geo_method, l.geo_approx = "geocode", False
                return True
        if muni:
            l.lat, l.lon = muni.lat, muni.lon
            l.municipality = muni.name_es
            l.geo_method, l.geo_approx = "municipality", True
            return True
        if l.municipality:
            coords = self.nominatim(f"{l.municipality}, Gipuzkoa")
            if coords:
                l.lat, l.lon = coords
                l.geo_method, l.geo_approx = "municipality", True
                return True
        return False


def _close(coords: tuple[float, float], muni, km: float = 8) -> bool:
    from .coast import haversine_km
    return haversine_km(coords[0], coords[1], muni.lat, muni.lon) <= km
