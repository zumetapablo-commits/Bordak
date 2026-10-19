"""SIRO Inmobiliaria (Pasaia/Donostia).

La página /propiedades se pinta con JS: js/tarjetas.js consulta la tabla `properties` de
Supabase con la clave "publishable" que publica js/catalogo.js (pública por diseño; la
seguridad la ponen sus políticas RLS). Aquí se hace la misma consulta que el navegador:
URL y clave se leen de catalogo.js en cada ejecución, y se piden solo ventas publicadas
de los tipos que pueden ser rústicos. Dos peticiones por ejecución.
"""
from __future__ import annotations

import re
from typing import Iterator
from urllib.parse import quote

from ..http import PoliteClient
from ..models import Listing
from .base import Source, register

SITE = "https://www.siroinmobiliaria.com"
CATALOGO_JS = f"{SITE}/js/catalogo.js"
TIPOS_RURALES = ("caserio", "terreno", "casa", "chalet")
TIPO_LABEL = {"caserio": "Caserío", "terreno": "Terreno", "casa": "Casa", "chalet": "Chalet"}


def supabase_config(js: str) -> tuple[str, str]:
    url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', js)
    key = re.search(r'SUPABASE_KEY\s*=\s*"([^"]+)"', js)
    if not (url and key):
        raise ValueError("No se encontraron SUPABASE_URL/SUPABASE_KEY en catalogo.js")
    return url.group(1), key.group(1)


def _num(row: dict, *names: str) -> float | None:
    for n in names:
        v = row.get(n)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def parse_rows(rows: list[dict]) -> list[Listing]:
    out = []
    for r in rows:
        if r.get("estado") not in (None, "publicada") or r.get("operacion") not in (None, "venta"):
            continue
        tipo = r.get("tipo") or ""
        title = r.get("titulo") or TIPO_LABEL.get(tipo, tipo)
        # El tipo declarado ayuda al clasificador ("Caserío", "Terreno")
        if tipo in ("caserio", "terreno") and TIPO_LABEL[tipo].lower() not in title.lower():
            title = f"{TIPO_LABEL[tipo]}: {title}"
        price = None if r.get("precio_a_consultar") else _num(r, "precio")
        out.append(Listing(
            source="siro", source_id=str(r.get("referencia") or r["id"]),
            url=f"{SITE}/propiedades/{r.get('slug') or r['id']}",
            title=title, price=int(price) if price else None,
            description=r.get("descripcion") or "",
            municipality=r.get("municipio"), address=r.get("zona") or r.get("direccion"),
            lat=_num(r, "lat", "latitud", "latitude"), lon=_num(r, "lng", "lon", "longitud", "longitude"),
            surface_m2=_num(r, "m2_parcela", "m2_terreno", "m2_construidos"),
        ))
    return out


@register
class Siro(Source):
    name = "siro"
    base_url = SITE

    def fetch_list(self, client: PoliteClient) -> Iterator[Listing]:
        url, key = supabase_config(client.get(CATALOGO_JS).text)
        q = (f"{url}/rest/v1/properties?select=*&operacion=eq.venta&estado=eq.publicada"
             f"&tipo=in.({quote(','.join(TIPOS_RURALES))})")
        rows = client.get(q, headers={"apikey": key, "Accept": "application/json"}).json()
        yield from parse_rows(rows)
