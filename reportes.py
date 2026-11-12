"""Gráficos técnicos a partir del mismo historial usado por el motor."""
import os
import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from metricas import _wilder_rma

log = logging.getLogger("curu.reportes")


def obtener_carpeta_temporal():
    carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_graficos")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _indicadores_grafico(datos):
    d = datos.copy()
    d.columns = [str(c).title() for c in d.columns]
    close = pd.to_numeric(d["Close"], errors="coerce")
    d["BB_MID"] = close.rolling(20).mean()
    std = close.rolling(20).std(ddof=0)
    d["BB_UPPER"] = d["BB_MID"] + 2 * std
    d["BB_LOWER"] = d["BB_MID"] - 2 * std
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    d["MACD"] = ema12 - ema26
    d["MACD_SIGNAL"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["MACD_HIST"] = d["MACD"] - d["MACD_SIGNAL"]
    delta = close.diff()
    gain = _wilder_rma(delta.clip(lower=0), 14)
    loss = _wilder_rma(-delta.clip(upper=0), 14)
    rs = gain / loss.replace(0, np.nan)
    d["RSI"] = 100 - 100 / (1 + rs)
    d.loc[(loss == 0) & (gain > 0), "RSI"] = 100
    d.loc[(gain == 0) & (loss > 0), "RSI"] = 0
    return d.dropna(subset=["Close"]).iloc[-90:]


def generar_grafico_avanzado_activo(ticker_nombre, valor_rsi=None, historial=None):
    try:
        if historial is None:
                        historial = yf.download(
                ticker_nombre, period="6mo", interval="1d",
                auto_adjust=True, progress=False, threads=False
            )
        if historial is None or historial.empty:
            return None, None
        if isinstance(historial.columns, pd.MultiIndex):
            # Compatibilidad con descarga por lotes de yfinance.
            for level in range(historial.columns.nlevels):
                if ticker_nombre in historial.columns.get_level_values(level):
                    historial = historial.xs(ticker_nombre, axis=1, level=level)
                    break

        d = _indicadores_grafico(historial)
        if len(d) < 30:
            return None, None

        carpeta = obtener_carpeta_temporal()
        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(8, 5), sharex=True,
            gridspec_kw={"height_ratios": [2.5, 1]}
        )
        ax1.plot(d.index, d["Close"], label="Cierre", linewidth=1.8)
        ax1.plot(d.index, d["BB_MID"], label="Bollinger media", linestyle="--", linewidth=1)
        ax1.plot(d.index, d["BB_UPPER"], label="Bollinger superior", linewidth=.8)
        ax1.plot(d.index, d["BB_LOWER"], label="Bollinger inferior", linewidth=.8)
        ax1.fill_between(d.index, d["BB_LOWER"], d["BB_UPPER"], alpha=.08)
        ax1.set_title(f"{ticker_nombre} · Precio y Bandas de Bollinger")
        ax1.legend(fontsize=7, loc="best")
        ax1.grid(alpha=.2)

        ax2.bar(d.index, d["MACD_HIST"], width=.7)
        ax2.axhline(0, linewidth=.7)
        ax2.set_title("Histograma MACD")
        ax2.grid(alpha=.2)
        fig.tight_layout()
        panel = os.path.join(carpeta, f"panel_tecnico_{ticker_nombre}.png")
        fig.savefig(panel, dpi=145)
        plt.close(fig)

        rsi_actual = float(d["RSI"].iloc[-1]) if valor_rsi is None else float(valor_rsi)
        fig2, ax = plt.subplots(figsize=(8, 1.35))
        ax.axhspan(0, 30, alpha=.12)
        ax.axhspan(70, 100, alpha=.12)
        ax.plot(d.index, d["RSI"], linewidth=1.4)
        ax.axhline(70, linestyle="--", linewidth=.7)
        ax.axhline(50, linestyle=":", linewidth=.7)
        ax.axhline(30, linestyle="--", linewidth=.7)
        ax.set_ylim(0, 100)
        ax.set_title(f"RSI (14): {rsi_actual:.1f}", fontsize=9)
        ax.grid(alpha=.2)
        fig2.tight_layout()
        rsi_path = os.path.join(carpeta, f"grafico_rsi_{ticker_nombre}.png")
        fig2.savefig(rsi_path, dpi=145)
        plt.close(fig2)
        return panel, rsi_path
    except Exception as exc:
        log.warning("No se pudo generar gráfico para %s: %s", ticker_nombre, exc)
        return None, None
