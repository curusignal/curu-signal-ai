"""Prueba sintética local; no consulta Yahoo Finance ni APIs externas."""
import unittest
import numpy as np
import pandas as pd

from metricas import calcular_indicadores_desde_historial, _wilder_rma


class TestMotorCuru(unittest.TestCase):
    def test_wilder_rma_usa_sma_como_semilla(self):
        values = pd.Series(range(1, 16), dtype=float)
        rma = _wilder_rma(values, 14)
        self.assertAlmostEqual(rma.iloc[13], 7.5, places=8)
        self.assertAlmostEqual(rma.iloc[14], (7.5 * 13 + 15) / 14, places=8)

    def test_calcula_metricas_y_score_acotado(self):
        rng = np.random.default_rng(42)
        n = 320
        retornos = rng.normal(0.0004, 0.018, n)
        close = 100 * np.exp(np.cumsum(retornos))
        hist = pd.DataFrame({
            "Open": close,
            "High": close * 1.015,
            "Low": close * 0.985,
            "Close": close,
            "Volume": rng.integers(1_000_000, 2_000_000, n),
        }, index=pd.bdate_range("2025-08-01", periods=n))

        resultado = calcular_indicadores_desde_historial("TEST", hist)
        self.assertIsNotNone(resultado)
        self.assertGreaterEqual(resultado["score_tecnico"], -1)
        self.assertLessEqual(resultado["score_tecnico"], 1)
        self.assertIn(resultado["sesgo"], {"ALCISTA", "BAJISTA", "NEUTRO"})
        self.assertGreater(resultado["atr_pct"], 0)
        self.assertGreater(resultado["volatilidad_realizada_20d_anualizada_pct"], 0)
        self.assertNotIn("probabilidad_acierto", resultado)


if __name__ == "__main__":
    unittest.main()
