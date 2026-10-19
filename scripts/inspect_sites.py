"""Inspección única de las webs: descarga robots.txt, portada y páginas de listado candidatas.

Respeta robots.txt y 1 petición/s por host (PoliteClient). Guarda todo en inspect/<sitio>/
junto con un summary.json que describe cómo está construida cada página.
Uso: python scripts/inspect_sites.py scripts/sites.yaml
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import yaml
from selectolax.lexbor import LexborHTMLParser as HTMLParser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fincas.http import PoliteClient, RobotsDisallowed  # noqa: E402

OUT = ROOT / "inspect"
UA = "fincas-gipuzkoa-bot/0.1 (inspeccion puntual, uso personal)"
LINK_RE = re.compile(
    r"venta|vender|comprar|erosi|salgai|inmueble|propiedad|propiedades|terreno|r[uú]stic|caser|baserri|"
    r"finca|borda|buscar|search|resultado|listado|catalog|inmobiliaria|etxebizitz",
    re.I,
)
MAX_LINKS = 8


def describe(html: str, url: str) -> dict:
    tree = HTMLParser(html)
    scripts = tree.css("script")
    body_text = tree.body.text(separator=" ", strip=True) if tree.body else ""
    return {
        "url": url,
        "title": (tree.css_first("title").text(strip=True) if tree.css_first("title") else None),
        "bytes": len(html),
        "text_chars": len(body_text),
        "n_scripts": len(scripts),
        "json_ld": [s.text()[:600] for s in tree.css('script[type="application/ld+json"]')][:3],
        "next_data": bool(tree.css_first("script#__NEXT_DATA__")),
        "nuxt": "__NUXT__" in html,
        "wordpress": "wp-content" in html,
        "generator": [m.attributes.get("content") for m in tree.css('meta[name="generator"]')],
        "prices_found": re.findall(r"\d{1,3}(?:\.\d{3})+\s?€", html)[:10],
        "api_hints": sorted(set(re.findall(r"""["'](/(?:api|wp-json|ajax)[^"'\s]{0,80})["']""", html)))[:15],
        "text_sample": body_text[:800],
    }


def candidate_links(html: str, base: str) -> list[str]:
    host = urlsplit(base).netloc
    seen, out = set(), []
    for a in HTMLParser(html).css("a[href]"):
        href = urljoin(base, a.attributes.get("href") or "").split("#")[0]
        if urlsplit(href).netloc != host or href in seen:
            continue
        if LINK_RE.search(href) or LINK_RE.search(a.text(strip=True) or ""):
            seen.add(href)
            out.append(href)
    return out[:MAX_LINKS]


def save(dirpath: Path, name: str, text: str) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / name).write_text(text, encoding="utf-8")


def inspect_site(client: PoliteClient, name: str, spec: dict) -> dict:
    d = OUT / name
    report: dict = {"site": name, "tried": [], "pages": []}
    base = None
    for cand in spec.get("candidates", []):
        try:
            r = client._raw_get(cand)
            report["tried"].append({"url": cand, "status": r.status_code, "final": str(r.url)})
            if r.status_code < 400:
                base = str(r.url)
                break
        except Exception as e:  # noqa: BLE001
            report["tried"].append({"url": cand, "error": repr(e)[:200]})
    if not base:
        return report

    parts = urlsplit(base)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        rr = client._raw_get(robots_url)
        save(d, "robots.txt", f"# status {rr.status_code}\n{rr.text}")
        report["robots_status"] = rr.status_code
    except Exception as e:  # noqa: BLE001
        report["robots_status"] = repr(e)[:200]

    urls = [base] + list(spec.get("extra", []))
    i = 0
    while i < len(urls) and i < 1 + MAX_LINKS + len(spec.get("extra", [])):
        url = urls[i]
        i += 1
        try:
            r = client.get(url)
        except RobotsDisallowed:
            report["pages"].append({"url": url, "robots": "DISALLOWED"})
            continue
        except Exception as e:  # noqa: BLE001
            report["pages"].append({"url": url, "error": repr(e)[:200]})
            continue
        fname = f"{len(report['pages']):02d}.html"
        save(d, fname, r.text)
        info = describe(r.text, str(r.url))
        info["file"] = fname
        report["pages"].append(info)
        if url == base:
            report["home_links"] = candidate_links(r.text, base)
            urls[1:1] = [u for u in report["home_links"] if u not in urls]
    return report


def main() -> None:
    sites = yaml.safe_load(Path(sys.argv[1]).read_text())
    only = sys.argv[2:]
    with PoliteClient(UA, min_interval_s=1.5, timeout_s=30, retries=1) as client:
        for name, spec in sites.items():
            if only and name not in only:
                continue
            print("==", name, flush=True)
            rep = inspect_site(client, name, spec)
            save(OUT / name, "summary.json", json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
