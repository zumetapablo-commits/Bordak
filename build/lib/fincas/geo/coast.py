"""Distancias en metros sobre ETRS89 / UTM 30N (EPSG:25830), adecuado para Gipuzkoa."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Point, shape
import shapely
from shapely.ops import unary_union

from ..config import DATA_DIR

_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True).transform


def _to_utm_array(xy):
    import numpy as np
    x, y = _to_utm(xy[:, 0], xy[:, 1])
    return np.column_stack([x, y])


def to_utm(lat: float, lon: float) -> Point:
    x, y = _to_utm(lon, lat)
    return Point(x, y)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return to_utm(lat1, lon1).distance(to_utm(lat2, lon2)) / 1000


class Coastline:
    def __init__(self, geojson_path: str | Path = DATA_DIR / "coastline_gipuzkoa.geojson"):
        with open(geojson_path, encoding="utf-8") as f:
            gj = json.load(f)
        feats = gj["features"] if gj.get("type") == "FeatureCollection" else [gj]
        geoms = [shape(f["geometry"] if "geometry" in f else f) for f in feats]
        self.geom = shapely.transform(unary_union(geoms), lambda xy: _to_utm_array(xy))

    def distance_km(self, lat: float, lon: float) -> float:
        return to_utm(lat, lon).distance(self.geom) / 1000


@lru_cache(maxsize=1)
def default_coastline() -> Coastline:
    return Coastline()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
