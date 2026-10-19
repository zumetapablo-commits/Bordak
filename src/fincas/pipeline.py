"""Una pasada: recorre fuentes, filtra, puntúa, guarda y devuelve los anuncios a notificar."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .classify import classify
from .geo.geocode import Geocoder
from .http import PoliteClient
from .models import Listing
from .scoring import Enricher
from .sources.base import Source
from .store import Store

log = logging.getLogger(__name__)

FAILURE_ALERT_AFTER = 3


@dataclass
class RunResult:
    new_hits: list[Listing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    seen: int = 0


def process_listing(l: Listing, src: Source, client: PoliteClient, store: Store,
                    geocoder: Geocoder, enricher: Enricher, cfg: dict, seed: bool) -> Listing | None:
    """Devuelve el anuncio si es un acierto nuevo que hay que notificar."""
    max_price = cfg["filters"]["max_price_eur"]
    known = store.get(l.source, l.source_id)
    if known is not None and known["price"] == l.price:
        store.touch(l.source, l.source_id)
        return None
    if l.price is not None and l.price > max_price:
        store.upsert(l, matches=False)  # se guarda para no volver a pedir su ficha
        return None

    src.fetch_detail(client, l)
    l.kind = classify(l.title, l.description)
    matches = False
    if l.kind and geocoder.locate(l):
        enricher.measure(l)
        enricher.score(l)
        matches = enricher.passes(l)
    elif l.kind:
        log.info("Sin ubicación: %s %s", l.source, l.url)

    already_notified = bool(known and known["notified"])
    is_hit = matches and not already_notified
    store.upsert(l, matches=matches, notified=seed and matches)
    return l if is_hit and not seed else None


def run(sources: list[Source], client: PoliteClient, store: Store, geocoder: Geocoder,
        enricher: Enricher, cfg: dict, seed: bool = False) -> RunResult:
    res = RunResult()
    for src in sources:
        n = 0
        try:
            for l in src.fetch_list(client):
                n += 1
                hit = process_listing(l, src, client, store, geocoder, enricher, cfg, seed)
                if hit:
                    res.new_hits.append(hit)
            store.log_source_run(src.name, True, n)
            if n == 0:
                res.warnings.append(f"{src.name}: 0 anuncios en el listado (¿ha cambiado la web?)")
        except Exception as e:  # noqa: BLE001 - una fuente rota no debe parar las demás
            log.exception("Fuente %s falló", src.name)
            store.log_source_run(src.name, False, n, repr(e))
            if store.consecutive_failures(src.name) == FAILURE_ALERT_AFTER:
                res.warnings.append(f"{src.name}: {FAILURE_ALERT_AFTER} fallos seguidos ({e!r})")
        store.commit()
        res.seen += n
        log.info("%s: %d anuncios en listado", src.name, n)
    return res
