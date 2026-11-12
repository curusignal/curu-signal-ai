"""Pruebas offline de la capa IA; no consumen API ni tokens."""
import json
import os
import unittest
from unittest.mock import patch

import cerebro_ia

DATOS = {
    "activo": "AAPL", "precio_cierre": 270.0, "rsi": 58.2,
    "sma_20": 265.0, "sma_50": 260.0, "sma_200": 240.0,
    "macd_linea": 2.1, "macd_senal": 1.7, "macd_histograma": 0.4,
    "bollinger_inferior": 250.0, "bollinger_media": 265.0,
    "bollinger_superior": 280.0, "posicion_bollinger": 0.66,
    "atr_riesgo_diario": 5.0, "atr_pct": 1.85,
    "volatilidad_realizada_20d_anualizada_pct": 24.0,
    "volumen_promedio_usd_20d": 2_000_000_000,
    "score_tecnico": 0.42, "intensidad_sesgo": 42.0,
    "sesgo": "ALCISTA", "riesgo_volatilidad": "CONTENIDO",
}
NOTICIAS = [{"titulo": "Resultados trimestrales", "fuente": "Fuente de prueba",
             "fecha": "2026-11-10", "url": "https://example.com/noticia"}]


class TestCerebroIA(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GROQ_API_KEY": "", "OPENROUTER_API_KEY": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_sin_credenciales_marca_respaldo(self):
        r = cerebro_ia.analizar_activo_con_ia_detallado(DATOS, [], [])
        self.assertEqual(r["estado_ia"], "no_disponible")
        self.assertIn("IA NO DISPONIBLE", r["texto"])
        self.assertIn("no es probabilidad", r["texto"])

    def test_respaldo_declara_datos_fundamentales_ausentes(self):
        texto = cerebro_ia.analizar_activo_con_ia(DATOS, [], [])
        self.assertIn("fundamentales", texto.lower())
        self.assertIn("SMA 200", texto)

    def test_json_valido_y_solo_referencias_existentes(self):
        payload = {
            "lectura_general": "Estructura técnica positiva, no concluyente.",
            "factores_favorables": ["Precio sobre SMA 50 y SMA 200."],
            "factores_contrarios": ["Hay volatilidad."], "riesgos": ["No hay causalidad probada."],
            "noticias_referenciadas": ["C1", "C99"],
            "informacion_faltante": ["Fundamentales no disponibles."],
            "conclusion": "Limitar la lectura a los datos suministrados.",
        }
        class FakeCompletions:
            def create(self, **kwargs):
                class Message:
                    content = json.dumps(payload)
                class Choice:
                    message = Message()
                class Response:
                    choices = [Choice()]
                return Response()
        class FakeClient:
            def __init__(self, **kwargs):
                self.chat = type("Chat", (), {"completions": FakeCompletions()})()
        with patch.dict(os.environ, {"GROQ_API_KEY": "test", "GROQ_MODEL": "test-model"}):
            with patch.object(cerebro_ia, "OpenAI", FakeClient):
                r = cerebro_ia.analizar_activo_con_ia_detallado(DATOS, NOTICIAS, [])
        self.assertEqual(r["estado_ia"], "completado")
        self.assertEqual(r["noticias_referenciadas"], ["C1"])
        self.assertIn("Fuente de prueba", r["texto"])
        self.assertNotIn("C99", r["texto"])

    def test_json_invalido_no_se_presenta_como_ia(self):
        class FakeCompletions:
            def create(self, **kwargs):
                class Message:
                    content = "respuesta inválida"
                class Choice:
                    message = Message()
                class Response:
                    choices = [Choice()]
                return Response()
        class FakeClient:
            def __init__(self, **kwargs):
                self.chat = type("Chat", (), {"completions": FakeCompletions()})()
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}):
            with patch.object(cerebro_ia, "OpenAI", FakeClient):
                r = cerebro_ia.analizar_activo_con_ia_detallado(DATOS, [], [])
        self.assertEqual(r["estado_ia"], "error")
        self.assertIn("IA NO DISPONIBLE", r["texto"])

    def test_interfaz_compatible_devuelve_string(self):
        self.assertIsInstance(cerebro_ia.analizar_activo_con_ia(DATOS, [], []), str)


if __name__ == "__main__":
    unittest.main()
