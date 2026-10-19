"""Cocampo: portal de fincas rústicas.

Listado: páginas de Gipuzkoa por categoría, con los anuncios en JSON-LD (ItemList:
url, name, description, size, offers.price). Precio 1 € = "a consultar".
Ficha: /propiedades/<uuid>/ con descripción completa (JSON-LD Product) y coordenadas en
los datos embebidos de Next.js ("latitude"/"longitude").
Cocampo muestra 25 anuncios por página y carga el resto con JS ("Ver más propiedades");
si el total supera lo leído se registra un aviso.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Iterator
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser

from ..http import PoliteClient
from ..models import Listing
from .base import Source, register

log = logging.getLogger(__name__)

BASE = "https://www.cocampo.com"
LIST_URLS = [
    f"{BASE}/es/es/explorar/comprar/fincas-rusticas/espana/pais-vasco/guipuzcoa/",
    f"{BASE}/es/es/explorar/comprar/casas-rusticas/espana/pais-vasco/guipuzcoa/",
]
UUID_RE = re.compile(r"/propiedades/([0-9a-f-]{36})/")
MUNI_RE = re.compile(r"en venta en (.+?),\s*Gu[ií]p[uú]zcoa", re.I)
COORD_RE = re.compile(r'latitude\\?"\s*:\s*(-?\d+\.\d+)\s*,\s*\\?"longitude\\?"\s*:\s*(-?\d+\.\d+)')


def _json_ld(html: str) -> list[dict]:
    out = []
    for s in LexborHTMLParser(html).css('script[type="application/ld+json"]'):
        try:
            out.append(json.loads(s.text()))
        except json.JSONDecodeError:
            continue
    return out


def _price(offers: dict | None) -> int | None:
    p = (offers or {}).get("price")
    try:
        p = int(float(p))
    except (TypeError, ValueError):
        return None
    return p if p > 1 else None  # 1 € = precio a consultar


def parse_list(html: str) -> tuple[list[Listing], int | None]:
    listings = []
    for d in _json_ld(html):
        if "ItemList" not in (d.get("@type") if isinstance(d.get("@type"), list) else [d.get("@type")]):
            continue
        for it in d.get("itemListElement", []):
            url = urljoin(BASE, it.get("url", ""))
            m = UUID_RE.search(url)
            if not m:
                continue
            name = it.get("name", "")
            muni = MUNI_RE.search(name)
            size = it.get("size") or {}
            surface = None
            if size.get("value") is not None:
                factor = 10000 if str(size.get("unitCode", "")).lower() == "ha" else 1
                surface = float(size["value"]) * factor
            listings.append(Listing(
                source="cocampo", source_id=m.group(1), url=url, title=name,
                price=_price(it.get("offers")), description=it.get("description", ""),
                municipality=muni.group(1).strip() if muni else None, surface_m2=surface,
            ))
    total = re.search(r"([\d.]+) resultados", html)
    return listings, int(total.group(1).replace(".", "")) if total else None


def parse_detail(html: str, listing: Listing) -> None:
    for d in _json_ld(html):
        if d.get("@type") == "Product":
            listing.description = d.get("description") or listing.description
            price = _price(d.get("offers"))
            if price:
                listing.price = price
    m = COORD_RE.search(html)
    if m:
        listing.lat, listing.lon = float(m.group(1)), float(m.group(2))


@register
class Cocampo(Source):
    name = "cocampo"
    base_url = BASE

    def fetch_list(self, client: PoliteClient) -> Iterator[Listing]:
        seen = set()
        for url in LIST_URLS:
            items, total = parse_list(client.get(url).text)
            if total and total > len(items):
                log.warning("Cocampo %s: %d resultados pero solo %d en la página", url, total, len(items))
            for l in items:
                if l.source_id not in seen:
                    seen.add(l.source_id)
                    yield l

    def fetch_detail(self, client: PoliteClient, listing: Listing) -> None:
        parse_detail(client.get(listing.url).text, listing)
