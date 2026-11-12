"""Pruebas offline de persistencia y ciclo de pagos; nunca llaman a Mercado Pago."""
import hashlib
import hmac
import importlib
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


class TestDatabasePaymentFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(self.tmp.name, "curu_test.db")
        import database
        self.db = importlib.reload(database)
        self.db.init_db()

    def tearDown(self):
        self.db.engine.dispose()
        if self.original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self.original_database_url
        importlib.reload(self.db)
        self.tmp.cleanup()
        sys.modules.pop("bot", None)

    def _crear_orden(self, amount=30000):
        user, created = self.db.register_user(
            "998877", username="prueba", first_name="Usuario"
        )
        self.assertTrue(created)
        self.db.create_payment_intent("998877", "orden-curu-001", amount)
        self.db.attach_preference("orden-curu-001", "pref-001")
        return user

    def _pago(self, **changes):
        payload = {
            "id": 7654321,
            "external_reference": "orden-curu-001",
            "status": "approved",
            "transaction_amount": 30000,
            "currency_id": "COP",
        }
        payload.update(changes)
        return payload

    def test_pago_aprobado_activa_membresia_y_es_idempotente(self):
        self._crear_orden()
        applied, telegram_id = self.db.process_approved_payment(self._pago(), 30)
        self.assertTrue(applied)
        self.assertEqual(telegram_id, "998877")
        self.assertTrue(self.db.is_subscription_active("998877"))

        applied_again, telegram_again = self.db.process_approved_payment(
            self._pago(id=7654322), 30
        )
        self.assertFalse(applied_again)
        self.assertIsNone(telegram_again)
        with self.db.engine.connect() as conn:
            subscriptions = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM subscriptions"
            ).scalar_one()
            duplicate_status = conn.exec_driver_sql(
                "SELECT status FROM payments WHERE provider_payment_id = '7654322'"
            ).scalar_one()
        self.assertEqual(subscriptions, 1)
        self.assertEqual(duplicate_status, "duplicate_approved")

    def test_rechaza_monto_o_moneda_distintos_de_la_orden(self):
        self._crear_orden()
        with self.assertRaisesRegex(ValueError, "Monto o moneda"):
            self.db.process_approved_payment(self._pago(transaction_amount=29999), 30)
        with self.assertRaisesRegex(ValueError, "Monto o moneda"):
            self.db.process_approved_payment(self._pago(currency_id="USD"), 30)
        self.assertFalse(self.db.is_subscription_active("998877"))

    def test_orden_usd_valida_importe_y_moneda_de_forma_independiente(self):
        self.db.create_payment_intent(
            "998877", "orden-usd-001", amount="9.99", currency="USD"
        )
        payment = {
            "id": "usd-payment-001",
            "external_reference": "orden-usd-001",
            "status": "approved",
            "transaction_amount": "9.99",
            "currency_id": "USD",
        }
        applied, telegram_id = self.db.process_approved_payment(payment, 30)
        self.assertTrue(applied)
        self.assertEqual(telegram_id, "998877")
        with self.db.engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT amount, amount_cop, currency FROM payments WHERE provider_payment_id = 'usd-payment-001'"
            ).one()
        self.assertEqual(str(row[0]), "9.990000")
        self.assertEqual(row[1], 0)
        self.assertEqual(row[2], "USD")

    def test_orden_usd_rechaza_pago_en_cop_o_importe_diferente(self):
        self.db.create_payment_intent(
            "998877", "orden-usd-002", amount="9.99", currency="USD"
        )
        base = {
            "id": "usd-payment-002",
            "external_reference": "orden-usd-002",
            "status": "approved",
            "transaction_amount": "9.99",
            "currency_id": "USD",
        }
        with self.assertRaisesRegex(ValueError, "Monto o moneda"):
            self.db.process_approved_payment({**base, "currency_id": "COP"}, 30)
        with self.assertRaisesRegex(ValueError, "Monto o moneda"):
            self.db.process_approved_payment({**base, "transaction_amount": "10.00"}, 30)
        self.assertFalse(self.db.is_subscription_active("998877"))

    def test_pago_reembolsado_revoca_su_periodo_y_conserva_historial(self):
        self._crear_orden()
        self.db.process_approved_payment(self._pago(), 30)
        changed = self.db.reconcile_non_approved_payment(
            {"id": "7654321", "status": "refunded"}
        )
        self.assertTrue(changed)
        self.assertFalse(self.db.is_subscription_active("998877"))
        self.assertFalse(self.db.reconcile_non_approved_payment(
            {"id": "7654321", "status": "refunded"}
        ))

    def test_webhooks_duplicados_no_se_encolan_dos_veces(self):
        first = self.db.enqueue_webhook("payment:7654321:approved", "payment", "7654321")
        duplicate = self.db.enqueue_webhook("payment:7654321:approved", "payment", "7654321")
        self.assertTrue(first)
        self.assertFalse(duplicate)
        pending = self.db.pending_webhooks()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0][1:], ("payment", "7654321"))

    def test_webhook_http_exige_firma_valida_antes_de_encolar(self):
        secret = "secreto-de-prueba"
        request_id = "req-curu-001"
        data_id = "12345"
        timestamp = str(int(time.time()))
        manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
        digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        signature = f"ts={timestamp},v1={digest}"

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "123456:token-falso-de-prueba",
            "MERCADOPAGO_WEBHOOK_SECRET": secret,
        }):
            import bot
            with patch.object(bot.db, "enqueue_webhook", return_value=True) as enqueue:
                client = bot.app.test_client()
                good = client.post(
                    f"/webhook-pago?data.id={data_id}&type=payment",
                    json={"type": "payment", "data": {"id": data_id}},
                    headers={"x-signature": signature, "x-request-id": request_id},
                )
                self.assertEqual(good.status_code, 200)
                enqueue.assert_called_once()

                enqueue.reset_mock()
                bad = client.post(
                    f"/webhook-pago?data.id={data_id}&type=payment",
                    json={"type": "payment", "data": {"id": data_id}},
                    headers={"x-signature": "ts=1,v1=incorrecta", "x-request-id": request_id},
                )
                self.assertEqual(bad.status_code, 401)
                enqueue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
