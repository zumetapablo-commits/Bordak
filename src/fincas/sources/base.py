from __future__ import annotations

import re
from typing import Iterator

from ..http import PoliteClient
from ..models import Listing


class Source:
    """Una web de anuncios.

    `fetch_list` recorre las páginas de resultados y devuelve anuncios con los datos que
    haya en el listado (como mínimo id, url, título y, si lo hay, precio). `fetch_detail`
    completa el anuncio desde su ficha; solo se llama para anuncios nuevos o con cambio de
    precio que no superan ya el precio máximo.
    """

    name: str = ""
    base_url: str = ""
    max_pages: int = 30

    def fetch_list(self, client: PoliteClient) -> Iterator[Listing]:
        raise NotImplementedError

    def fetch_detail(self, client: PoliteClient, listing: Listing) -> None:
        return None


def parse_price(text: str | None) -> int | None:
    """'185.000 €' / '185000€' / '1.250.000,00 €' → int. 'Consultar' → None."""
    if not text:
        return None
    m = re.search(r"(\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d+)?\s*(?:€|eur)", text, re.I)
    if not m:
        m = re.search(r"(\d{1,3}(?:[.\s]\d{3})+|\d{4,})", text)
    if not m:
        return None
    return int(re.sub(r"[.\s]", "", m.group(1)))


def parse_surface(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?\s*m(?:2|²)", text)
    if not m:
        return None
    return float(m.group(1).replace(".", "") + ("." + m.group(2) if m.group(2) else ""))


SOURCES: dict[str, type[Source]] = {}


def register(cls: type[Source]) -> type[Source]:
    SOURCES[cls.name] = cls
    return cls
