# CURU SIGNAL AI — release candidate

Plataforma Telegram con informe cuantitativo, cortesía de bienvenida de una sola entrega por cuenta de Telegram, membresías de 30 días y cobro mediante Mercado Pago.

## Estado de esta versión

Esta es una base de lanzamiento consolidada, todavía pendiente de configurar con las credenciales y el servidor reales y de completar una prueba de extremo a extremo en Mercado Pago.

### Componentes incluidos

- Motor cuantitativo del paquete original: descarga por lotes, cobertura mínima, filtro de liquidez, volatilidad realizada, RSI, SMA, MACD, Bollinger y ATR.
- Suavizado RSI/ATR inicializado con la media simple de las primeras 14 observaciones, conforme al método de Wilder.
- Informe PDF con score técnico claramente separado de probabilidad/confianza estadística.
- PostgreSQL en producción; SQLite solo para desarrollo.
- Historial persistente de usuarios, cortesías, pagos, suscripciones, informes, entregas, webhooks y auditoría.
- Restricciones de base de datos que impiden borrar o truncar registros históricos.
- Cortesía única por `telegram_id`, reservada atómicamente y con reintento de entrega sin crear un segundo beneficio.
- Checkout Pro mediante Preferences API, validación HMAC de webhook, consulta del pago a Mercado Pago, comprobación estricta del importe y moneda definidos en cada orden, y activación idempotente. El catálogo de precios puede ofrecer varios mercados/monedas desde Telegram.
- Reconciliación de pagos reembolsados/contracargos: el acceso asociado se revoca sin borrar los registros.
- Generación y envío diario programado en la zona `America/Bogota`.
- Docker, health check y carpeta de informes configurable para volumen persistente.

## Importante sobre la cortesía

La garantía técnica actual es una cortesía por **cuenta de Telegram** (`telegram_id`). Telegram no entrega una identidad civil verificable por defecto, por lo que no es posible garantizar una cortesía por persona física si alguien crea varias cuentas. Para eso habría que añadir una verificación adicional, por ejemplo teléfono, con consentimiento y política de privacidad.

Si falla la generación o el envío, el beneficio queda reservado como `failed`; un nuevo `/start` reintenta entregar el mismo beneficio, no crea uno nuevo. Los estados y los intentos quedan auditados.

## Configuración local

1. Crear un entorno virtual e instalar `requirements.txt`.
2. Copiar `.env.example` a `.env` y completar variables. Nunca subir `.env` al repositorio.
3. Para desarrollo se permite SQLite. En producción `APP_ENV=production` exige `DATABASE_URL` PostgreSQL.
4. Ejecutar `python bot.py`.
5. Verificar `GET /health`.

## Pagos multi-moneda e internacionalización

- El modelo de órdenes ya no asume que todo pago es COP: cada intención conserva su importe esperado y código ISO 4217 de moneda; cada pago guarda importe y moneda recibidos.
- Telegram muestra los mercados configurados en `CURU_PRICE_CATALOG`. Ejemplo de variable de entorno: `CURU_PRICE_CATALOG={"CO":{"label":"Colombia","currency":"COP","amount":"30000"},"MX":{"label":"México","currency":"MXN","amount":"199"}}`. Los importes son ejemplos de configuración, no precios comerciales recomendados.
- Si la variable no existe, se conserva el catálogo colombiano heredado (`PRECIO_SUSCRIPCION_COP`). No se debe habilitar un mercado hasta confirmar que la cuenta y el producto de pago del proveedor aceptan esa moneda y pueden liquidar los fondos al vendedor. Cambiar el código de moneda no crea por sí solo capacidad internacional.
- Para actualizar una base PostgreSQL existente, ejecutar una sola vez `migrations/002_payment_multi_currency.sql` antes de desplegar este código. La migración conserva las órdenes y pagos COP anteriores. En bases nuevas, `init_db()` crea directamente el esquema actualizado.
- El diseño deja el importe/moneda desacoplados de la membresía, pero la integración de cobro activa sigue siendo Mercado Pago. Para cobertura global real habrá que habilitar el producto Cross Border aplicable a la cuenta o añadir otro proveedor (por ejemplo, uno con cobertura internacional adecuada); no se debe anunciar aceptación mundial hasta probar cobros y liquidación por país.

## Nota de integración Mercado Pago

La versión actual utiliza Preferences API para conservar compatibilidad con el flujo del proyecto anterior. Mercado Pago mantiene esa API, pero su documentación actual recomienda Orders API para integraciones nuevas y señala que las nuevas funcionalidades se concentran allí. Antes de escalar comercialmente conviene migrar el checkout a Orders API y ejecutar de nuevo las pruebas de compra, notificaciones y reembolsos.

## Variables obligatorias en producción

- `TELEGRAM_BOT_TOKEN`
- `MERCADOPAGO_ACCESS_TOKEN`
- `MERCADOPAGO_WEBHOOK_SECRET`
- `DATABASE_URL` (PostgreSQL)
- `PUBLIC_BASE_URL` (HTTPS público del servicio)
- `REPORTS_DIR` (directorio montado en almacenamiento persistente)

Variables opcionales:

- `ADMIN_TELEGRAM_IDS`: también habilita `/reintentar_cortesia TELEGRAM_ID` para reintentar la misma cortesía pendiente/fallida.
- `PRECIO_SUSCRIPCION_COP` (por defecto 30000)
- `DURACION_SUSCRIPCION_DIAS` (por defecto 30)
- `ADMIN_TELEGRAM_IDS` (IDs separados por coma; no hay VIP codificados en el repositorio)
- `CRON_SECRET` (solo si se desea habilitar `/webhook-cron`)
- `GROQ_API_KEY`, `OPENROUTER_API_KEY` (análisis contextual de métricas técnicas y noticias para los diez activos seleccionados; no calcula las métricas ni probabilidades)

## Despliegue Docker

- Construir desde esta carpeta con el `Dockerfile`.
- Configurar las variables obligatorias.
- Montar un volumen persistente en `/data` o definir `REPORTS_DIR` a la ruta persistente elegida.
- Mantener **una sola réplica** de la aplicación: el proceso ejecuta un consumidor de Telegram y un scheduler integrado. No escalar horizontalmente esta misma imagen sin separar el scheduler/worker y añadir bloqueo distribuido.
- Publicar el puerto asignado en `PORT`.
- Configurar el webhook de Mercado Pago a `https://TU_DOMINIO/webhook-pago`.
- Mantener la base de datos PostgreSQL con backups automáticos y probar una restauración.

## Migración del archivo antiguo de usuarios

El proyecto anterior incluía un `usuarios.json` con fechas de vencimiento. Para conservarlas, copia ese archivo de forma segura al servidor y ejecuta una sola vez:

```bash
python migrar_usuarios_legacy.py /ruta/usuarios.json
```

El importador es idempotente: repetirlo no duplica la suscripción legacy. No se debe subir el JSON con IDs de usuarios a GitHub.

## Pruebas

```bash
python -m unittest -v test_motor.py
python -m unittest discover -s tests -v
```

Las pruebas automatizadas cubren cálculo sintético, análisis IA simulado, selección Top 10, generación PDF, persistencia SQLite, idempotencia de pagos, reembolsos, firma de webhook y cliente Checkout Pro con HTTP simulado. No prueban credenciales reales, entrega real de Telegram, cotizaciones reales de Yahoo Finance ni despliegue en infraestructura.

## Límites de análisis y publicación

- El score entre -1 y +1 y la intensidad 0–100 son métricas internas, **no probabilidades**.
- El PDF declara que no existe aún una confianza estadística calibrada. No se debe anunciar porcentaje de acierto hasta ejecutar backtesting walk-forward, pruebas fuera de muestra, costes/slippage y calibración.
- La selección actual prioriza volatilidad realizada y liquidez; identifica activos volátiles para análisis, no “ganadores” ni señales garantizadas.
- Yahoo Finance/yfinance es una fuente de conveniencia sin SLA; el proceso aborta si la cobertura mínima no se cumple.
- `sp500.txt` recibido contiene 497 símbolos; debe actualizarse y validarse contra una fuente vigente antes de publicitar cobertura total del S&P 500.
- La IA contextualiza las métricas técnicas ya calculadas por CURU junto con los titulares recientes de cada activo y del S&P 500. No se han integrado estados financieros estructurados ni series macroeconómicas; si la IA falla, el informe conserva una explicación cuantitativa determinista.

## Seguridad

Las credenciales que aparecieron en los ZIP recibidos deben considerarse expuestas. Revocar/rotar el token de Telegram, el Access Token de Mercado Pago y cualquier clave de IA/proxy que haya estado en los archivos o en el historial Git. No reutilizar secretos de los ZIP. Configurar secretos nuevos en el panel del proveedor.
