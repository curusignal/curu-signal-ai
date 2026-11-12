"""Integración: las 500 entradas se filtran cuantitativamente y solo el Top 10 usa IA."""
import os
import tempfile
import unittest
from unittest.mock import patch

import orquestador


class TestOrquestadorTop10(unittest.TestCase):
    def test_solo_los_diez_seleccionados_llegan_a_ia(self):
        tickers = [f"T{i:03d}" for i in range(500)]
        historiales = {ticker: object() for ticker in tickers}
        llamadas_ia = []
        pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        pdf.write(b"PDF de prueba CURU")
        pdf.close()
        self.addCleanup(lambda: os.path.exists(pdf.name) and os.remove(pdf.name))

        def metricas(ticker, _historial):
            numero = int(ticker[1:])
            return {
                "activo": ticker,
                "fecha_datos": "2026-11-10",
                "volumen_promedio_usd_20d": 50_000_000,
                "volatilidad_realizada_20d_anualizada_pct": float(numero),
                "atr_pct": float(numero) / 100,
            }

        def ia(activo, _micro, _macro):
            llamadas_ia.append(activo["activo"])
            return "IA simulada"

        with patch.dict(os.environ, {
            "CURU_MIN_COVERAGE": "0.70",
            "CURU_MIN_DOLLAR_VOLUME": "10000000",
        }):
            with patch.object(orquestador, "init_db"), \
                 patch.object(orquestador, "limpiar_residuo_imagenes"), \
                 patch.object(orquestador, "obtener_todos_los_tickers_sp500", return_value=tickers), \
                 patch.object(orquestador, "descargar_historiales", return_value=historiales), \
                 patch.object(orquestador, "calcular_indicadores_desde_historial", side_effect=metricas), \
                 patch.object(orquestador, "_fecha_de_datos_valida", return_value=True), \
                 patch.object(orquestador, "extraer_noticias_macro", return_value=[]), \
                 patch.object(orquestador, "extraer_noticias_micro", return_value=[]), \
                 patch.object(orquestador, "analizar_activo_con_ia", side_effect=ia), \
                 patch.object(orquestador, "generar_grafico_avanzado_activo"), \
                 patch.object(orquestador, "fabricar_pdf_comercial", return_value=pdf.name), \
                 patch.object(orquestador, "save_report"):
                resultado = orquestador.ejecutar_sistema_premium_automatizado()

        esperados = [f"T{i:03d}" for i in range(499, 489, -1)]
        self.assertEqual(resultado, pdf.name)
        self.assertEqual(len(llamadas_ia), 10)
        self.assertEqual(llamadas_ia, esperados)


if __name__ == "__main__":
    unittest.main()
