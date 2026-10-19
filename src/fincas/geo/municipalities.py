"""Municipios de Gipuzkoa: centroide y minutos en coche hasta Tolosa (data/municipios.csv)."""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..config import DATA_DIR
from .coast import haversine_km


@dataclass
class Municipality:
    name_es: str
    name_eu: str
    lat: float
    lon: float
    tolosa_min: float | None


def norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


class Municipalities:
    def __init__(self, csv_path: str | Path = DATA_DIR / "municipios.csv"):
        self.items: list[Municipality] = []
        self._index: dict[str, Municipality] = {}
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                m = Municipality(
                    name_es=row["name_es"],
                    name_eu=row["name_eu"],
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    tolosa_min=float(row["tolosa_min"]) if row.get("tolosa_min") else None,
                )
                self.items.append(m)
                names = [row["name_es"], row["name_eu"], row.get("osm_name") or ""]
                for n in {*names, *(p for x in names for p in x.split("/"))}:
                    if n.strip():
                        self._index[norm_name(n)] = m

    def find(self, name: str | None) -> Municipality | None:
        if not name:
            return None
        key = norm_name(name)
        if key in self._index:
            return self._index[key]
        # "Zarautz, Gipuzkoa", "Barrio X - Azpeitia"... busca el nombre más largo contenido
        hits = [k for k in self._index if re.search(rf"\b{re.escape(k)}\b", key)]
        return self._index[max(hits, key=len)] if hits else None

    def nearest(self, lat: float, lon: float) -> Municipality:
        return min(self.items, key=lambda m: haversine_km(lat, lon, m.lat, m.lon))


@lru_cache(maxsize=1)
def default_municipalities() -> Municipalities:
    return Municipalities()
