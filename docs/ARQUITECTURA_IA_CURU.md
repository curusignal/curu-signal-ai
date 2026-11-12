# CURU SIGNAL AI — Alcance y arquitectura de análisis con IA

**Versión del documento:** 1.0  
**Fecha:** 11 de noviembre de 2026  
**Estado:** especificación aprobada para la primera versión; todavía no implica que todas las funciones descritas estén implementadas.

## 1. Alcance de la primera versión

La primera versión comercial de CURU SIGNAL AI analizará exclusivamente acciones pertenecientes al **S&P 500**.

No se incorporarán en esta versión criptomonedas, penny stocks, opciones, acciones OTC ni otros activos de alto riesgo. Una futura versión para activos de alto riesgo será un producto separado, con universo, filtros de liquidez, controles de riesgo, pruebas y comunicación propios.

La decisión de limitar el universo busca mantener una cobertura de datos manejable, reducir fallos y evitar saturar el proceso de análisis.

## 2. Objetivo de la IA

La IA debe aportar análisis e interpretación financiera, no limitarse a resumir titulares. Su función será estudiar la información estructurada que CURU haya obtenido y calculado, identificar coincidencias y contradicciones entre factores, explicar riesgos y redactar una conclusión trazable.

La IA **no** debe:

- inventar precios, indicadores, resultados financieros, eventos, fuentes o fechas;
- presentar una inferencia como si fuera un dato confirmado;
- convertir un score técnico en probabilidad de acierto;
- prometer rentabilidad ni garantizar movimientos futuros;
- sustituir los cálculos cuantitativos reproducibles del motor.

## 3. Flujo de análisis previsto

### Etapa A — Cobertura del universo

1. Cargar la lista local del S&P 500.
2. Descargar los datos históricos disponibles para todos los símbolos.
3. Calcular las métricas cuantitativas de cada símbolo.
4. Registrar la fecha de los datos y la cobertura real.
5. Detener el informe si la cobertura queda por debajo del mínimo configurado.
6. Aplicar el filtro de liquidez antes de presentar resultados.

La lista local actual contiene 497 símbolos según la revisión técnica disponible. Antes de anunciar cobertura completa del S&P 500 deberá contrastarse y actualizarse contra una fuente vigente y documentada.

### Etapa B — Primera lectura de IA de todo el universo elegible

La IA hará una lectura preliminar de **todos los símbolos que hayan superado los controles de datos y liquidez**, no solamente del Top 10.

Para controlar consumo, tiempo y límites de proveedores:

- enviar los activos en lotes compactos, no una llamada independiente por símbolo;
- reutilizar resultados mientras no cambien los datos de entrada relevantes;
- guardar el proveedor, modelo, fecha, versión del prompt y estado de cada evaluación;
- limitar tamaño de entrada y salida;
- manejar límites, errores y respuestas inválidas sin detener ni falsear el análisis cuantitativo;
- marcar explícitamente los activos sin evaluación de IA cuando el proveedor no responda.

Esta primera lectura debe identificar, cuando los datos disponibles lo permitan, alineación o divergencia entre tendencia, impulso, momentum, volatilidad y liquidez. No debe inferir fundamentales o noticias que no se hayan suministrado.

### Etapa C — Selección cuantitativa y análisis profundo

La selección del informe seguirá siendo reproducible y separada de la opinión del modelo. El Top 10 se determinará mediante las reglas cuantitativas configuradas por CURU (actualmente, volatilidad realizada a 20 sesiones y ATR, después del filtro de liquidez).

Sobre esos activos seleccionados se realizará una segunda lectura más profunda de IA, incorporando:

- métricas técnicas calculadas por CURU;
- noticias corporativas recientes con fuente, fecha y enlace cuando estén disponibles;
- contexto general del mercado;
- datos fundamentales y macroeconómicos **solo cuando se integren fuentes verificables**.

La IA deberá señalar qué factores apoyan la lectura, cuáles la contradicen, qué riesgos destacan y qué información falta. Si no hay datos suficientes, debe decirlo expresamente.

## 4. Capas de información y estado

| Capa | Uso previsto | Condición para utilizarla |
|---|---|---|
| Precio e histórico | Tendencia, retornos, volatilidad y rangos | Datos con fecha y cobertura válidas |
| Indicadores técnicos | RSI, SMA, MACD, Bollinger, ATR y score | Cálculo determinista y reproducible |
| Liquidez | Filtro de negociabilidad | Volumen y precio disponibles; umbral explícito |
| Noticias corporativas | Catalizadores y riesgos específicos | Titular, fuente, fecha y enlace cuando exista |
| Contexto de mercado | Entorno general y factores macro | Fuente identificada y fecha de publicación |
| Fundamentales | Ingresos, márgenes, deuda, flujo de caja y valoración | Integrar proveedor y validar período fiscal, moneda y unidades antes de usar |

**Limitación actual importante:** la base técnica revisada calcula indicadores de precio y obtiene titulares de noticias. No se ha verificado una integración fundamental completa ni una base macroeconómica estructurada. Hasta que esas fuentes se incorporen y prueben, el informe no podrá afirmar que realiza un análisis fundamental completo.

## 5. Separación entre motor cuantitativo e IA

- El motor cuantitativo calcula indicadores, score, volatilidad, ATR, cobertura y filtros.
- La IA interpreta los datos recibidos, contrasta factores y explica el contexto.
- La IA no modifica retroactivamente las métricas ni cambia la selección cuantitativa sin una regla explícita, versionada y probada.
- Si la IA falla, CURU debe mostrar el estado de fallo o ausencia de análisis de IA y conservar los resultados cuantitativos válidos. No debe presentar el texto de respaldo como si lo hubiera generado un modelo.

## 6. Salida estructurada por activo

Cada evaluación de IA deberá conservar, como mínimo:

1. símbolo y fecha de corte de los datos;
2. estado de evaluación: completada, parcial, no disponible o error;
3. resumen de lectura técnica;
4. factores que apoyan la lectura;
5. factores que la contradicen;
6. riesgos observados;
7. eventos o noticias considerados, con fuente y fecha;
8. datos faltantes y limitaciones;
9. explicación en lenguaje claro;
10. proveedor, modelo y versión del prompt.

No se incluirá un porcentaje de probabilidad o tasa de acierto salvo que exista un modelo estadístico independiente, validado fuera de muestra y calibrado. El score técnico seguirá identificado como score, no como probabilidad.

## 7. Controles de calidad y aceptación

Antes de considerar terminada esta capa se deberán probar, al menos, estos casos:

- respuesta válida del proveedor;
- ausencia de credenciales;
- límite de uso o indisponibilidad del proveedor;
- respuesta que no respeta el formato solicitado;
- contenido vacío o malformado;
- titulares sin fecha o fuente verificable;
- datos técnicos incompletos o desactualizados;
- contradicción entre indicadores;
- activo sin noticias recientes;
- lote con uno o varios símbolos fallidos.

La prueba debe confirmar que ningún fallo de IA genera datos ficticios, bloquea indebidamente el motor cuantitativo o etiqueta un resultado no evaluado como análisis completado.

También se deberán medir consumo, latencia y tasa de fallos con un universo de prueba representativo antes de habilitar el análisis completo de todos los símbolos.

## 8. Orden de trabajo acordado

1. Corregir y completar el software y sus pruebas.
2. Verificar la cobertura y calidad de las fuentes de datos.
3. Elegir y configurar la base de datos cuando el software esté listo.
4. Elegir y configurar el servidor como último paso.
5. Ejecutar pruebas integrales antes de ofrecer el producto al público.

No se inicia en esta etapa la contratación ni configuración de base de datos o servidor.

## 9. Registro de cambios

Cada entrega de CURU deberá acompañarse de:

- archivo(s) exacto(s) que se deben agregar o reemplazar;
- ruta dentro del repositorio;
- mensaje de commit sugerido;
- explicación del cambio y motivo;
- pruebas ejecutadas y resultado;
- limitaciones o tareas pendientes.

Este documento fija el alcance y los criterios de aceptación. **No modifica por sí solo el comportamiento del bot ni activa nuevas llamadas a proveedores de IA.**
