"""Moldatu Home: la web pública muestra en un iframe el portal Inmoweb inmuebles.moldatuhome.com.

Listado por tipo: /<tipo>-en-venta-<id>-1.html, en HTML servidor. Cada anuncio es un
<div data-url=… id=<ref> title=<municipio>> con h4 "Tipo en Municipio", descripción
corta, precio (.precio .actual) y, a veces, data-lat/data-lng.

robots.txt prohíbe las URLs con ?i= / ?c=, que son justo las de paginación. Por eso:
  1. se lee la primera página de cada tipo (ordenada por precio ascendente);
  2. si hay más resultados, se leen las páginas por municipio de ese tipo
     (/<tipo>-en-venta-en-<municipio>-<id>-1-<cod>.html, sin parámetros) enlazadas
     desde la portada, solo para municipios de Gipuzkoa.
"""
from __future__ import annotations

import logging
import re
from typing import Iterator
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser

from ..geo.municipalities import default_municipalities
from ..http import PoliteClient
from ..models import Listing
from .base import Source, parse_price, register

log = logging.getLogger(__name__)

BASE = "https://www.inmuebles.moldatuhome.com"
# id de tipo Inmoweb → prefijo de URL. Solo los que pueden ser rústicos.
TYPES = {9: "fincas-rusticas", 5: "parcelas", 3: "casas-chalets", 20: "casas-de-pueblo"}
TOTAL_RE = re.compile(r"Mostrando\s+\d+\s+a\s+(\d+)\s+de\s+(\d+)")


def parse_list(html: str) -> tuple[list[Listing], int, int]:
    tree = LexborHTMLParser(html)
    out = []
    for card in tree.css("div[data-url][id]"):
        ref = card.attributes.get("id")
        if not ref or not ref.isdigit():
            continue
        h4 = card.css_first("h4.subTitulo")
        price = card.css_first(".precio .actual")
        desc = card.css_first("p.descripcion")
        lat, lng = card.attributes.get("data-lat"), card.attributes.get("data-lng")
        out.append(Listing(
            source="moldatu", source_id=ref,
            url=urljoin(BASE, card.attributes["data-url"]),
            title=h4.text(strip=True) if h4 else "",
            price=parse_price(price.text(strip=True)) if price else None,
            description=desc.text(strip=True) if desc else "",
            municipality=card.attributes.get("title"),
            lat=float(lat) if lat else None, lon=float(lng) if lng else None,
        ))
    m = TOTAL_RE.search(tree.body.text() if tree.body else "")
    shown, total = (int(m.group(1)), int(m.group(2))) if m else (len(out), len(out))
    return out, shown, total


def municipality_links(home_html: str, prefix: str, type_id: int) -> list[str]:
    pat = re.compile(rf"^/{prefix}-en-venta-en-[a-z0-9-]+-{type_id}-1-\d+\.html$")
    hrefs = {a.attributes.get("href") for a in LexborHTMLParser(home_html).css("a[href]")}
    return sorted(urljoin(BASE, h) for h in hrefs if h and pat.match(h))


def parse_detail(html: str, listing: Listing) -> None:
    tree = LexborHTMLParser(html)
    for sel in ("#descripcion", ".descripcion", 'meta[name="description"]'):
        node = tree.css_first(sel)
        if node is None:
            continue
        text = node.attributes.get("content") if node.tag == "meta" else node.text(separator=" ", strip=True)
        if text and len(text) > len(listing.description):
            listing.description = text
            break
    if listing.lat is None:
        mapa = tree.css_first("#mapa[data-lat][data-lng]")  # mapa de la propia ficha
        if mapa:
            listing.lat = float(mapa.attributes["data-lat"])
            listing.lon = float(mapa.attributes["data-lng"])


@register
class Moldatu(Source):
    name = "moldatu"
    base_url = BASE

    def fetch_list(self, client: PoliteClient) -> Iterator[Listing]:
        seen: set[str] = set()
        home = None
        munis = default_municipalities()
        for type_id, prefix in TYPES.items():
            items, shown, total = parse_list(client.get(f"{BASE}/{prefix}-en-venta-{type_id}-1.html").text)
            pages = [items]
            if total > shown:
                home = home or client.get(f"{BASE}/").text
                links = [u for u in municipality_links(home, prefix, type_id)
                         if munis.find(_muni_from_url(u, prefix, type_id))]
                log.info("Moldatu %s: %d de %d en la 1.ª página; leyendo %d páginas de municipios de Gipuzkoa",
                         prefix, shown, total, len(links))
                for u in links:
                    pages.append(parse_list(client.get(u).text)[0])
            for page in pages:
                for l in page:
                    if l.source_id not in seen:
                        seen.add(l.source_id)
                        yield l

    def fetch_detail(self, client: PoliteClient, listing: Listing) -> None:
        parse_detail(client.get(listing.url).text, listing)


def _muni_from_url(url: str, prefix: str, type_id: int) -> str:
    m = re.search(rf"/{prefix}-en-venta-en-([a-z0-9-]+)-{type_id}-1-\d+\.html$", url)
    return m.group(1).replace("-", " ") if m else ""
