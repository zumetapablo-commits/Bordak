from __future__ import annotations

import argparse
import importlib
import logging
import pkgutil
import sqlite3
import sys

from . import notify, sources as sources_pkg
from .config import ROOT, load_config
from .geo.coast import default_coastline
from .geo.geocode import Geocoder
from .geo.municipalities import default_municipalities
from .http import PoliteClient
from .models import Listing
from .pipeline import run
from .scoring import Enricher
from .sources.base import SOURCES
from .store import Store

log = logging.getLogger("fincas")


def load_sources(cfg: dict, only: list[str] | None):
    for m in pkgutil.iter_modules(sources_pkg.__path__):
        if m.name != "base":
            importlib.import_module(f"{sources_pkg.__name__}.{m.name}")
    names = only or [n for n, c in cfg["sources"].items() if c.get("enabled")]
    missing = [n for n in names if n not in SOURCES]
    if missing:
        log.warning("Fuentes sin implementar todavía: %s", ", ".join(missing))
    return [SOURCES[n](**cfg["sources"].get(n, {}).get("options", {})) for n in names if n in SOURCES]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fincas")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="Busca anuncios nuevos y avisa por correo")
    r.add_argument("--dry-run", action="store_true", help="No guarda en la BD ni envía correo")
    r.add_argument("--seed", action="store_true", help="Marca todo lo actual como visto, sin correo")
    r.add_argument("--source", action="append", help="Ejecuta solo esta fuente (repetible)")
    r.add_argument("--config", default=None)
    r.add_argument("--email-preview", metavar="FICHERO", help="Con --dry-run: guarda el correo en HTML")
    sub.add_parser("test-email", help="Envía un correo de prueba")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.cmd == "test-email":
        demo = Listing("demo", "1", "https://example.org", "Borda de prueba con terreno", 120000,
                       municipality="Aizarnazabal", kind="borda", geo_approx=True, coast_km=4.2,
                       zarautz_km=6.1, surf_km=5.0, surf_spot="Zumaia (Itzurun)", tolosa_min=35, score=71)
        notify.send(*notify.render([demo], ["Esto es un correo de prueba"]))
        return 0

    cfg = load_config(args.config)
    db_path = ROOT / cfg["db_path"]
    seed = args.seed
    if not db_path.exists() and not args.dry_run:
        log.info("Primera ejecución: se marcan como vistos los anuncios actuales sin enviar correo")
        seed = True
    store = Store(db_path)
    if args.dry_run:  # trabaja sobre una copia en memoria
        mem = sqlite3.connect(":memory:")
        store.db.backup(mem)
        store.db.close()
        mem.row_factory = sqlite3.Row
        store.db = mem

    h = cfg["http"]
    with PoliteClient(h["user_agent"], h["min_interval_s"], h["timeout_s"], h["retries"]) as client:
        munis = default_municipalities()
        enricher = Enricher(cfg, default_coastline(), munis)
        geocoder = Geocoder(client, store, munis)
        res = run(load_sources(cfg, args.source), client, store, geocoder, enricher, cfg, seed=seed)

    log.info("Vistos %d anuncios, %d nuevos que cumplen filtros", res.seen, len(res.new_hits))
    if args.dry_run:
        subject, text, body = notify.render(res.new_hits, res.warnings)
        print(subject, "\n", text, sep="")
        if args.email_preview:
            with open(args.email_preview, "w", encoding="utf-8") as f:
                f.write(f"<!doctype html><html><head><meta charset='utf-8'><title>{subject}</title>"
                        f"<meta name='viewport' content='width=device-width'></head>"
                        f"<body style='margin:0'>{body}</body></html>")
        return 0
    pending = store.pending_notifications()  # nuevos + los de envíos fallidos anteriores
    try:
        if pending or res.warnings:
            notify.send(*notify.render(pending, res.warnings))
            store.mark_notified(pending)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
