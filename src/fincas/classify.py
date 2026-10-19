"""Clasificación del tipo de inmueble a partir de título y descripción (es/eu)."""
from __future__ import annotations

import re
import unicodedata

# Orden = prioridad: el primero que encaje en el título gana; si no, en la descripción.
KIND_PATTERNS: list[tuple[str, list[str]]] = [
    ("caserio", [r"caser[ií]o", r"baserri"]),
    # "finca" a secas también significa "edificio" (piso en finca rehabilitada): no basta
    ("finca_rustica", [r"finca r[uú]stica", r"finca agr[ií]cola", r"finca de [\d.,]+ ?(m2|m²|ha|hect)", r"landa[- ]?etxe"]),
    ("borda", [r"\bborda\b"]),
    ("caseta", [r"\bcaseta\b", r"\btxabola\b", r"\bchabola\b", r"\bpabell[oó]n agr[ií]cola\b"]),
    ("huerta", [r"\bhuerta\b", r"\bhuerto\b", r"\bortu(a|ak)?\b", r"\bbaratz"]),
    ("terreno_rustico", [
        r"terreno r[uú]stico", r"suelo r[uú]stico", r"no urbanizable", r"\bterreno\b",
        r"\bparcela r[uú]stica\b", r"\blursail", r"\bpradera\b", r"\bprado\b", r"\bmonte\b",
    ]),
]

# Si aparece alguno de estos sin un tipo rural claro en el título, se descarta.
URBAN_EXCLUDE = [
    r"\bpiso\b", r"\bapartamento\b", r"\b[aá]tico\b", r"\bd[uú]plex\b", r"\bestudio\b",
    r"\blocal comercial\b", r"\bgaraje\b", r"\btrastero\b", r"\boficina\b",
    r"terreno urbano", r"suelo urbano", r"\burbanizable\b(?<!no urbanizable)",
]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower()
    return re.sub(r"\s+", " ", text)


def _match(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def classify(title: str, description: str = "") -> str | None:
    t, d = _norm(title), _norm(description)
    for kind, pats in KIND_PATTERNS:
        if _match(pats, t):
            return kind
    if _match(URBAN_EXCLUDE, t):
        return None
    # "no urbanizable" contiene "urbanizable": se trata aparte
    d_urban = re.sub(r"no urbanizable", "", d)
    for kind, pats in KIND_PATTERNS:
        if _match(pats, d):
            if kind == "terreno_rustico" and re.search(r"terreno urbano|suelo urbano|\burbanizable\b", d_urban):
                return None
            return kind
    return None
