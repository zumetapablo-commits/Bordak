"""Genera data/coastline_gipuzkoa.geojson y data/municipios.csv a partir de OSM.

Usa el extracto del País Vasco de Geofabrik (un único fichero .osm.pbf), así no depende
de los servidores públicos de Overpass, que rechazan con frecuencia las IPs de GitHub.
Los minutos hasta Tolosa salen de una tabla OSRM; si OSRM no responde, la columna queda
vacía y el programa usa una estimación por distancia.

Uso (una sola vez, o cuando quieras refrescar):  python scripts/build_geodata.py [fichero.pbf]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import osmium
import shapely.wkb
import yaml
from shapely.geometry import LineString, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fincas.http import PoliteClient  # noqa: E402

PBF_URL = "https://download.geofabrik.de/europe/spain/pais-vasco-latest.osm.pbf"
OSRM = "https://router.project-osrm.org/table/v1/driving/"
UA = "fincas-gipuzkoa-bot/0.1 (generacion unica de datos geograficos)"
# Costa a considerar: Gipuzkoa con margen (incluye Ondarroa/Bizkaia oriental)
COAST_BBOX = (-2.60, 43.15, -1.65, 43.50)  # lon_min, lat_min, lon_max, lat_max


class Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.wkb = osmium.geom.WKBFactory()
        self.coast: list[LineString] = []
        self.gipuzkoa = None
        self.munis: list[dict] = []

    def way(self, w):
        if w.tags.get("natural") != "coastline":
            return
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(coords) >= 2:
            self.coast.append(LineString(coords))

    def area(self, a):
        if a.from_way() or a.tags.get("boundary") != "administrative":
            return
        level = a.tags.get("admin_level")
        if level not in ("6", "8"):
            return
        try:
            geom = shapely.wkb.loads(self.wkb.create_multipolygon(a), hex=True)
        except Exception:  # noqa: BLE001 - polígono roto en OSM
            print("geometría inválida:", a.tags.get("name"))
            return
        tags = {t.k: t.v for t in a.tags}
        if level == "6":
            if tags.get("name") in ("Gipuzkoa", "Guipúzcoa") or tags.get("name:es") == "Guipúzcoa":
                self.gipuzkoa = geom
        else:
            self.munis.append({"tags": tags, "geom": geom})


def download_pbf(dest: Path) -> None:
    import httpx

    print("Descargando", PBF_URL, flush=True)
    with httpx.stream("GET", PBF_URL, headers={"User-Agent": UA}, timeout=600, follow_redirects=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)


def build(pbf: Path) -> None:
    h = Handler()
    h.apply_file(str(pbf), locations=True)
    print(f"costa: {len(h.coast)} vías; municipios (todo el extracto): {len(h.munis)}", flush=True)

    # --- costa ---
    from shapely.geometry import box

    clip = box(*COAST_BBOX)
    coast = unary_union(h.coast).intersection(clip)
    out = {"type": "FeatureCollection",
           "features": [{"type": "Feature", "properties": {"source": "OSM natural=coastline (Geofabrik)"},
                         "geometry": mapping(coast.simplify(0.00005))}]}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data/coastline_gipuzkoa.geojson").write_text(json.dumps(out))

    # --- municipios de Gipuzkoa ---
    if h.gipuzkoa is None:
        raise RuntimeError("No se encontró el límite de Gipuzkoa (admin_level=6)")
    rows = []
    for m in h.munis:
        pt = m["geom"].representative_point()  # siempre dentro del municipio
        if not h.gipuzkoa.contains(pt):
            continue
        t = m["tags"]
        rows.append({
            "ine": t.get("ine:municipio", ""),
            "name_es": t.get("name:es") or t.get("name"),
            "name_eu": t.get("name:eu") or t.get("name"),
            "osm_name": t.get("name", ""),
            "lat": round(pt.y, 5), "lon": round(pt.x, 5), "tolosa_min": "",
        })
    print(f"municipios de Gipuzkoa: {len(rows)}", flush=True)

    # --- minutos en coche hasta Tolosa (OSRM, opcional) ---
    ref = yaml.safe_load((ROOT / "data/surf_spots.yaml").read_text())["reference"]["tolosa"]
    coords = ";".join([f"{ref['lon']},{ref['lat']}"] + [f"{r['lon']},{r['lat']}" for r in rows])
    try:
        with PoliteClient(UA, min_interval_s=2.0, timeout_s=120) as c:
            resp = c.get(f"{OSRM}{coords}?sources=0&annotations=duration", check_robots=False).json()
        for r, secs in zip(rows, resp["durations"][0][1:]):
            r["tolosa_min"] = round(secs / 60) if secs is not None else ""
        print("tiempos OSRM: ok", flush=True)
    except Exception as e:  # noqa: BLE001
        print("OSRM no disponible, se usará la estimación por distancia:", repr(e)[:200], flush=True)

    rows.sort(key=lambda r: r["name_es"])
    with open(ROOT / "data/municipios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ine", "name_es", "name_eu", "osm_name", "lat", "lon", "tolosa_min"])
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pbf = Path(sys.argv[1])
    else:
        pbf = Path("/tmp/pais-vasco.osm.pbf")
        if not pbf.exists():
            download_pbf(pbf)
    build(pbf)
