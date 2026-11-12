"""
Motor cuantitativo de CURU Signal AI.

Calcula indicadores sobre velas diarias ajustadas y separa:
- selección por volatilidad/liquidez;
- sesgo direccional técnico;
- rango de riesgo (ATR).

IMPORTANTE: score_tecnico/confluencia no es una probabilidad de acierto.
"""
from __future__ import annotations

import logging
import math
import os
import time
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

log = logging.getLogger("curu.metricas")


def _extraer_ticker(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normaliza columnas de yfinance (MultiIndex o columnas simples)."""
    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        for level in range(data.columns.nlevels):
            values = data.columns.get_level_values(level)
            if ticker in values:
                try:
                    out = data.xs(ticker, axis=1, level=level, drop_level=True)
                    if isinstance(out.columns, pd.MultiIndex):
                        out.columns = out.columns.get_level_values(-1)
                    return out
                except Exception:
                    pass
        return pd.DataFrame()

    return data.copy()


def descargar_historiales(
    tickers: Iterable[str],
    periodo: str = "18mo",
    tamano_lote: int = 40,
    reintentos: int = 2,
) -> Dict[str, pd.DataFrame]:
    """
    Descarga el universo por lotes para reducir las peticiones individuales.
    YF_PROXY es opcional y debe configurarse como variable de entorno si se usa.
    """
    tickers = list(dict.fromkeys(t.strip() for t in tickers if t and t.strip()))
    resultados: Dict[str, pd.DataFrame] = {}
    proxy = os.getenv("YF_PROXY") or None

    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Falta instalar yfinance para descargar datos de mercado") from exc

    for inicio in range(0, len(tickers), tamano_lote):
        lote = tickers[inicio:inicio + tamano_lote]
        descargado = None

        for intento in range(reintentos + 1):
            try:
                descargado = yf.download(
                    tickers=lote,
                    period=periodo,
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                    group_by="ticker",
                    threads=5,
                    progress=False,
                    timeout=35,
                    proxy=proxy,
                )
                if descargado is not None and not descargado.empty:
                    break
            except Exception as exc:
                log.warning("Fallo descargando lote %s (intento %s): %s",
                            inicio // tamano_lote + 1, intento + 1, exc)
            if intento < reintentos:
                time.sleep(3 * (intento + 1))

        if descargado is None or descargado.empty:
            log.error("Lote sin datos: %s", ", ".join(lote))
            continue

        for ticker in lote:
            hist = _extraer_ticker(descargado, ticker)
            if hist.empty:
                continue
            hist.columns = [str(c).title() for c in hist.columns]
            columnas = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in hist.columns]
            if "Close" in columnas:
                resultados[ticker] = hist[columnas].dropna(subset=["Close"]).copy()

        log.info("Lote %s/%s: %s de %s activos con datos",
                 inicio // tamano_lote + 1,
                 math.ceil(len(tickers) / tamano_lote),
                 sum(1 for t in lote if t in resultados), len(lote))

    return resultados


def _wilder_rma(values: pd.Series, length: int) -> pd.Series:
    """Media móvil suavizada de Wilder, inicializada con SMA de las primeras N observaciones."""
    arr = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(arr), np.nan, dtype=float)
    valid = np.flatnonzero(np.isfinite(arr))
    if len(valid) < length:
        return pd.Series(out, index=values.index)
    first = valid[0]
    seed_end = first + length
    if seed_end > len(arr) or not np.isfinite(arr[first:seed_end]).all():
        # Reiniciar el bloque inicial si hay huecos internos.
        for start in range(len(arr) - length + 1):
            if np.isfinite(arr[start:start + length]).all():
                first = start
                seed_end = start + length
                break
        else:
            return pd.Series(out, index=values.index)
    out[seed_end - 1] = float(np.mean(arr[first:seed_end]))
    for i in range(seed_end, len(arr)):
        if np.isfinite(arr[i]) and np.isfinite(out[i - 1]):
            out[i] = (out[i - 1] * (length - 1) + arr[i]) / length
    return pd.Series(out, index=values.index)


def _serie_indicadores(hist: pd.DataFrame) -> pd.DataFrame:
    d = hist.copy()
    d.columns = [str(c).title() for c in d.columns]
    requeridas = {"High", "Low", "Close"}
    if not requeridas.issubset(d.columns):
        raise ValueError(f"Faltan columnas OHLC: {requeridas - set(d.columns)}")

    for c in ("High", "Low", "Close", "Volume"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["High", "Low", "Close"]).sort_index()
    d = d[~d.index.duplicated(keep="last")]

    close, high, low = d["Close"], d["High"], d["Low"]

    # RSI de Wilder (14)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _wilder_rma(gain, 14)
    avg_loss = _wilder_rma(loss, 14)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    d["RSI_14"] = 100 - (100 / (1 + rs))
    d.loc[(avg_loss == 0) & (avg_gain > 0), "RSI_14"] = 100
    d.loc[(avg_gain == 0) & (avg_loss > 0), "RSI_14"] = 0
    d.loc[(avg_gain == 0) & (avg_loss == 0), "RSI_14"] = 50

    d["SMA_20"] = close.rolling(20, min_periods=20).mean()
    d["SMA_50"] = close.rolling(50, min_periods=50).mean()
    d["SMA_200"] = close.rolling(200, min_periods=200).mean()

    ema12 = close.ewm(span=12, adjust=False, min_periods=26).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    d["MACD"] = ema12 - ema26
    d["MACD_SIGNAL"] = d["MACD"].ewm(span=9, adjust=False, min_periods=9).mean()
    d["MACD_HIST"] = d["MACD"] - d["MACD_SIGNAL"]

    std20 = close.rolling(20, min_periods=20).std(ddof=0)
    d["BB_MID"] = d["SMA_20"]
    d["BB_UPPER"] = d["BB_MID"] + 2 * std20
    d["BB_LOWER"] = d["BB_MID"] - 2 * std20

    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    d["ATR_14"] = _wilder_rma(true_range, 14)

    d["LOG_RETURN"] = np.log(close / close.shift(1))
    d["VOL_REALIZADA_20"] = d["LOG_RETURN"].rolling(20, min_periods=20).std(ddof=1) * np.sqrt(252) * 100

    if "Volume" in d.columns:
        d["DOLLAR_VOLUME"] = close * d["Volume"]
        d["DOLLAR_VOLUME_20"] = d["DOLLAR_VOLUME"].rolling(20, min_periods=20).mean()
        d["VOLUME_20"] = d["Volume"].rolling(20, min_periods=20).mean()
    else:
        d["DOLLAR_VOLUME_20"] = np.nan
        d["VOLUME_20"] = np.nan

    return d


def calcular_indicadores_desde_historial(
    ticker_nombre: str,
    historial: pd.DataFrame,
) -> Optional[dict]:
    """Calcula métricas y un sesgo técnico determinista para un activo."""
    try:
        d = _serie_indicadores(historial)
        if len(d) < 205:
            log.warning("%s: historial insuficiente (%s sesiones)", ticker_nombre, len(d))
            return None

        fila = d.iloc[-1]
        campos = [
            "Close", "RSI_14", "SMA_50", "SMA_200", "MACD",
            "MACD_SIGNAL", "MACD_HIST", "BB_LOWER", "BB_MID",
            "BB_UPPER", "ATR_14", "VOL_REALIZADA_20",
        ]
        if any(pd.isna(fila.get(c)) for c in campos):
            log.warning("%s: indicadores incompletos en la última sesión", ticker_nombre)
            return None

        precio = float(fila["Close"])
        atr = float(fila["ATR_14"])
        if precio <= 0 or atr < 0:
            return None

        # Componentes normalizados entre -1 y +1.
        tendencia = (
            (0.5 if precio > float(fila["SMA_50"]) else -0.5)
            + (0.5 if float(fila["SMA_50"]) > float(fila["SMA_200"]) else -0.5)
        )
        macd_norm = float(np.tanh((float(fila["MACD_HIST"]) / max(atr, 1e-9)) * 4))
        rsi_norm = float(np.clip((float(fila["RSI_14"]) - 50) / 20, -1, 1))

        banda_ancho = float(fila["BB_UPPER"] - fila["BB_LOWER"])
        posicion_bollinger = (
            float((precio - float(fila["BB_LOWER"])) / banda_ancho)
            if banda_ancho > 0 else 0.5
        )
        bollinger_norm = float(np.clip((posicion_bollinger - 0.5) * 2, -1, 1))

        # Ponderación técnica explícita; no es una probabilidad.
        score = (
            0.40 * tendencia
            + 0.30 * macd_norm
            + 0.20 * rsi_norm
            + 0.10 * bollinger_norm
        )
        score = float(np.clip(score, -1, 1))
        if score >= 0.20:
            sesgo = "ALCISTA"
        elif score <= -0.20:
            sesgo = "BAJISTA"
        else:
            sesgo = "NEUTRO"

        volumen_usd = fila.get("DOLLAR_VOLUME_20")
        volumen_usd = float(volumen_usd) if pd.notna(volumen_usd) else 0.0
        atr_pct = (atr / precio) * 100
        fecha = d.index[-1]
        fecha_datos = fecha.strftime("%Y-%m-%d") if hasattr(fecha, "strftime") else str(fecha)

        return {
            "activo": ticker_nombre,
            "fecha_datos": fecha_datos,
            "precio_cierre": precio,
            "volumen_diario": int(fila.get("Volume", 0)) if pd.notna(fila.get("Volume", 0)) else 0,
            "volumen_promedio_usd_20d": volumen_usd,
            "rsi": float(fila["RSI_14"]),
            "sma_20": float(fila["SMA_20"]),
            "sma_50": float(fila["SMA_50"]),
            "sma_200": float(fila["SMA_200"]),
            "macd_linea": float(fila["MACD"]),
            "macd_senal": float(fila["MACD_SIGNAL"]),
            "macd_histograma": float(fila["MACD_HIST"]),
            "bollinger_inferior": float(fila["BB_LOWER"]),
            "bollinger_media": float(fila["BB_MID"]),
            "bollinger_superior": float(fila["BB_UPPER"]),
            "posicion_bollinger": posicion_bollinger,
            "atr_riesgo_diario": atr,
            "atr_pct": atr_pct,
            "rango_atr_inferior": precio - atr,
            "rango_atr_superior": precio + atr,
            "volatilidad_realizada_20d_anualizada_pct": float(fila["VOL_REALIZADA_20"]),
            "score_tecnico": score,
            "intensidad_sesgo": round(abs(score) * 100, 1),
            "sesgo": sesgo,
            "riesgo_volatilidad": "ELEVADO" if atr_pct >= 4 else ("MODERADO" if atr_pct >= 2 else "CONTENIDO"),
        }
    except Exception as exc:
        log.exception("Error calculando indicadores para %s: %s", ticker_nombre, exc)
        return None


def calcular_indicadores_duros(ticker_nombre: str) -> Optional[dict]:
    """Compatibilidad con pruebas individuales y código legado."""
    historiales = descargar_historiales([ticker_nombre], periodo="18mo", tamano_lote=1)
    historial = historiales.get(ticker_nombre)
    return calcular_indicadores_desde_historial(ticker_nombre, historial) if historial is not None else None


if __name__ == "__main__":
    for activo in ("AAPL", "MSFT", "NVDA"):
        resultado = calcular_indicadores_duros(activo)
        if resultado:
            print(
                f"{activo}: sesgo={resultado['sesgo']} "
                f"score={resultado['score_tecnico']:.2f} "
                f"vol20={resultado['volatilidad_realizada_20d_anualizada_pct']:.1f}% "
                f"ATR={resultado['atr_pct']:.2f}%"
            )
