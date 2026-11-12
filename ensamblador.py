"""Ensamblador PDF de CURU: el veredicto sale del motor cuantitativo, no del RSI aislado."""
import os
import html
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)


def _fmt(valor, dec=2, prefijo="", sufijo=""):
    try:
        return f"{prefijo}{float(valor):,.{dec}f}{sufijo}"
    except (TypeError, ValueError):
        return "N/D"


def _encabezado_pie(canvas, doc):
    canvas.saveState()
    base = os.path.dirname(os.path.abspath(__file__))
    logo = os.path.join(base, "logo.png")
    if os.path.exists(logo):
        canvas.drawImage(logo, 510, 740, width=38, height=38, mask="auto")
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(40, 38, 572, 38)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawCentredString(306, 24, "CURU signal AI · Información cuantitativa, no asesoría financiera")
    canvas.restoreState()


def fabricar_pdf_comercial(lista_activos_analizados, fecha_generacion=None):
    if not lista_activos_analizados:
        raise ValueError("No hay activos analizados; no se puede fabricar un informe vacío.")

    base = os.path.dirname(os.path.abspath(__file__))
    fecha_generacion = fecha_generacion or datetime.now(ZoneInfo("America/Bogota"))
    fecha_tag = fecha_generacion.strftime("%Y-%m-%d")
    carpeta_reportes = os.getenv("REPORTS_DIR", os.path.join(base, "reportes_generados"))
    os.makedirs(carpeta_reportes, exist_ok=True)
    ruta_pdf = os.path.join(carpeta_reportes, f"Reporte_Premium_WallStreet_{fecha_tag}.pdf")
    carpeta_graficos = os.path.join(base, "temp_graficos")

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=letter, leftMargin=40, rightMargin=40,
        topMargin=48, bottomMargin=52
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "CuruTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=20, leading=24, textColor=colors.HexColor("#0F172A"),
        alignment=0, spaceAfter=5
    )
    subtitulo = ParagraphStyle(
        "CuruSub", parent=styles["Normal"], fontSize=8.5, leading=12,
        textColor=colors.HexColor("#64748B"), spaceAfter=14
    )
    h2 = ParagraphStyle(
        "CuruH2", parent=styles["Heading2"], fontSize=14, leading=17,
        textColor=colors.HexColor("#1D4ED8"), spaceBefore=5, spaceAfter=8
    )
    normal = ParagraphStyle(
        "CuruBody", parent=styles["BodyText"], fontSize=8.5, leading=12,
        textColor=colors.HexColor("#334155")
    )
    small = ParagraphStyle(
        "CuruSmall", parent=normal, fontSize=7.5, leading=10,
        textColor=colors.HexColor("#64748B")
    )
    th = ParagraphStyle(
        "CuruTH", parent=normal, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0F172A")
    )

    universo_total = lista_activos_analizados[0].get("universo_total", "N/D")
    cobertura_datos = lista_activos_analizados[0].get("cobertura_datos")
    cobertura_txt = f" · Cobertura de datos: {float(cobertura_datos):.1%}" if cobertura_datos is not None else ""
    story = [
        Paragraph("CURU SIGNAL AI · REPORTE CUANTITATIVO", titulo),
        Paragraph(
            f"Universo de referencia S&amp;P 500 · Símbolos en lista local: {universo_total} (composición pendiente de sincronización){cobertura_txt} · Generado: {fecha_generacion.strftime('%Y-%m-%d %H:%M')} "
            f"(Bogotá) · Selección: activos con mayor volatilidad realizada a 20 sesiones, "
            f"sujetos a filtro de liquidez; no es un ranking de ganadores.",
            subtitulo
        ),
        Paragraph(
            "<b>Cómo leer este informe:</b> el sesgo y la confluencia son métricas "
            "descriptivas del modelo técnico. No representan una probabilidad de acierto "
            "ni garantizan movimientos futuros. El ATR expresa amplitud histórica, no "
            "un límite máximo de pérdida. La confianza estadística calibrada no está disponible: "
            "aún se requiere backtesting walk-forward y validación fuera de muestra.",
            small
        ),
        Spacer(1, 12),
    ]

    color_sesgo = {
        "ALCISTA": colors.HexColor("#15803D"),
        "BAJISTA": colors.HexColor("#B91C1C"),
        "NEUTRO": colors.HexColor("#475569"),
    }

    for rank, activo in enumerate(lista_activos_analizados, 1):
        if rank > 1:
            story.append(PageBreak())

        ticker = html.escape(str(activo.get("activo", "N/D")))
        sesgo = str(activo.get("sesgo", "NEUTRO")).upper()
        score = _fmt(activo.get("score_tecnico"), 2)
        fuerza = _fmt(activo.get("intensidad_sesgo"), 1, sufijo=" pts/100")
        story.append(Paragraph(f"#{rank} · {ticker}", h2))

        datos = [
            [Paragraph("<b>Sesgo técnico</b>", th),
             Paragraph("<b>Score del modelo</b>", th),
             Paragraph("<b>Intensidad del score</b>", th)],
            [Paragraph(f"<font color='{color_sesgo.get(sesgo, color_sesgo['NEUTRO']).hexval()}'><b>{sesgo}</b></font>", normal),
             Paragraph(score, normal),
             Paragraph(fuerza, normal)],
        ]
        t = Table(datos, colWidths=[175, 150, 150])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), .4, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story += [t, Spacer(1, 10)]

        metricas = [
            [Paragraph("<b>Métrica</b>", th), Paragraph("<b>Valor</b>", th),
             Paragraph("<b>Lectura</b>", th)],
            ["Último cierre", _fmt(activo.get("precio_cierre"), 2, "$"), activo.get("fecha_datos", "N/D")],
            ["RSI (14)", _fmt(activo.get("rsi")), "Fuerza del movimiento; no es señal autónoma de reversión"],
            ["SMA 50 / SMA 200", f"{_fmt(activo.get('sma_50'), 2, '$')} / {_fmt(activo.get('sma_200'), 2, '$')}", "Tendencia intermedia / estructural"],
            ["MACD histograma", _fmt(activo.get("macd_histograma"), 4), "Impulso relativo"],
            ["Bandas Bollinger", f"{_fmt(activo.get('bollinger_inferior'), 2, '$')} – {_fmt(activo.get('bollinger_superior'), 2, '$')}", "Rango estadístico de 20 sesiones"],
            ["ATR (14)", _fmt(activo.get("atr_riesgo_diario"), 2, "$"), f"{_fmt(activo.get('atr_pct'), 2, sufijo='%')} del precio · riesgo {activo.get('riesgo_volatilidad', 'N/D').lower()}"],
            ["Volatilidad realizada 20d", _fmt(activo.get("volatilidad_realizada_20d_anualizada_pct"), 1, sufijo="%"), "Anualizada; calculada con retornos diarios"],
            ["Volumen promedio negociado", _fmt(activo.get("volumen_promedio_usd_20d"), 0, "$"), "Promedio diario en dólares, 20 sesiones"],
        ]
        mt = Table(metricas, colWidths=[130, 150, 195])
        mt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story += [mt, Spacer(1, 10)]

        panel = os.path.join(carpeta_graficos, f"panel_tecnico_{ticker}.png")
        rsi_img = os.path.join(carpeta_graficos, f"grafico_rsi_{ticker}.png")
        if os.path.exists(panel):
            story.append(Image(panel, width=430, height=269))
            story.append(Spacer(1, 5))
        if os.path.exists(rsi_img):
            story.append(Image(rsi_img, width=430, height=72))
            story.append(Spacer(1, 6))

        resumen = html.escape(str(activo.get("veredicto_ia") or activo.get("analisis_contextual") or "Sin comentario contextual."))
        story.append(Paragraph("<b>Lectura y contexto</b>", th))
        story.append(Spacer(1, 4))
        story.append(Paragraph(resumen, normal))
        story.append(Spacer(1, 8))

        noticias = activo.get("noticias_micro", [])
        if noticias:
            story.append(Paragraph("<b>Titulares corporativos considerados</b>", th))
            for n in noticias[:3]:
                linea = f"• {html.escape(str(n.get('titulo', '')))} — {html.escape(str(n.get('fuente', '')))}"
                story.append(Paragraph(linea, small))
        else:
            story.append(Paragraph("Sin titulares corporativos recientes verificables.", small))

    doc.build(story, onFirstPage=_encabezado_pie, onLaterPages=_encabezado_pie)
    return ruta_pdf
