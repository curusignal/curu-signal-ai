"""Persistencia transaccional de CURU SIGNAL AI.

En producción DATABASE_URL debe apuntar a PostgreSQL. SQLite se admite solo
para desarrollo local. Los registros comerciales son históricos: este módulo
no expone operaciones de borrado.
"""
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
    create_engine, event, select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _database_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw and os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError("DATABASE_URL es obligatorio en producción; no se permite SQLite efímero")
    url = raw or "sqlite:///./curu_dev.db"
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+" not in url.split(":", 1)[0]:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")
if not IS_SQLITE and not DATABASE_URL.startswith("postgresql+"):
    raise RuntimeError("DATABASE_URL debe ser PostgreSQL en producción o SQLite en desarrollo.")

_engine_options = {"pool_pre_ping": True, "pool_recycle": 1800}
if IS_SQLITE:
    _engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **_engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(128))
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    last_name: Mapped[Optional[str]] = mapped_column(String(128))
    language_code: Mapped[Optional[str]] = mapped_column(String(16))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class TrialGrant(Base):
    __tablename__ = "trial_grants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)  # pending/sent/failed
    report_id: Mapped[Optional[int]] = mapped_column(ForeignKey("reports.id", ondelete="RESTRICT"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    report_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ready", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    source_payment_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PaymentIntent(Base):
    __tablename__ = "payment_intents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_reference: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    expected_amount_cop: Mapped[int] = mapped_column(Integer, nullable=False)
    preference_id: Mapped[Optional[str]] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="created", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_payment_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    preference_id: Mapped[Optional[str]] = mapped_column(String(80))
    amount_cop: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="COP", nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    raw_reference: Mapped[Optional[str]] = mapped_column(Text)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReportDelivery(Base):
    __tablename__ = "report_deliveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    delivery_type: Mapped[str] = mapped_column(String(16), nullable=False)  # trial/subscriber
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("report_id", "user_id", "delivery_type", name="uq_report_user_type"),)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_event_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


Index("ix_subscriptions_user_end", Subscription.user_id, Subscription.ends_at)


def init_db() -> None:
    Base.metadata.create_all(engine)
    # Defensa adicional para desarrollo SQLite. En PostgreSQL aplicar también
    # migrations/001_immutable_history.sql y restringir DELETE al rol de app.
    historical_tables = ("users", "trial_grants", "reports", "subscriptions", "payment_intents", "payments", "report_deliveries", "webhook_events", "audit_events")
    with engine.begin() as conn:
        if IS_SQLITE:
            for table in historical_tables:
                conn.exec_driver_sql(
                    f"CREATE TRIGGER IF NOT EXISTS prevent_delete_{table} "
                    f"BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'historical records are immutable'); END"
                )
        else:
            conn.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION curu_prevent_historical_mutation()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'CURU historical records are immutable';
                END;
                $$ LANGUAGE plpgsql;
            """)
            for table in historical_tables:
                conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS curu_no_delete_{table} ON {table}")
                conn.exec_driver_sql(
                    f"CREATE TRIGGER curu_no_delete_{table} BEFORE DELETE ON {table} "
                    f"FOR EACH ROW EXECUTE FUNCTION curu_prevent_historical_mutation()"
                )
                conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS curu_no_truncate_{table} ON {table}")
                conn.exec_driver_sql(
                    f"CREATE TRIGGER curu_no_truncate_{table} BEFORE TRUNCATE ON {table} "
                    f"FOR EACH STATEMENT EXECUTE FUNCTION curu_prevent_historical_mutation()"
                )


def register_user(telegram_id: int | str, *, username=None, first_name=None, last_name=None, language_code=None) -> tuple[User, bool]:
    """Crea/actualiza el perfil y devuelve (usuario, es_nuevo). Nunca reemplaza su ID."""
    tid = str(telegram_id)
    with SessionLocal.begin() as session:
        user = session.scalar(select(User).where(User.telegram_id == tid))
        created = user is None
        if created:
            user = User(telegram_id=tid)
            session.add(user)
            session.flush()
            session.add(AuditEvent(user_id=user.id, event_type="user_registered"))
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.language_code = language_code
        session.flush()
        session.expunge(user)
    return user, created


def claim_trial_once(user_id: int) -> bool:
    """Reserva el único informe gratuito del usuario, atómicamente."""
    try:
        with SessionLocal.begin() as session:
            exists = session.scalar(select(TrialGrant.id).where(TrialGrant.user_id == user_id))
            if exists:
                return False
            session.add(TrialGrant(user_id=user_id, status="pending"))
            session.add(AuditEvent(user_id=user_id, event_type="trial_reserved"))
            session.flush()
        return True
    except IntegrityError:
        # Otra actualización concurrente ya reservó el beneficio.
        return False


def mark_trial(user_id: int, status: str, *, report_id: int | None = None, error: str | None = None) -> None:
    if status not in {"pending", "sent", "failed"}:
        raise ValueError("Estado de cortesía no válido")
    with SessionLocal.begin() as session:
        grant = session.scalar(select(TrialGrant).where(TrialGrant.user_id == user_id).with_for_update())
        if grant is None:
            raise LookupError("No existe reserva de cortesía")
        # Nunca retroceder una cortesía ya entregada.
        if grant.status == "sent" and status != "sent":
            return
        grant.status = status
        grant.report_id = report_id or grant.report_id
        grant.last_error = error[:2000] if error else None
        if status == "sent":
            grant.delivered_at = utcnow()
        session.add(AuditEvent(user_id=user_id, event_type=f"trial_{status}", details=error[:500] if error else None))


def is_subscription_active(telegram_id: int | str) -> bool:
    now = utcnow()
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.telegram_id == str(telegram_id)))
        if user is None:
            return False
        end = session.scalar(
            select(Subscription.ends_at).where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
                Subscription.ends_at > now,
            ).order_by(Subscription.ends_at.desc()).limit(1)
        )
        return end is not None


def create_payment_intent(telegram_id: int | str, external_reference: str, amount_cop: int) -> int:
    with SessionLocal.begin() as session:
        user = session.scalar(select(User).where(User.telegram_id == str(telegram_id)))
        if user is None:
            raise LookupError("Usuario no registrado")
        intent = PaymentIntent(external_reference=external_reference, user_id=user.id, expected_amount_cop=amount_cop)
        session.add(intent)
        session.flush()
        return intent.id


def attach_preference(external_reference: str, preference_id: str) -> None:
    with SessionLocal.begin() as session:
        intent = session.scalar(select(PaymentIntent).where(PaymentIntent.external_reference == external_reference).with_for_update())
        if intent is None:
            raise LookupError("Intención de pago no encontrada")
        intent.preference_id = str(preference_id)


def process_approved_payment(payment: dict, duration_days: int = 30) -> tuple[bool, str | None]:
    """Registra pago aprobado y activa/extiende suscripción una sola vez."""
    payment_id = str(payment.get("id", ""))
    external_reference = str(payment.get("external_reference", ""))
    if not payment_id or not external_reference:
        raise ValueError("Pago sin identificador o referencia externa")
    if payment.get("status") != "approved":
        return False, None
    try:
        amount = Decimal(str(payment.get("transaction_amount", "0")))
    except InvalidOperation as exc:
        raise ValueError("Monto de pago inválido") from exc
    currency = str(payment.get("currency_id", "")).upper()
    with SessionLocal.begin() as session:
        existing = session.scalar(select(Payment.id).where(Payment.provider_payment_id == payment_id))
        if existing:
            return False, None
        intent = session.scalar(select(PaymentIntent).where(PaymentIntent.external_reference == external_reference).with_for_update())
        if intent is None:
            raise ValueError("Referencia de pago desconocida")
        if amount != Decimal(intent.expected_amount_cop) or currency != "COP":
            raise ValueError("Monto o moneda del pago no coinciden con la orden")
        if str(payment.get("external_reference")) != external_reference:
            raise ValueError("Referencia externa inválida")
        user = session.get(User, intent.user_id)
        if user is None:
            raise LookupError("Usuario de pago no encontrado")
        payment_row = Payment(
            provider_payment_id=payment_id, user_id=user.id, preference_id=intent.preference_id,
            amount_cop=int(amount), currency=currency, status="approved", raw_reference=external_reference,
        )
        session.add(payment_row)
        now = utcnow()
        last_end = session.scalar(
            select(Subscription.ends_at).where(Subscription.user_id == user.id, Subscription.status == "active")
            .order_by(Subscription.ends_at.desc()).limit(1).with_for_update()
        )
        if last_end is not None and last_end.tzinfo is None:
            last_end = last_end.replace(tzinfo=timezone.utc)
        start = last_end if last_end and last_end > now else now
        from datetime import timedelta
        session.add(Subscription(user_id=user.id, starts_at=start, ends_at=start + timedelta(days=duration_days),
                                 status="active", source_payment_id=payment_id))
        intent.status = "approved"
        session.add(AuditEvent(user_id=user.id, event_type="payment_approved", details=f"payment_id={payment_id}; amount={int(amount)} COP"))
        return True, user.telegram_id


def enqueue_webhook(provider_event_id: str, topic: str, resource_id: str) -> bool:
    try:
        with SessionLocal.begin() as session:
            session.add(WebhookEvent(provider_event_id=provider_event_id, topic=topic, resource_id=resource_id))
            session.flush()
        return True
    except IntegrityError:
        return False

def pending_webhooks(limit: int = 20) -> list[tuple[int, str, str]]:
    with SessionLocal() as session:
        rows = session.scalars(select(WebhookEvent).where(WebhookEvent.status == "pending").order_by(WebhookEvent.id).limit(limit)).all()
        return [(r.id, r.topic, r.resource_id) for r in rows]

def finish_webhook(event_id: int, *, error: str | None = None) -> None:
    with SessionLocal.begin() as session:
        row = session.get(WebhookEvent, event_id)
        if row is None:
            return
        row.attempts += 1
        row.last_error = error[:2000] if error else None
        if error and row.attempts < 10:
            row.status = "pending"
        else:
            row.status = "processed" if not error else "failed"
            row.processed_at = utcnow()


def save_report(report_key: str, report_date: str, file_path: str, sha256: str) -> int:
    with SessionLocal.begin() as session:
        existing = session.scalar(select(Report).where(Report.report_key == report_key))
        if existing:
            existing.file_path = file_path
            existing.sha256 = sha256
            existing.status = "ready"
            return existing.id
        row = Report(report_key=report_key, report_date=report_date, file_path=file_path, sha256=sha256, status="ready")
        session.add(row)
        session.flush()
        return row.id


def latest_report() -> Report | None:
    with SessionLocal() as session:
        row = session.scalar(select(Report).where(Report.status == "ready").order_by(Report.report_date.desc(), Report.id.desc()).limit(1))
        if row:
            session.expunge(row)
        return row


def get_user_id(telegram_id: int | str) -> int | None:
    with SessionLocal() as session:
        return session.scalar(select(User.id).where(User.telegram_id == str(telegram_id)))


def trial_state(user_id: int) -> str | None:
    with SessionLocal() as session:
        return session.scalar(select(TrialGrant.status).where(TrialGrant.user_id == user_id))


def get_trial_user_ids() -> list[str]:
    with SessionLocal() as session:
        return list(session.scalars(
            select(User.telegram_id).join(TrialGrant, TrialGrant.user_id == User.id)
            .where(TrialGrant.status == "pending")
        ).all())


def record_delivery(report_id: int, user_id: int, delivery_type: str, status: str, error: str | None = None) -> None:
    with SessionLocal.begin() as session:
        row = session.scalar(select(ReportDelivery).where(
            ReportDelivery.report_id == report_id,
            ReportDelivery.user_id == user_id,
            ReportDelivery.delivery_type == delivery_type,
        ).with_for_update())
        if row is None:
            row = ReportDelivery(report_id=report_id, user_id=user_id, delivery_type=delivery_type, status=status)
            session.add(row)
        row.status = status
        row.error = error[:2000] if error else None
        if status == "sent":
            row.sent_at = utcnow()


def active_subscriber_ids() -> list[tuple[int, str]]:
    now = utcnow()
    with SessionLocal() as session:
        rows = session.execute(
            select(User.id, User.telegram_id).join(Subscription, Subscription.user_id == User.id)
            .where(Subscription.status == "active", Subscription.ends_at > now)
            .distinct()
        ).all()
        return [(int(r[0]), str(r[1])) for r in rows]


def delivery_was_sent(report_id: int, user_id: int, delivery_type: str) -> bool:
    with SessionLocal() as session:
        return session.scalar(select(ReportDelivery.id).where(
            ReportDelivery.report_id == report_id,
            ReportDelivery.user_id == user_id,
            ReportDelivery.delivery_type == delivery_type,
            ReportDelivery.status == "sent",
        )) is not None


def reconcile_non_approved_payment(payment: dict) -> bool:
    """Registra devoluciones/contracargos de pagos ya acreditados sin borrar el historial."""
    payment_id = str(payment.get("id", ""))
    status = str(payment.get("status", "")).lower()
    if not payment_id or status not in {"refunded", "charged_back", "partially_refunded"}:
        return False
    with SessionLocal.begin() as session:
        row = session.scalar(select(Payment).where(Payment.provider_payment_id == payment_id).with_for_update())
        if row is None:
            return False
        if row.status == status:
            return False
        row.status = status
        subscriptions = session.scalars(select(Subscription).where(Subscription.source_payment_id == payment_id).with_for_update()).all()
        for subscription in subscriptions:
            subscription.status = "revoked"
        session.add(AuditEvent(user_id=row.user_id, event_type=f"payment_{status}", details=f"payment_id={payment_id}"))
        return True
