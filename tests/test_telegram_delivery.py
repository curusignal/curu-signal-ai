"""Pruebas de la ruta de entrega PDF a Telegram con el cliente HTTP simulado."""
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestTelegramDelivery(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "123456:token-falso-de-prueba",
            "DATABASE_URL": "sqlite:///./telegram_delivery_test.db",
        })
        self.env.start()
        sys.modules.pop("bot", None)
        import bot
        self.bot_module = bot

    def tearDown(self):
        self.bot_module.db.engine.dispose()
        sys.modules.pop("bot", None)
        self.env.stop()
        if os.path.exists("telegram_delivery_test.db"):
            os.remove("telegram_delivery_test.db")

    def test_entrega_pdf_registra_pendiente_y_enviado(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as pdf:
            pdf.write(b"%PDF-1.4 CURU TEST")
            pdf.flush()
            report = SimpleNamespace(
                id=41, report_date="2026-11-11", file_path=pdf.name
            )
            with patch.object(self.bot_module, "_get_report", return_value=report), \
                 patch.object(self.bot_module.db, "delivery_was_sent", return_value=False), \
                 patch.object(self.bot_module.db, "record_delivery") as record, \
                 patch.object(self.bot_module.bot, "send_document") as send:
                delivered = self.bot_module._send_current_report("998877", 7)

        self.assertTrue(delivered)
        send.assert_called_once()
        self.assertEqual(
            [call.args[3] for call in record.call_args_list],
            ["pending", "sent"],
        )

    def test_no_reenvia_un_reporte_ya_entregado(self):
        with patch.object(self.bot_module, "_get_report") as get_report, \
             patch.object(self.bot_module.db, "delivery_was_sent", return_value=True), \
             patch.object(self.bot_module.bot, "send_document") as send:
            result = self.bot_module._send_current_report("998877", 7)

        self.assertFalse(result)
        get_report.assert_called_once()
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
