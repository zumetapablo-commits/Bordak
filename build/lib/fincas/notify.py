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
SOURCE_LABEL = {"cocampo": "Cocampo", "moldatu": "Moldatu Home", "siro": "SIRO Inmobiliaria",
                "milanuncios": "Milanuncios", "wallapop": "Wallapop"}


def _eur(v: int | None) -> str:
    return f"{v:,.0f} €".replace(",", ".") if v is not None else "A consultar"


def _km(v: float | None, approx: bool) -> str:
    if v is None:
        return "¿?"
    return f"{'≈' if approx else ''}{v:.1f} km".replace(".", ",")


def _score_color(score: float) -> str:
    return "#15803d" if score >= 60 else "#b45309" if score >= 40 else "#6b7280"


def _text_item(l: Listing) -> str:
    a = l.geo_approx
    return (
        f"[{l.score or 0:.0f}] {KIND_LABEL.get(l.kind, l.kind)} · {_eur(l.price)} · {l.municipality or '?'}"
        f"{' (ubicación aprox.)' if a else ''}\n"
        f"    {l.title}\n"
        f"    Costa {_km(l.coast_km, a)} · Zarautz {_km(l.zarautz_km, a)} · "
        f"surf {l.surf_spot} {_km(l.surf_km, a)} · Tolosa ~{l.tolosa_min or 0:.0f} min\n"
        f"    {SOURCE_LABEL.get(l.source, l.source)}: {l.url}"
    )


def _html_item(l: Listing) -> str:
    e, a = html.escape, l.geo_approx
    score = l.score or 0
    approx = " <span style='color:#6b7280'>(ubicación aproximada)</span>" if a else ""
    return f"""
<tr><td style="padding:0 0 14px 0">
 <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:10px">
  <tr><td style="padding:14px 16px">
   <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em">
      {e(KIND_LABEL.get(l.kind, l.kind or ''))} · {e(SOURCE_LABEL.get(l.source, l.source))}</td>
    <td align="right"><span style="background:{_score_color(score)};color:#fff;border-radius:12px;
      padding:2px 9px;font-size:12px;font-weight:bold">{score:.0f}/100</span></td>
   </tr></table>
   <div style="font-size:17px;font-weight:bold;margin:6px 0 2px 0">
     <a href="{e(l.url)}" style="color:#111827;text-decoration:none">{e(l.title)}</a></div>
   <div style="font-size:20px;font-weight:bold;color:#111827">{_eur(l.price)}
     <span style="font-size:14px;font-weight:normal;color:#374151"> · {e(l.municipality or '?')}</span>{approx}</div>
   <table cellpadding="0" cellspacing="0" style="margin-top:10px;font-size:14px;color:#374151">
    <tr><td style="padding:2px 14px 2px 0">🌊 Costa</td><td><b>{_km(l.coast_km, a)}</b></td></tr>
    <tr><td style="padding:2px 14px 2px 0">📍 Zarautz</td><td><b>{_km(l.zarautz_km, a)}</b></td></tr>
    <tr><td style="padding:2px 14px 2px 0">🏄 Surf</td><td><b>{_km(l.surf_km, a)}</b> ({e(l.surf_spot or '')})</td></tr>
    <tr><td style="padding:2px 14px 2px 0">🚗 Desde Tolosa</td><td><b>~{l.tolosa_min or 0:.0f} min</b></td></tr>
   </table>
   <div style="margin-top:12px"><a href="{e(l.url)}" style="background:#111827;color:#fff;text-decoration:none;
     padding:8px 14px;border-radius:6px;font-size:14px;display:inline-block">Ver anuncio</a></div>
  </td></tr>
 </table>
</td></tr>"""


def render(listings: list[Listing], warnings: list[str] | None = None) -> tuple[str, str, str]:
    listings = sorted(listings, key=lambda l: -(l.score or 0))
    priced = [l for l in listings if l.price is not None]
    on_request = [l for l in listings if l.price is None]
    n = len(listings)
    subject = f"🏡 {n} finca{'s' if n != 1 else ''} nueva{'s' if n != 1 else ''} en Gipuzkoa"
    if priced:
        subject += f" · desde {_eur(min(l.price for l in priced))}"

    text_parts = [_text_item(l) for l in priced]
    if on_request:
        text_parts.append("— Precio a consultar —")
        text_parts += [_text_item(l) for l in on_request]
    text_parts += [f"⚠ {w}" for w in warnings or []]
    text = "\n\n".join(text_parts)

    def section(title: str, items: list[Listing]) -> str:
        if not items:
            return ""
        return (f"<tr><td style='padding:8px 0 10px 0;font-size:15px;font-weight:bold;color:#374151'>{title}</td></tr>"
                + "".join(_html_item(l) for l in items))

    warn_html = "".join(
        f"<tr><td style='padding:6px 10px;background:#fef3c7;color:#92400e;font-size:13px;border-radius:6px'>"
        f"⚠ {html.escape(w)}</td></tr>" for w in warnings or [])
    body = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:16px 0">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:12px;
  padding:20px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
 <tr><td style="font-size:22px;font-weight:bold;color:#111827;padding-bottom:4px">{html.escape(subject)}</td></tr>
 <tr><td style="font-size:13px;color:#6b7280;padding-bottom:16px">Filtros: ≤ 250.000 € · ≤ 15 km de la costa.
   Ordenado por puntuación (cercanía a Zarautz y a playas de surf, tiempo desde Tolosa, precio).
   «≈» = ubicación aproximada por el municipio.</td></tr>
 {section("Con precio", priced)}
 {section("Precio a consultar", on_request)}
 {warn_html}
 <tr><td style="font-size:12px;color:#9ca3af;padding-top:10px">Buscador de fincas · Bordak</td></tr>
</table></td></tr></table>"""
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
    msg.add_alternative(f"<html><body style='margin:0'>{html_body}</body></html>", subtype="html")
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
