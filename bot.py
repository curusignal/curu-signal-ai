"""Aplicación Telegram + webhooks + entrega programada de CURU SIGNAL AI."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass

import telebot
from telebot import types
from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

import database as db
from pagos import crear_preferencia, obtener_pago, verificar_firma_webhook

LOG = logging.getLogger("curu.bot")
TZ_NAME = os.getenv("TIMEZONE", "America/Bogota")
TZ = ZoneInfo(TZ_NAME)
DURATION_DAYS = int(os.getenv("DURACION_SUSCRIPCION_DIAS", "30"))
REPORT_HOUR = int(os.getenv("REPORT_HOUR", "4"))
REPORT_MINUTE = int(os.getenv("REPORT_MINUTE", "0"))
ADMIN_IDS = {x.strip() for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_TOKEN:
    raise RuntimeError("Falta TELEGRAM_BOT_TOKEN")
def _load_price_catalog() -> dict:
    raw = os.getenv("CURU_PRICE_CATALOG", "").strip()
    if raw:
        try:
            catalog = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("CURU_PRICE_CATALOG debe ser JSON válido") from exc
    else:
        catalog = {"CO": {"label": "Colombia", "currency": "COP", "amount": os.getenv("PRECIO_SUSCRIPCION_COP", "30000")}}
    if not isinstance(catalog, dict) or not catalog:
        raise RuntimeError("CURU_PRICE_CATALOG debe contener al menos un mercado")
    validated = {}
    for country, item in catalog.items():
        code = str(country).upper().strip()
        if len(code) != 2 or not code.isalpha() or not isinstance(item, dict):
            raise RuntimeError("Mercado inválido en CURU_PRICE_CATALOG")
        currency = str(item.get("currency", "")).upper().strip()
        label = str(item.get("label", code)).strip()
        try:
            amount = Decimal(str(item.get("amount", "")))
        except InvalidOperation as exc:
            raise RuntimeError(f"Importe inválido para mercado {code}") from exc
        if len(currency) != 3 or not currency.isalpha() or not label or not amount.is_finite() or amount <= 0:
            raise RuntimeError(f"Configuración inválida para mercado {code}")
        validated[code] = {"label": label, "currency": currency, "amount": amount}
    return validated

PRICE_CATALOG = _load_price_catalog()
if DURATION_DAYS <= 0:
    raise RuntimeError("La duración de suscripción debe ser positiva")

def _format_amount(amount: Decimal) -> str:
    if amount == amount.to_integral_value():
        return f"{int(amount):,}".replace(",", ".")
    return format(amount.normalize(), "f")

def _membership_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for country, item in PRICE_CATALOG.items():
        label = f"{item['label']} · {item['currency']} {_format_amount(item['amount'])} / {DURATION_DAYS} días"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"comprar_{country}"))
    return markup


bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML", threaded=True)
app = Flask(__name__)
_report_lock = threading.Lock()
_trial_guard = threading.Lock()
_trial_inflight: set[int] = set()


def _escape(value: str | None) -> str:
    from html import escape
    return escape(value or "", quote=True)


def _get_report():
    report = db.latest_report()
    if report and Path(report.file_path).is_file():
        try:
            report_age = (datetime.now(TZ).date() - datetime.strptime(report.report_date, "%Y-%m-%d").date()).days
        except ValueError:
            report_age = 999
        if 0 <= report_age <= 7:
            return report
    # Primera generación bajo demanda: el lock evita que varios registros
    # nuevos disparen escaneos duplicados del universo completo.
    with _report_lock:
        report = db.latest_report()
        if report and Path(report.file_path).is_file():
            try:
                report_age = (datetime.now(TZ).date() - datetime.strptime(report.report_date, "%Y-%m-%d").date()).days
            except ValueError:
                report_age = 999
            if 0 <= report_age <= 7:
                return report
        from orquestador import ejecutar_sistema_premium_automatizado
        ejecutar_sistema_premium_automatizado()
        report = db.latest_report()
        if not report or not Path(report.file_path).is_file():
            raise RuntimeError("El informe no quedó disponible en almacenamiento")
        return report


def _deliver_trial(telegram_id: str, user_db_id: int):
    with _trial_guard:
        if user_db_id in _trial_inflight:
            return
        _trial_inflight.add(user_db_id)
    try:
        bot.send_message(telegram_id, "⏳ Estamos preparando tu informe de cortesía. Analizamos los datos y te lo enviaremos aquí mismo.")
        report = _get_report()
        if db.trial_state(user_db_id) == "sent":
            return
        with open(report.file_path, "rb") as pdf:
            bot.send_document(
                telegram_id, pdf,
                caption=(
                    "🎁 <b>Tu informe de cortesía CURU SIGNAL AI</b>\n\n"
                    "Este es el informe completo, el mismo formato analítico que reciben nuestros miembros. "
                    "Revísalo con calma y conoce cómo trabajamos.\n\n"
                    "Importante: los sesgos y scores son métricas técnicas, no probabilidades de acierto ni garantías de rentabilidad."
                ),
            )
        db.record_delivery(report.id, user_db_id, "trial", "sent")
        db.mark_trial(user_db_id, "sent", report_id=report.id)
        markup = _membership_markup()
        bot.send_message(
            telegram_id,
            "¿Te gustaría recibir los próximos informes y mantener tu acceso? Puedes activar tu membresía cuando quieras.",
            reply_markup=markup,
        )
    except Exception as exc:
        LOG.exception("No se pudo entregar cortesía a usuario %s", telegram_id)
        try:
            db.mark_trial(user_db_id, "failed", error=type(exc).__name__)
        except Exception:
            LOG.exception("No se pudo registrar fallo de cortesía")
        try:
            bot.send_message(telegram_id, "Tuvimos un inconveniente técnico preparando tu informe. Tu solicitud quedó registrada y nuestro equipo podrá reintentar la entrega.")
        except Exception:
            pass
    finally:
        with _trial_guard:
            _trial_inflight.discard(user_db_id)


def _send_current_report(telegram_id: str, user_db_id: int, delivery_type: str = "subscriber"):
    report = _get_report()
    if db.delivery_was_sent(report.id, user_db_id, delivery_type):
        return False
    db.record_delivery(report.id, user_db_id, delivery_type, "pending")
    with open(report.file_path, "rb") as pdf:
        bot.send_document(telegram_id, pdf, caption=f"📊 <b>Informe CURU SIGNAL AI · {report.report_date}</b>\nAnálisis cuantitativo del universo S&amp;P 500.")
    db.record_delivery(report.id, user_db_id, delivery_type, "sent")
    return True


def _daily_report_job():
    LOG.info("Inicio de generación diaria")
    try:
        # Fuerza una actualización diaria; el PDF se guarda en REPORTS_DIR.
        from orquestador import ejecutar_sistema_premium_automatizado
        with _report_lock:
            ejecutar_sistema_premium_automatizado()
        report = db.latest_report()
        if not report:
            raise RuntimeError("No se registró el reporte diario")
        for user_id, telegram_id in db.active_subscriber_ids():
            if db.delivery_was_sent(report.id, user_id, "subscriber"):
                continue
            try:
                db.record_delivery(report.id, user_id, "subscriber", "pending")
                with open(report.file_path, "rb") as pdf:
                    bot.send_document(telegram_id, pdf, caption=f"📊 <b>Tu informe diario CURU SIGNAL AI · {report.report_date}</b>")
                db.record_delivery(report.id, user_id, "subscriber", "sent")
            except Exception as exc:
                LOG.warning("Fallo entregando reporte a %s: %s", telegram_id, type(exc).__name__)
                db.record_delivery(report.id, user_id, "subscriber", "failed", type(exc).__name__)
    except Exception:
        LOG.exception("Falló el proceso diario; no se enviará un informe incompleto")


def _process_webhook_queue():
    for event_id, topic, resource_id in db.pending_webhooks(limit=10):
        try:
            if topic != "payment":
                db.finish_webhook(event_id)
                continue
            payment = obtener_pago(resource_id)
            if payment.get("status") == "approved":
                applied, telegram_id = db.process_approved_payment(payment, DURATION_DAYS)
                if applied and telegram_id:
                    bot.send_message(
                        telegram_id,
                        f"🎉 <b>¡Pago aprobado!</b> Tu membresía CURU SIGNAL AI está activa por {DURATION_DAYS} días.\n\nYa puedes solicitar tu informe actual desde el menú.",
                    )
            else:
                revoked = db.reconcile_non_approved_payment(payment)
                if revoked:
                    LOG.warning("Acceso revocado por reversión del pago %s", resource_id)
            db.finish_webhook(event_id)
        except Exception as exc:
            LOG.exception("Error procesando webhook persistido %s", event_id)
            try:
                db.finish_webhook(event_id, error=type(exc).__name__)
            except Exception:
                LOG.exception("No se pudo actualizar webhook %s", event_id)


def _worker_loop():
    while True:
        try:
            _process_webhook_queue()
        except Exception:
            LOG.exception("Error en worker de webhooks")
        time.sleep(3)


@bot.message_handler(commands=["start", "help"])
def start(message):
    if message.chat.type != "private":
        bot.reply_to(message, "Por seguridad, inicia CURU SIGNAL AI en un chat privado con el bot.")
        return
    user = message.from_user
    user_db, is_new = db.register_user(
        message.chat.id, username=user.username, first_name=user.first_name,
        last_name=user.last_name, language_code=user.language_code,
    )
    active = db.is_subscription_active(message.chat.id)
    greeting = _escape(user.first_name or "")
    text = (
        f"🎯 <b>¡Bienvenido a CURU SIGNAL AI, {greeting}!</b>\n\n"
        "Tu terminal de análisis cuantitativo del S&amp;P 500 combina indicadores técnicos, "
        "volatilidad, liquidez y contexto informativo.\n\n"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    if is_new:
        reserved = db.claim_trial_once(user_db.id)
        if reserved:
            text += "🎁 <b>Tienes un informe completo de cortesía.</b> Lo estamos preparando para que conozcas el servicio antes de decidir."
            bot.send_message(message.chat.id, text)
            threading.Thread(target=_deliver_trial, args=(str(message.chat.id), user_db.id), daemon=True).start()
            return
    if active:
        text += "✅ <b>Tu membresía está activa.</b> Puedes descargar el informe vigente o consultar la renovación."
        markup.add(types.InlineKeyboardButton("📊 Descargar informe actual", callback_data="pedir_pdf"))
    else:
        trial_status = db.trial_state(user_db.id)
        if trial_status == "sent":
            text += "Tu informe de cortesía ya fue entregado. Si quieres continuar recibiendo los informes, puedes activar tu membresía."
        elif trial_status in {"pending", "failed"}:
            text += "Tu informe de cortesía está reservado. Estamos reintentando la entrega si quedó pendiente."
            threading.Thread(target=_deliver_trial, args=(str(message.chat.id), user_db.id), daemon=True).start()
        else:
            text += "Actualmente no tienes una membresía activa."
        membership_markup = _membership_markup()
        for button_row in membership_markup.keyboard:
            markup.row(*button_row)
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=["reintentar_cortesia"])
def retry_trial(message):
    if str(message.from_user.id) not in ADMIN_IDS:
        bot.reply_to(message, "Comando no autorizado.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().isdigit():
        bot.reply_to(message, "Uso: /reintentar_cortesia TELEGRAM_ID")
        return
    target = parts[1].strip()
    user_db_id = db.get_user_id(target)
    if not user_db_id:
        bot.reply_to(message, "No existe ese usuario.")
        return
    state = db.trial_state(user_db_id)
    if state not in {"pending", "failed"}:
        bot.reply_to(message, "La cortesía no está pendiente de entrega o ya fue enviada.")
        return
    threading.Thread(target=_deliver_trial, args=(target, user_db_id), daemon=True).start()
    bot.reply_to(message, "Reintento de la misma cortesía iniciado.")


@bot.callback_query_handler(func=lambda call: call.data == "pedir_pdf" or call.data == "comprar_acceso" or call.data.startswith("comprar_"))
def callbacks(call):
    telegram_id = str(call.message.chat.id)
    user_db_id = db.get_user_id(telegram_id)
    if not user_db_id:
        bot.answer_callback_query(call.id, "Inicia el bot con /start", show_alert=True)
        return
    if call.data == "pedir_pdf":
        if not db.is_subscription_active(telegram_id):
            bot.answer_callback_query(call.id, "Tu membresía no está activa.", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(telegram_id, "⏳ Preparando el informe vigente...")
        try:
            _send_current_report(telegram_id, user_db_id)
        except Exception:
            LOG.exception("Error enviando informe solicitado")
            bot.send_message(telegram_id, "No pudimos entregar el archivo en este momento. Inténtalo más tarde.")
        return

    bot.answer_callback_query(call.id)
    try:
        country = call.data.removeprefix("comprar_") if call.data != "comprar_acceso" else "CO"
        item = PRICE_CATALOG.get(country)
        if item is None:
            bot.send_message(telegram_id, "Ese mercado no está habilitado todavía. Elige una de las monedas disponibles.")
            return
        external_reference = str(uuid.uuid4())
        db.create_payment_intent(telegram_id, external_reference, amount=item["amount"], currency=item["currency"])
        url, preference_id = crear_preferencia(
            external_reference=external_reference, amount=item["amount"], currency=item["currency"],
            duration_days=DURATION_DAYS,
        )
        db.attach_preference(external_reference, preference_id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Pagar con Mercado Pago", url=url))
        bot.send_message(telegram_id, "Tu enlace de pago seguro está listo. El acceso se activa únicamente cuando Mercado Pago confirme el pago.", reply_markup=markup)
    except Exception as exc:
        LOG.exception("No se pudo crear preferencia de pago")
        bot.send_message(telegram_id, "No pudimos generar el enlace de pago ahora. Inténtalo de nuevo en unos minutos.")


@app.get("/health")
def health():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "ok"}), 200
    except Exception:
        LOG.exception("Health check DB failed")
        return jsonify({"status": "degraded"}), 503


@app.get("/pago/resultado")
def payment_result():
    status = request.args.get("estado", "recibido")
    return (f"<h2>CURU SIGNAL AI</h2><p>Estado de retorno: { _escape(status) }.</p><p>La activación depende de la confirmación directa de Mercado Pago; no cierres Telegram todavía.</p>"), 200


@app.post("/webhook-pago")
def payment_webhook():
    payload = request.get_json(silent=True) or {}
    resource_id = request.args.get("data.id") or (payload.get("data") or {}).get("id")
    topic = payload.get("type") or request.args.get("type") or request.args.get("topic")
    if not resource_id or topic != "payment":
        return jsonify({"status": "ignored"}), 200
    secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
    if not verificar_firma_webhook(
        request.headers.get("x-signature"), request.headers.get("x-request-id"),
        request.args.get("data.id"), secret,
    ):
        LOG.warning("Webhook Mercado Pago rechazado: firma inválida o ausente")
        return jsonify({"status": "unauthorized"}), 401
    action = str(payload.get("action", "notification"))
    event_key = f"{topic}:{resource_id}:{action}:{payload.get('id', '')}"
    db.enqueue_webhook(event_key[:100], "payment", str(resource_id))
    return jsonify({"status": "accepted"}), 200


@app.get("/webhook-cron")
def manual_cron():
    # Compatibilidad con cron externo, protegido por secreto compartido.
    supplied = request.headers.get("X-Curu-Cron", "")
    expected = os.getenv("CRON_SECRET", "")
    if not expected or not __import__("hmac").compare_digest(supplied, expected):
        return jsonify({"status": "unauthorized"}), 401
    threading.Thread(target=_daily_report_job, daemon=True).start()
    return jsonify({"status": "started"}), 202


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    db.init_db()
    scheduler = BackgroundScheduler(timezone=TZ)
    scheduler.add_job(
        _daily_report_job, "cron", hour=REPORT_HOUR, minute=REPORT_MINUTE,
        id="daily_market_report", replace_existing=True, max_instances=1, coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    threading.Thread(target=_worker_loop, daemon=True, name="mp-webhook-worker").start()
    from werkzeug.serving import make_server
    port = int(os.getenv("PORT", "5000"))
    server = make_server("0.0.0.0", port, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True, name="http-server").start()
    LOG.info("CURU SIGNAL AI iniciado; zona=%s; reporte diario=%02d:%02d", TZ_NAME, REPORT_HOUR, REPORT_MINUTE)
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
