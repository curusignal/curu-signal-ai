"""Pruebas del adaptador de datos por lotes con respuesta Yahoo sintética."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import yfinance

from metricas import descargar_historiales


class TestDescargaHistoriales(unittest.TestCase):
    def test_separa_correctamente_columnas_multiactivo(self):
        fechas = pd.bdate_range("2026-01-01", periods=3)
        tickers = ["AAA", "BBB"]
        campos = ["Open", "High", "Low", "Close", "Volume"]
        columnas = pd.MultiIndex.from_product([tickers, campos])
        datos = np.array([
            [10, 11, 9, 10.5, 1000, 20, 21, 19, 20.5, 2000],
            [11, 12, 10, 11.5, 1100, 21, 22, 20, 21.5, 2100],
            [12, 13, 11, 12.5, 1200, 22, 23, 21, 22.5, 2200],
        ])
        historico = pd.DataFrame(datos, index=fechas, columns=columnas)

        with patch.object(yfinance, "download", return_value=historico) as download:
            resultado = descargar_historiales(
                ["AAA", "BBB", "AAA"], tamano_lote=40, reintentos=0
            )

        self.assertEqual(set(resultado), {"AAA", "BBB"})
        self.assertEqual(list(resultado["AAA"].columns), campos)
        self.assertEqual(list(resultado["BBB"].columns), campos)
        self.assertEqual(float(resultado["AAA"]["Close"].iloc[-1]), 12.5)
        self.assertEqual(float(resultado["BBB"]["Close"].iloc[-1]), 22.5)
        self.assertEqual(download.call_count, 1)
        self.assertEqual(download.call_args.kwargs["tickers"], ["AAA", "BBB"])


if __name__ == "__main__":
    unittest.main()
