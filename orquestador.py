"""Orquestador diario de CURU Signal AI."""
from __future__ import annotations

import logging
import hashlib
import math
import os
import shutil
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from metricas import descargar_historiales, calcular_indicadores_desde_historial
from noticias import extraer_noticias_micro, extraer_noticias_macro
from cerebro_ia import analizar_activo_con_ia
from reportes import generar_grafico_avanzado_activo, obtener_carpeta_temporal
from ensamblador import fabricar_pdf_comercial
from database import init_db, save_report

BASE = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger("curu.orquestador")


def obtener_todos_los_tickers_sp500():
    ruta = os.path.join(BASE, "sp500.txt")
    if not os.path.exists(ruta):
        raise FileNotFoundError("No existe sp500.txt; no se generará un informe con un universo improvisado.")
    with open(ruta, "r", encoding="utf-8") as archivo:
        tickers = [linea.strip().replace(".", "-") for linea in archivo if linea.strip()]
    tickers = list(dict.fromkeys(tickers))
    if len(tickers) < 400:
        raise ValueError(
            f"El archivo sp500.txt contiene solo {len(tickers)} símbolos. "
            "Verifica que sea el universo completo y actualizado del S&P 500."
        )
    return tickers


def _fecha_de_datos_valida(fecha_texto, max_dias=7):
    try:
        fecha = datetime.strptime(fecha_texto, "%Y-%m-%d").date()
        hoy = datetime.now(ZoneInfo("America/Bogota")).date()
        return 0 <= (hoy - fecha).days <= max_dias
    except Exception:
        return False


def limpiar_residuo_imagenes():
    carpeta = obtener_carpeta_temporal()
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta, ignore_errors=True)


def ejecutar_sistema_premium_automatizado():
    """Genera un único PDF diario; no realiza una generación por suscriptor."""
    inicio = datetime.now(ZoneInfo("America/Bogota"))
    init_db()
    limpiar_residuo_imagenes()

    tickers = obtener_todos_los_tickers_sp500()
    log.info("Iniciando escaneo de %s símbolos del universo local.", len(tickers))

    historiales = descargar_historiales(tickers, periodo="18mo", tamano_lote=40)
    activos = []
    for ticker, historial in historiales.items():
        datos = calcular_indicadores_desde_historial(ticker, historial)
        if datos and _fecha_de_datos_valida(datos["fecha_datos"]):
            activos.append(datos)

    cobertura = len(activos) / max(len(tickers), 1)
    for activo in activos:
        activo["universo_total"] = len(tickers)
        activo["cobertura_datos"] = cobertura
    cobertura_minima = float(os.getenv("CURU_MIN_COVERAGE", "0.70"))
    if cobertura < cobertura_minima:
        raise RuntimeError(
            f"Cobertura insuficiente: {len(activos)}/{len(tickers)} "
            f"({cobertura:.1%}). Mínimo requerido: {cobertura_minima:.0%}. "
            "Se cancela el informe para no presentar un universo incompleto como completo."
        )

    liquidez_minima = float(os.getenv("CURU_MIN_DOLLAR_VOLUME", "10000000"))
    universo_liquido = [
        a for a in activos
        if a.get("volumen_promedio_usd_20d", 0) >= liquidez_minima
    ]
    if len(universo_liquido) < 10:
        raise RuntimeError(
            f"Solo {len(universo_liquido)} activos superaron el filtro de liquidez "
            f"de USD {liquidez_minima:,.0f}; no se fabrica un Top 10 artificial."
        )

    # La selección responde al objetivo del producto: detectar volatilidad,
    # no buscar RSI extremos ni declarar ganadores.
    seleccionados = sorted(
        universo_liquido,
        key=lambda a: (
            a["volatilidad_realizada_20d_anualizada_pct"],
            a["atr_pct"],
        ),
        reverse=True,
    )[:10]

    log.info(
        "Cobertura %.1f%%. Top de volatilidad: %s",
        cobertura * 100,
        ", ".join(a["activo"] for a in seleccionados),
    )

    noticias_macro = extraer_noticias_macro()
    for activo in seleccionados:
        micro = extraer_noticias_micro(activo["activo"])
        activo["noticias_micro"] = micro
        activo["veredicto_ia"] = analizar_activo_con_ia(
            activo, micro, noticias_macro
        )
        generar_grafico_avanzado_activo(
            activo["activo"],
            activo.get("rsi"),
            historial=historiales.get(activo["activo"]),
        )

    ruta_pdf = fabricar_pdf_comercial(seleccionados, fecha_generacion=inicio)

    # El PDF vive en REPORTS_DIR, que en producción debe montarse sobre
    # almacenamiento persistente (por ejemplo, un volumen del proveedor).
    with open(ruta_pdf, "rb") as archivo:
        digest = hashlib.sha256(archivo.read()).hexdigest()
    fecha_reporte = inicio.strftime("%Y-%m-%d")
    save_report(f"sp500-{fecha_reporte}", fecha_reporte, ruta_pdf, digest)

    limpiar_residuo_imagenes()
    log.info("Informe terminado y registrado: %s", ruta_pdf)
    return ruta_pdf


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ejecutar_sistema_premium_automatizado()
