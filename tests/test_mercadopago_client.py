"""Pruebas offline del cliente Mercado Pago; todas las llamadas HTTP están simuladas."""
import os
import unittest
from unittest.mock import patch

import pagos


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class TestMercadoPagoClient(unittest.TestCase):
    def test_crea_preferencia_checkout_pro_con_cop_y_webhook_https(self):
        response = FakeResponse({
            "id": "pref-prueba-123",
            "init_point": "https://www.mercadopago.com.co/checkout/v1/redirect?pref_id=123",
        })
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-ACCESS-TOKEN",
            "PUBLIC_BASE_URL": "https://curu.example.com",
        }):
            with patch.object(pagos.requests, "post", return_value=response) as post:
                url, preference_id = pagos.crear_preferencia(
                    external_reference="orden-001", amount_cop=30000, duration_days=30
                )

        self.assertEqual(preference_id, "pref-prueba-123")
        self.assertTrue(url.startswith("https://"))
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.mercadopago.com/checkout/preferences")
        self.assertEqual(kwargs["json"]["items"][0]["currency_id"], "COP")
        self.assertEqual(kwargs["json"]["items"][0]["unit_price"], 30000.0)
        self.assertEqual(kwargs["json"]["external_reference"], "orden-001")
        self.assertEqual(kwargs["json"]["notification_url"], "https://curu.example.com/webhook-pago")
        self.assertEqual(kwargs["json"]["back_urls"]["success"], "https://curu.example.com/pago/resultado?estado=exitoso")
        self.assertTrue(kwargs["headers"]["X-Idempotency-Key"])

    def test_crea_preferencia_con_moneda_usd_y_monto_decimal(self):
        response = FakeResponse({
            "id": "pref-usd-456",
            "init_point": "https://www.mercadopago.com/checkout/v1/redirect?pref_id=456",
        })
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-ACCESS-TOKEN",
            "PUBLIC_BASE_URL": "https://curu.example.com",
        }):
            with patch.object(pagos.requests, "post", return_value=response) as post:
                pagos.crear_preferencia(
                    external_reference="orden-usd-001",
                    amount="9.99",
                    currency="USD",
                    duration_days=30,
                )
        item = post.call_args.kwargs["json"]["items"][0]
        self.assertEqual(item["currency_id"], "USD")
        self.assertEqual(item["unit_price"], 9.99)
        self.assertEqual(post.call_args.kwargs["json"]["metadata"]["expected_currency"], "USD")

    def test_rechaza_importe_no_positivo_o_moneda_mal_formada(self):
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-ACCESS-TOKEN",
            "PUBLIC_BASE_URL": "https://curu.example.com",
        }):
            with self.assertRaisesRegex(ValueError, "Importe o moneda"):
                pagos.crear_preferencia(
                    external_reference="orden-001", amount="0", currency="COP"
                )
            with self.assertRaisesRegex(ValueError, "Importe o moneda"):
                pagos.crear_preferencia(
                    external_reference="orden-001", amount="10", currency="US"
                )

    def test_no_crea_preferencia_sin_token_o_url_https(self):
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "",
            "PUBLIC_BASE_URL": "https://curu.example.com",
        }):
            with self.assertRaisesRegex(RuntimeError, "MERCADOPAGO_ACCESS_TOKEN"):
                pagos.crear_preferencia(
                    external_reference="orden-001", amount_cop=30000
                )

        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-ACCESS-TOKEN",
            "PUBLIC_BASE_URL": "http://curu.example.com",
        }):
            with self.assertRaisesRegex(RuntimeError, "HTTPS"):
                pagos.crear_preferencia(
                    external_reference="orden-001", amount_cop=30000
                )

    def test_consulta_pago_con_token_bearer(self):
        response = FakeResponse({"id": 123, "status": "approved"})
        with patch.dict(os.environ, {
            "MERCADOPAGO_ACCESS_TOKEN": "TEST-ACCESS-TOKEN",
            "PUBLIC_BASE_URL": "https://curu.example.com",
        }):
            with patch.object(pagos.requests, "get", return_value=response) as get:
                payment = pagos.obtener_pago("123")

        self.assertEqual(payment["status"], "approved")
        self.assertEqual(get.call_args.args[0], "https://api.mercadopago.com/v1/payments/123")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer TEST-ACCESS-TOKEN")


if __name__ == "__main__":
    unittest.main()
