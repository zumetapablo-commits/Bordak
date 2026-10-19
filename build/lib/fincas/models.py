from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Listing:
    source: str
    source_id: str
    url: str
    title: str
    price: int | None = None
    description: str = ""
    municipality: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    surface_m2: float | None = None

    # Calculados
    kind: str | None = None
    geo_approx: bool = False
    geo_method: str | None = None  # listing | geocode | municipality
    coast_km: float | None = None
    zarautz_km: float | None = None
    surf_km: float | None = None
    surf_spot: str | None = None
    tolosa_min: float | None = None
    score: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str]:
        return (self.source, self.source_id)
