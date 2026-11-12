"""
Capa de explicación de CURU.

La IA NO calcula la señal, la puntuación ni una probabilidad de éxito.
Su función opcional es resumir los titulares recibidos. Si falla, el informe
sigue funcionando con una explicación técnica determinista.
"""
import os
import logging
try:
    from openai import OpenAI
except ImportError:  # El motor cuantitativo no depende de la IA.
    OpenAI = None

log = logging.getLogger("curu.cerebro")


def _resumen_local(datos, noticias_micro, noticias_macro):
    sesgo = datos.get("sesgo", "NEUTRO")
    rsi = datos.get("rsi", 50)
    hist = datos.get("macd_histograma", 0)
    precio = datos.get("precio_cierre", 0)
    sma50 = datos.get("sma_50", precio)
    sma200 = datos.get("sma_200", precio)
    atr_pct = datos.get("atr_pct", 0)
    vol = datos.get("volatilidad_realizada_20d_anualizada_pct", 0)

    tendencia = "por encima" if precio > sma200 else "por debajo"
    impulso = "positivo" if hist > 0 else ("negativo" if hist < 0 else "cercano a cero")
    noticia_txt = (
        f"Se encontraron {len(noticias_micro)} titulares corporativos recientes y "
        f"{len(noticias_macro)} titulares de mercado."
        if noticias_micro or noticias_macro
        else "No se obtuvieron titulares recientes verificables; el componente informativo queda neutral."
    )
    return (
        f"Sesgo técnico {sesgo.lower()}: el precio está {tendencia} de la SMA 200 "
        f"(${sma200:.2f}); RSI {rsi:.1f} y MACD histograma {impulso} ({hist:.4f}). "
        f"ATR equivale al {atr_pct:.2f}% del precio y la volatilidad realizada anualizada "
        f"de 20 sesiones es {vol:.1f}%. {noticia_txt}"
    )


def analizar_activo_con_ia(datos_matematicos, noticias_micro, noticias_macro):
    """
    Devuelve comentario informativo. No devuelve compra/venta ni porcentajes.
    Groq y OpenRouter son opcionales; sin credenciales se usa el respaldo local.
    """
    fallback = _resumen_local(datos_matematicos, noticias_micro, noticias_macro)
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    router_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    titulares = []
    for etiqueta, lista in (("EMPRESA", noticias_micro), ("MERCADO", noticias_macro)):
        for n in lista[:5]:
            titulares.append(
                f"{etiqueta} | {n.get('fecha', 'fecha no disponible')} | "
                f"{n.get('fuente', 'fuente no disponible')} | {n.get('titulo', '')}"
            )

    if not titulares:
        return fallback

    prompt = (
        "Resume en español, en máximo 3 frases, únicamente el contexto informativo "
        "de estos titulares. No inventes hechos, causalidad, cifras ni noticias. "
        "No emitas recomendaciones de compra/venta, predicciones ni probabilidades. "
        "Si los titulares no permiten inferir impacto financiero directo, dilo. "
        "Distingue noticias corporativas de contexto macro.\n\n"
        + "\n".join(titulares)
    )

    proveedores = []
    if OpenAI is None:
        return fallback
    if groq_key:
        proveedores.append(("https://api.groq.com/openai/v1", groq_key,
                            os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")))
    if router_key:
        proveedores.append(("https://openrouter.ai/api/v1", router_key,
                            os.getenv("OPENROUTER_MODEL", "openrouter/free")))

    for base_url, key, model in proveedores:
        try:
            client = OpenAI(base_url=base_url, api_key=key, timeout=25, max_retries=0)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Eres un resumidor financiero prudente. No pronosticas precios."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=180,
            )
            texto = response.choices[0].message.content
            if texto and texto.strip():
                return texto.strip()
        except Exception as exc:
            log.warning("Proveedor IA no disponible (%s): %s", base_url, exc)

    return fallback
