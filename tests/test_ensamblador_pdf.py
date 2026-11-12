"""Pruebas de generación real del PDF comercial, sin servicios externos."""
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from ensamblador import fabricar_pdf_comercial


class TestEnsambladorPDF(unittest.TestCase):
    def test_genera_pdf_legible_con_un_activo(self):
        activo = {
            "activo": "AAPL", "sesgo": "ALCISTA", "score_tecnico": 0.42,
            "intensidad_sesgo": 42.0, "precio_cierre": 270.0,
            "fecha_datos": "2026-11-10", "rsi": 58.2,
            "sma_50": 260.0, "sma_200": 240.0, "macd_histograma": 0.4,
            "bollinger_inferior": 250.0, "bollinger_superior": 280.0,
            "atr_riesgo_diario": 5.0, "atr_pct": 1.85,
            "riesgo_volatilidad": "CONTENIDO",
            "volatilidad_realizada_20d_anualizada_pct": 24.0,
            "volumen_promedio_usd_20d": 2_000_000_000,
            "veredicto_ia": "ESTADO: IA NO DISPONIBLE. Respaldo de prueba.",
            "noticias_micro": [],
            "universo_total": 500, "cobertura_datos": 0.95,
        }
        with tempfile.TemporaryDirectory() as carpeta:
            with patch.dict(os.environ, {"REPORTS_DIR": carpeta}):
                ruta = fabricar_pdf_comercial(
                    [activo], fecha_generacion=datetime(2026, 11, 12, 4, 0)
                )
            self.assertTrue(os.path.isfile(ruta))
            with open(ruta, "rb") as archivo:
                contenido = archivo.read()
            self.assertTrue(contenido.startswith(b"%PDF-"))
            self.assertGreater(len(contenido), 2_000)

    def test_rechaza_informe_sin_activos(self):
        with self.assertRaises(ValueError):
            fabricar_pdf_comercial([])


if __name__ == "__main__":
    unittest.main()
