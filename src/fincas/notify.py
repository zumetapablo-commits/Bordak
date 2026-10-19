"""Aviso por correo (SMTP). Configuración por variables de entorno:
SMTP_HOST, SMTP_PORT (587 STARTTLS / 465 SSL), SMTP_USER, SMTP_PASSWORD, MAIL_TO, MAIL_FROM (opcional).
"""
from __future__ import annotations

import html
import os
import smtplib
import ssl
from email.message import EmailMessage

from .models import Listing

KIND_LABEL = {
    "terreno_rustico": "Terreno rústico", "borda": "Borda", "caseta": "Caseta",
    "caserio": "Caserío", "finca_rustica": "Finca rústica", "huerta": "Huerta",
}


def _eur(v: int | None) -> str:
    return f"{v:,.0f} €".replace(",", ".") if v is not None else "¿?"


def _km(v: float | None, approx: bool) -> str:
    if v is None:
        return "¿?"
    return f"{'≈' if approx else ''}{v:.1f} km"


def render(listings: list[Listing], warnings: list[str] | None = None) -> tuple[str, str, str]:
    listings = sorted(listings, key=lambda l: -(l.score or 0))
    n = len(listings)
    subject = f"🏡 {n} finca{'s' if n != 1 else ''} nueva{'s' if n != 1 else ''} en Gipuzkoa"
    if listings:
        top = listings[0]
        subject += f" · {_eur(top.price)} {top.municipality or ''}".rstrip()

    text_lines, rows = [], []
    for l in listings:
        a = l.geo_approx
        line = (
            f"[{l.score:.0f}] {KIND_LABEL.get(l.kind, l.kind)} · {_eur(l.price)} · {l.municipality or '?'}\n"
            f"    {l.title}\n"
            f"    Costa {_km(l.coast_km, a)} · Zarautz {_km(l.zarautz_km, a)} · "
            f"{l.surf_spot} {_km(l.surf_km, a)} · Tolosa ~{l.tolosa_min:.0f} min\n"
            f"    {l.url}"
        )
        text_lines.append(line)
        e = html.escape
        rows.append(
            f"<tr><td style='font-weight:bold'>{l.score:.0f}</td>"
            f"<td><a href='{e(l.url)}'>{e(l.title)}</a><br><small>{e(KIND_LABEL.get(l.kind, l.kind or ''))}"
            f" · {e(l.source)}</small></td>"
            f"<td style='white-space:nowrap'>{_eur(l.price)}</td><td>{e(l.municipality or '?')}"
            f"{' <small>(aprox.)</small>' if a else ''}</td>"
            f"<td>{_km(l.coast_km, a)}</td><td>{_km(l.zarautz_km, a)}</td>"
            f"<td>{e(l.surf_spot or '')}<br>{_km(l.surf_km, a)}</td><td>~{l.tolosa_min:.0f} min</td></tr>"
        )
    warn_txt = "\n".join(f"⚠ {w}" for w in warnings or [])
    text = "\n\n".join(text_lines) + (f"\n\n{warn_txt}" if warn_txt else "")
    head = "".join(f"<th align='left'>{h}</th>" for h in
                   ["Punt.", "Anuncio", "Precio", "Municipio", "Costa", "Zarautz", "Surf", "Tolosa"])
    body = (
        "<p style='font-family:sans-serif'>≈ = ubicación aproximada (centroide del municipio).</p>"
        f"<table cellpadding='6' style='border-collapse:collapse;font-family:sans-serif;font-size:14px'>"
        f"<tr>{head}</tr>{''.join(rows)}</table>"
        + "".join(f"<p style='color:#b45309'>⚠ {html.escape(w)}</p>" for w in warnings or [])
    )
    return subject, text, body


def send(subject: str, text: str, html_body: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    to = os.environ["MAIL_TO"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("MAIL_FROM", user)
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(f"<html><body>{html_body}</body></html>", subtype="html")
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)
