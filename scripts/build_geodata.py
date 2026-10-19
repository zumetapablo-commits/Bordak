"""Genera data/coastline_gipuzkoa.geojson y data/municipios.csv a partir de OSM.

Uso (una sola vez, o cuando quieras refrescar):  python scripts/build_geodata.py
Necesita acceso a overpass-api.de y router.project-osrm.org.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import yaml
from shapely.geometry import LineString, MultiPolygon, Polygon, mapping
from shapely.ops import linemerge, polygonize, unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fincas.http import PoliteClient  # noqa: E402

OVERPASS = "https://overpass-api.de/api/interpreter"
OSRM = "https://router.project-osrm.org/table/v1/driving/"
# Costa: Gipuzkoa ampliada (incluye Ondarroa y Hendaia para no falsear los extremos)
COAST_BBOX = "43.15,-2.60,43.50,-1.65"  # S,W,N,E

UA = "fincas-gipuzkoa-bot/0.1 (generación única de datos geográficos)"


def overpass(client: PoliteClient, query: str) -> dict:
    client._throttle("overpass-api.de")
    return client._client.post(OVERPASS, data={"data": query}, timeout=180).raise_for_status().json()


def build_coastline(client: PoliteClient) -> None:
    data = overpass(client, f'[out:json][timeout:120];way["natural"="coastline"]({COAST_BBOX});out geom;')
    lines = [LineString([(p["lon"], p["lat"]) for p in w["geometry"]])
             for w in data["elements"] if w["type"] == "way"]
    merged = linemerge(lines)
    out = {"type": "FeatureCollection",
           "features": [{"type": "Feature", "properties": {"source": "OSM natural=coastline"},
                         "geometry": mapping(merged)}]}
    (ROOT / "data/coastline_gipuzkoa.geojson").write_text(json.dumps(out))
    print(f"costa: {len(lines)} vías")


def _relation_polygon(rel: dict):
    lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
             for m in rel["members"] if m["type"] == "way" and m.get("role") in ("outer", "") and m.get("geometry")]
    polys = list(polygonize(unary_union(lines)))
    return unary_union(polys) if polys else None


def build_municipalities(client: PoliteClient) -> None:
    q = """[out:json][timeout:180];
    area["name"="Gipuzkoa"]["admin_level"="6"]->.g;
    relation(area.g)["boundary"="administrative"]["admin_level"="8"];
    out geom;"""
    data = overpass(client, q)
    ref = yaml.safe_load((ROOT / "data/surf_spots.yaml").read_text())["reference"]["tolosa"]
    rows = []
    for rel in data["elements"]:
        t = rel.get("tags", {})
        poly = _relation_polygon(rel)
        if poly is None or not isinstance(poly, (Polygon, MultiPolygon)):
            print("sin polígono:", t.get("name"))
            continue
        pt = poly.representative_point()  # siempre dentro del municipio (el centroide podría no)
        name_es = t.get("name:es") or t.get("name")
        name_eu = t.get("name:eu") or t.get("name")
        rows.append({"ine": t.get("ine:municipio", ""), "name_es": name_es, "name_eu": name_eu,
                     "osm_name": t.get("name", ""), "lat": round(pt.y, 5), "lon": round(pt.x, 5)})

    # Tiempos en coche desde Tolosa con una sola petición de tabla OSRM
    coords = ";".join([f"{ref['lon']},{ref['lat']}"] + [f"{r['lon']},{r['lat']}" for r in rows])
    resp = client.get(f"{OSRM}{coords}?sources=0&annotations=duration", check_robots=False).json()
    for r, secs in zip(rows, resp["durations"][0][1:]):
        r["tolosa_min"] = round(secs / 60) if secs is not None else ""

    rows.sort(key=lambda r: r["name_es"])
    with open(ROOT / "data/municipios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ine", "name_es", "name_eu", "osm_name", "lat", "lon", "tolosa_min"])
        w.writeheader()
        w.writerows(rows)
    print(f"municipios: {len(rows)}")


if __name__ == "__main__":
    with PoliteClient(UA, min_interval_s=2.0, timeout_s=180) as c:
        build_coastline(c)
        build_municipalities(c)
