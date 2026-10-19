"""Persistencia en SQLite: anuncios vistos, histórico de precios, caché de geocodificación."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    kind         TEXT,
    price        INTEGER,
    municipality TEXT,
    lat REAL, lon REAL,
    geo_approx   INTEGER,
    coast_km REAL, zarautz_km REAL, surf_km REAL, surf_spot TEXT, tolosa_min REAL,
    score        REAL,
    matches      INTEGER NOT NULL DEFAULT 0,  -- pasa los filtros
    notified     INTEGER NOT NULL DEFAULT 0,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
);
CREATE TABLE IF NOT EXISTS price_history (
    source TEXT, source_id TEXT, price INTEGER, seen_at TEXT
);
CREATE TABLE IF NOT EXISTS geocode_cache (
    query TEXT PRIMARY KEY, lat REAL, lon REAL, raw TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS source_runs (
    source TEXT, run_at TEXT, ok INTEGER, n_listings INTEGER, error TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.commit()
        self.db.close()

    # --- anuncios --------------------------------------------------------
    def get(self, source: str, source_id: str) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM listings WHERE source=? AND source_id=?", (source, source_id)
        ).fetchone()

    def is_known(self, source: str, source_id: str) -> bool:
        return self.get(source, source_id) is not None

    def touch(self, source: str, source_id: str) -> None:
        self.db.execute(
            "UPDATE listings SET last_seen=? WHERE source=? AND source_id=?", (_now(), source, source_id)
        )

    def upsert(self, l: Listing, matches: bool, notified: bool = False) -> None:
        now = _now()
        prev = self.get(l.source, l.source_id)
        if prev is None or prev["price"] != l.price:
            self.db.execute(
                "INSERT INTO price_history VALUES (?,?,?,?)", (l.source, l.source_id, l.price, now)
            )
        self.db.execute(
            """INSERT INTO listings (source, source_id, url, title, kind, price, municipality, lat, lon,
                   geo_approx, coast_km, zarautz_km, surf_km, surf_spot, tolosa_min, score, matches,
                   notified, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source, source_id) DO UPDATE SET
                   url=excluded.url, title=excluded.title, kind=excluded.kind, price=excluded.price,
                   municipality=excluded.municipality, lat=excluded.lat, lon=excluded.lon,
                   geo_approx=excluded.geo_approx, coast_km=excluded.coast_km,
                   zarautz_km=excluded.zarautz_km, surf_km=excluded.surf_km,
                   surf_spot=excluded.surf_spot, tolosa_min=excluded.tolosa_min,
                   score=excluded.score, matches=excluded.matches,
                   notified=MAX(listings.notified, excluded.notified), last_seen=excluded.last_seen""",
            (l.source, l.source_id, l.url, l.title, l.kind, l.price, l.municipality, l.lat, l.lon,
             int(l.geo_approx), l.coast_km, l.zarautz_km, l.surf_km, l.surf_spot, l.tolosa_min,
             l.score, int(matches), int(notified), now, now),
        )

    def pending_notifications(self) -> list[Listing]:
        """Anuncios que cumplen los filtros y aún no se han avisado (incluye envíos fallidos)."""
        rows = self.db.execute(
            "SELECT * FROM listings WHERE matches=1 AND notified=0 ORDER BY score DESC"
        ).fetchall()
        return [
            Listing(source=r["source"], source_id=r["source_id"], url=r["url"], title=r["title"],
                    price=r["price"], municipality=r["municipality"], lat=r["lat"], lon=r["lon"],
                    kind=r["kind"], geo_approx=bool(r["geo_approx"]), coast_km=r["coast_km"],
                    zarautz_km=r["zarautz_km"], surf_km=r["surf_km"], surf_spot=r["surf_spot"],
                    tolosa_min=r["tolosa_min"], score=r["score"])
            for r in rows
        ]

    def mark_notified(self, listings: list[Listing]) -> None:
        self.db.executemany(
            "UPDATE listings SET notified=1 WHERE source=? AND source_id=?",
            [l.key for l in listings],
        )
        self.db.commit()

    def commit(self) -> None:
        self.db.commit()

    # --- geocodificación -------------------------------------------------
    def geocode_get(self, query: str) -> tuple[float, float] | None | bool:
        """Devuelve (lat, lon), None si se buscó sin resultado, o False si no está en caché."""
        row = self.db.execute("SELECT lat, lon FROM geocode_cache WHERE query=?", (query,)).fetchone()
        if row is None:
            return False
        return None if row["lat"] is None else (row["lat"], row["lon"])

    def geocode_put(self, query: str, coords: tuple[float, float] | None, raw: object = None) -> None:
        lat, lon = coords if coords else (None, None)
        self.db.execute(
            "INSERT OR REPLACE INTO geocode_cache VALUES (?,?,?,?,?)",
            (query, lat, lon, json.dumps(raw, ensure_ascii=False) if raw else None, _now()),
        )

    # --- estado de fuentes ----------------------------------------------
    def log_source_run(self, source: str, ok: bool, n: int, error: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO source_runs VALUES (?,?,?,?,?)", (source, _now(), int(ok), n, error)
        )

    def consecutive_failures(self, source: str) -> int:
        rows = self.db.execute(
            "SELECT ok FROM source_runs WHERE source=? ORDER BY rowid DESC LIMIT 20", (source,)
        ).fetchall()
        n = 0
        for r in rows:
            if r["ok"]:
                break
            n += 1
        return n
