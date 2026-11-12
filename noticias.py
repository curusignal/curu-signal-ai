"""Obtención prudente de titulares desde Yahoo Finance.

Los titulares son contexto, no evidencia automática de causalidad ni señal.
No se inventan fechas cuando el proveedor no entrega un timestamp válido.
"""
from datetime import datetime, timedelta, timezone
import logging
import yfinance as yf

log = logging.getLogger("curu.noticias")


def _fecha_publicacion(nota):
    ts = nota.get("providerPublishTime")
    if ts is None:
        content = nota.get("content") or {}
        ts = content.get("pubDate")
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(ts, str):
            value = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None
    return None


def _normalizar_noticias(raw, tipo, horas=72, limite=5):
    salida = []
    if isinstance(raw, dict):
        raw = raw.get("news", [])
    if not isinstance(raw, list):
        return salida

    ahora = datetime.now(timezone.utc)
    desde = ahora - timedelta(hours=horas)

    for nota in raw:
        if not isinstance(nota, dict):
            continue
        contenido = nota.get("content") or {}
        titulo = nota.get("title") or contenido.get("title")
        proveedor = nota.get("publisher")
        if not proveedor:
            proveedor = (contenido.get("provider") or {}).get("displayName")
        fecha = _fecha_publicacion(nota)

        if not titulo or not fecha or fecha < desde or fecha > ahora:
            continue

        enlace = nota.get("link") or contenido.get("canonicalUrl", {}).get("url")
        salida.append({
            "titulo": str(titulo).strip(),
            "fuente": str(proveedor or "Fuente no especificada"),
            "tipo": tipo,
            "fecha": fecha.isoformat(),
            "url": enlace,
        })

    salida.sort(key=lambda x: x["fecha"], reverse=True)
    return salida[:limite]


def extraer_noticias_micro(ticker_nombre, horas=72, limite=5):
    try:
        raw = yf.Ticker(ticker_nombre).news
        return _normalizar_noticias(raw, f"MICRO · {ticker_nombre}", horas, limite)
    except Exception as exc:
        log.warning("No se pudieron obtener noticias de %s: %s", ticker_nombre, exc)
        return []


def extraer_noticias_macro(horas=72, limite=5):
    """Usa noticias del S&P 500 como proxy de contexto bursátil general."""
    try:
        raw = yf.Ticker("^GSPC").news
        return _normalizar_noticias(raw, "MACRO · S&P 500", horas, limite)
    except Exception as exc:
        log.warning("No se pudieron obtener noticias macro: %s", exc)
        return []
