"""Importa usuarios.json legado sin borrar ni reemplazar registros.

Uso: python migrar_usuarios_legacy.py /ruta/usuarios.json
El script conserva fechas de vencimiento y crea un registro histórico de origen legacy.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, date, time, timezone
from pathlib import Path

import database as db
from sqlalchemy import select


def main(path_text: str) -> None:
    path = Path(path_text)
    if not path.is_file():
        raise SystemExit(f"No existe el archivo: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Formato legado inválido: se esperaba un objeto {telegram_id: YYYY-MM-DD}")
    db.init_db()
    imported = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    with db.SessionLocal.begin() as session:
        for telegram_id, expiry_text in data.items():
            expiry_date = date.fromisoformat(str(expiry_text))
            ends_at = datetime.combine(expiry_date, time.max, tzinfo=timezone.utc)
            user = session.scalar(select(db.User).where(db.User.telegram_id == str(telegram_id)))
            if user is None:
                user = db.User(telegram_id=str(telegram_id))
                session.add(user)
                session.flush()
            source = f"legacy-import-{telegram_id}-{expiry_date.isoformat()}"
            existing = session.scalar(select(db.Subscription.id).where(db.Subscription.source_payment_id == source))
            if existing:
                skipped += 1
                continue
            session.add(db.Subscription(
                user_id=user.id,
                starts_at=now,
                ends_at=ends_at,
                status="active" if ends_at > now else "expired",
                source_payment_id=source,
            ))
            session.add(db.AuditEvent(user_id=user.id, event_type="legacy_subscription_imported", details=f"expires={expiry_date.isoformat()}"))
            imported += 1
    print(f"Importación terminada. Nuevos registros: {imported}; ya existentes: {skipped}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python migrar_usuarios_legacy.py /ruta/usuarios.json")
    main(sys.argv[1])
