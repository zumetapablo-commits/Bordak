"""Métricas geográficas, filtros y puntuación (0–100)."""
from __future__ import annotations

from pathlib import Path

import yaml

from .config import DATA_DIR
from .geo.coast import Coastline, distance_km, haversine_km
from .geo.municipalities import Municipalities
from .models import Listing

# Si no hay matriz OSRM: distancia en línea recta × sinuosidad a velocidad media de carretera.
_DETOUR, _KMH = 1.35, 55


class Enricher:
    def __init__(self, cfg: dict, coast: Coastline, munis: Municipalities,
                 spots_path: str | Path = DATA_DIR / "surf_spots.yaml"):
        self.cfg = cfg
        self.coast = coast
        self.munis = munis
        with open(spots_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.zarautz = data["reference"]["zarautz"]
        self.tolosa = data["reference"]["tolosa"]
        self.spots = data["spots"]

    def measure(self, l: Listing) -> None:
        lat, lon = l.lat, l.lon
        l.coast_km = round(self.coast.distance_km(lat, lon), 2)
        l.zarautz_km = round(distance_km(lat, lon, self.zarautz["lat"], self.zarautz["lon"]), 2)
        spot = min(self.spots, key=lambda s: distance_km(lat, lon, s["lat"], s["lon"]))
        l.surf_spot = spot["name"]
        l.surf_km = round(distance_km(lat, lon, spot["lat"], spot["lon"]), 2)
        muni = self.munis.find(l.municipality) if l.municipality else None
        if muni is None:
            muni = self.munis.nearest(lat, lon)
            l.municipality = l.municipality or muni.name_es
        if muni.tolosa_min is not None:
            l.tolosa_min = muni.tolosa_min
        else:
            km = haversine_km(lat, lon, self.tolosa["lat"], self.tolosa["lon"]) * _DETOUR
            l.tolosa_min = round(km / _KMH * 60)

    def passes(self, l: Listing) -> bool:
        f = self.cfg["filters"]
        return (
            l.kind in self.cfg["types"]
            and (l.price <= f["max_price_eur"] if l.price is not None
                 else f.get("include_price_on_request", False))
            and l.coast_km is not None and l.coast_km <= f["max_coast_km"]
        )

    def score(self, l: Listing) -> float:
        s = self.cfg["scoring"]
        w = s["weights"]

        def closeness(value, max_value):
            return max(0.0, 1 - value / max_value) if value is not None else 0.0

        total = (
            w["zarautz"] * closeness(l.zarautz_km, s["zarautz_max_km"])
            + w["surf"] * closeness(l.surf_km, s["surf_max_km"])
            + w["tolosa"] * closeness(l.tolosa_min, s["tolosa_max_min"])
            + w["price"] * closeness(l.price, self.cfg["filters"]["max_price_eur"])
        ) * 100
        if l.geo_approx:
            total -= s.get("approx_penalty", 0)
        l.score = round(max(0.0, total), 1)
        return l.score
