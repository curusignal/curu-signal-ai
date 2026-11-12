"""Prueba la cascada Groq -> OpenRouter sin consumir tokens ni llamar servicios."""
import json
import os
import unittest
from unittest.mock import patch

import cerebro_ia


DATOS = {
    "activo": "MSFT", "fecha_datos": "2026-11-11",
    "precio_cierre": 500.0, "rsi": 57.0, "sma_20": 495.0,
    "sma_50": 480.0, "sma_200": 430.0, "macd_linea": 2.2,
    "macd_senal": 1.8, "macd_histograma": 0.4,
    "bollinger_inferior": 470.0, "bollinger_media": 495.0,
    "bollinger_superior": 520.0, "posicion_bollinger": 0.6,
    "atr_riesgo_diario": 8.0, "atr_pct": 1.6,
    "volatilidad_realizada_20d_anualizada_pct": 22.0,
    "volumen_promedio_usd_20d": 3_000_000_000,
    "score_tecnico": 0.35, "intensidad_sesgo": 35.0,
    "sesgo": "ALCISTA", "riesgo_volatilidad": "CONTENIDO",
}
RESPUESTA = {
    "lectura_general": "La estructura técnica es positiva, pero no concluyente.",
    "factores_favorables": ["Precio sobre SMA 50 y SMA 200."],
    "factores_contrarios": ["El impulso puede perder fuerza."],
    "riesgos": ["La volatilidad puede cambiar."],
    "noticias_referenciadas": ["C1"],
    "informacion_faltante": ["No hay fundamentales estructurados."],
    "conclusion": "Mantener una lectura descriptiva y prudente.",
}


class TestCascadaIA(unittest.TestCase):
    def test_si_groq_falla_openrouter_recibe_metricas_y_responde(self):
        llamadas = []

        class FakeCompletions:
            def __init__(self, proveedor):
                self.proveedor = proveedor

            def create(self, **kwargs):
                llamadas.append((self.proveedor, kwargs))
                if self.proveedor == "Groq":
                    raise TimeoutError("fallo simulado de Groq")
                message = type("Message", (), {"content": json.dumps(RESPUESTA)})()
                choice = type("Choice", (), {"message": message})()
                return type("Response", (), {"choices": [choice]})()

        class FakeClient:
            def __init__(self, *, base_url, **kwargs):
                proveedor = "Groq" if "groq.com" in base_url else "OpenRouter"
                self.chat = type(
                    "Chat", (), {"completions": FakeCompletions(proveedor)}
                )()

        with patch.dict(os.environ, {
            "GROQ_API_KEY": "groq-test-key",
            "GROQ_MODEL": "modelo-groq-test",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "OPENROUTER_MODEL": "modelo-openrouter-test",
        }):
            with patch.object(cerebro_ia, "OpenAI", FakeClient):
                resultado = cerebro_ia.analizar_activo_con_ia_detallado(
                    DATOS,
                    [{"titulo": "Resultados de prueba", "fuente": "Fuente test",
                      "fecha": "2026-11-11", "url": "https://example.com"}],
                    [],
                )

        self.assertEqual(resultado["estado_ia"], "completado")
        self.assertEqual(resultado["proveedor"], "OpenRouter")
        self.assertEqual([x[0] for x in llamadas], ["Groq", "OpenRouter"])
        prompt = llamadas[1][1]["messages"][1]["content"]
        self.assertIn('"volatilidad_realizada_20d_anualizada_pct": 22.0', prompt)
        self.assertIn("Resultados de prueba", prompt)
        self.assertIn("no es una probabilidad", resultado["texto"])


if __name__ == "__main__":
    unittest.main()
