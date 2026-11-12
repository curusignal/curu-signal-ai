"""Integración Mercado Pago Checkout Pro con validación de webhook."""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
import hmac
import os
import time
import uuid
from urllib.parse import urlparse

import requests

API_BASE = "https://api.mercadopago.com"


def _config():
    token = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip()
    base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not token:
        raise RuntimeError("Falta MERCADOPAGO_ACCESS_TOKEN")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("PUBLIC_BASE_URL debe ser una URL HTTPS pública")
    return token, base_url


def crear_preferencia(
    *,
    external_reference: str,
    amount_cop: int | Decimal | str | None = None,
    amount: int | Decimal | str | None = None,
    currency: str = "COP",
    duration_days: int = 30,
) -> tuple[str, str]:
    """Crea Checkout Pro usando la moneda exacta de la orden, no una moneda global."""
    token, base_url = _config()
    raw_amount = amount if amount is not None else amount_cop
    if raw_amount is None:
        raise ValueError("El importe de la preferencia es obligatorio")
    try:
        value = Decimal(str(raw_amount))
    except InvalidOperation as exc:
        raise ValueError("Importe de preferencia inválido") from exc
    code = str(currency).upper().strip()
    if not value.is_finite() or value <= 0 or not re.fullmatch(r"[A-Z]{3}", code):
        raise ValueError("Importe o moneda de preferencia inválidos")
    idem = str(uuid.uuid4())
    payload = {
        "items": [{
            "id": "curu-membership",
            "title": f"Membresía CURU SIGNAL AI - {duration_days} días",
            "quantity": 1,
            "currency_id": code,
            "unit_price": float(value),
        }],
        "external_reference": external_reference,
        "notification_url": f"{base_url}/webhook-pago",
        "back_urls": {
            "success": f"{base_url}/pago/resultado?estado=exitoso",
            "pending": f"{base_url}/pago/resultado?estado=pendiente",
            "failure": f"{base_url}/pago/resultado?estado=fallido",
        },
        "auto_return": "approved",
        "statement_descriptor": "CURU SIGNAL AI",
        "metadata": {
            "product": "membership", "duration_days": duration_days,
            "expected_currency": code, "expected_amount": str(value),
        },
    }
    response = requests.post(
        f"{API_BASE}/checkout/preferences", json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Idempotency-Key": idem},
        timeout=25,
    )
    response.raise_for_status()
    data = response.json()
    url = data.get("init_point")
    preference_id = data.get("id")
    if not url or not preference_id:
        raise RuntimeError("Mercado Pago no devolvió una preferencia válida")
    return str(url), str(preference_id)


def verificar_firma_webhook(signature: str | None, request_id: str | None, data_id: str | None, secret: str | None, *, tolerance_seconds: int = 300) -> bool:
    if not all((signature, request_id, data_id, secret)):
        return False
    parts = {}
    for part in signature.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            parts[key.strip()] = value.strip()
    ts, supplied = parts.get("ts"), parts.get("v1")
    if not ts or not supplied:
        return False
    try:
        stamp = int(ts)
        # Mercado Pago publica ejemplos en segundos; tolerar también milisegundos.
        if stamp > 10**12:
            stamp //= 1000
        if abs(int(time.time()) - stamp) > tolerance_seconds:
            return False
    except (TypeError, ValueError):
        return False
    normalized_id = str(data_id)
    if normalized_id.isalnum():
        normalized_id = normalized_id.lower()
    manifest = f"id:{normalized_id};request-id:{request_id};ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)


def obtener_pago(payment_id: str) -> dict:
    token, _ = _config()
    response = requests.get(
        f"{API_BASE}/v1/payments/{payment_id}",
        headers={"Authorization": f"Bearer {token}"}, timeout=20,
    )
    response.raise_for_status()
    return response.json()
