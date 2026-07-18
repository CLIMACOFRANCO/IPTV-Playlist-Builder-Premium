# Bulk Ranking Harvest 01 — método

## Objetivo práctico

Este runner amplía el universo de marcas IPTV a partir de páginas que comparan o
enumeran varios servicios. La ejecución real se realiza una sola vez y recorre
automáticamente Search, filtro dinámico local, Map, filtro de productividad por
dominio, Crawl selectivo, Extract de respaldo, filtro de marcas, consolidación,
Top 50 y Top 20.

El resultado es un inventario de candidatos trazable. No constituye una
evaluación de legitimidad, reputación, estabilidad, calidad, precio, EPG,
soporte, trial ni dominio oficial.

## Capacidades Tavily utilizadas

El runner utiliza el SDK oficial `tavily-python` y no Tavily CLI:

- Search para recuperar hasta 240 resultados de 24 consultas multirregión.
- Map para descubrir hasta 60 URLs en cada uno de un máximo de 10 dominios.
- Crawl para obtener hasta 25 páginas completas en cada uno de un máximo de
  cuatro dominios productivos.
- Extract como respaldo, en un máximo de tres lotes de 20 URLs.

La creación del cliente y la lectura de `TAVILY_API_KEY` son tardías y solo
ocurren en la ruta `--execute`, después de validar token y origen. `--dry-run`,
`--preflight`, pruebas y resumen son operaciones locales.

## Adaptación de Dynamic Search

La lógica Python funciona como filtro dinámico y mantiene el aislamiento de
contexto:

1. Los resultados brutos permanecen en memoria o se guardan completos en JSONL.
2. La consola solo muestra etapa, operación, conteos, errores sanitizados,
   principales nombres, `RUN_DIR` y estado.
3. Primero se puntúan las páginas Search; después solo se profundiza en los
   dominios con mejor productividad.
4. Map informa la selección de Crawl y de URLs para Extract de respaldo.
5. Todo el flujo vive en un script reutilizable del proyecto; no usa scripts
   temporales ni heredocs.

## Flujo automático

Una ejecución autorizada sigue estas etapas sin pausas intermedias:

1. `SEARCH`
2. `DYNAMIC_SEARCH_FILTER`
3. `MAP`
4. `DOMAIN_PRODUCTIVITY_FILTER`
5. `CRAWL`
6. `EXTRACT_FALLBACK`
7. `DYNAMIC_BRAND_FILTER`
8. `CONSOLIDATE`
9. `COMPLETE`

Una fuente vacía, inútil o fallida queda registrada y el lote continúa. El
runner se bloquea ante autenticación, corrupción, presupuesto, intento reservado
ambiguo o error estructural repetido.

## Search y filtro de rankings

Las 24 consultas congeladas cubren inglés global, Norteamérica, Europa,
español y portugués. Cada una conserva `operation_id`, secuencia, región,
idioma y `time_range`; las consultas explícitamente actuales usan
`time_range="year"`.

Search usa:

- `search_depth="advanced"`
- `max_results=10`
- `auto_parameters=False`
- `include_answer=False`
- `include_images=False`
- `include_raw_content="markdown"`
- `topic="general"`
- `include_usage=True`

Se excluyen inicialmente YouTube, Facebook, Instagram, TikTok, Pinterest y
SlideShare. Reddit puede permanecer como señal secundaria, pero no recibe
prioridad automática.

`score_ranking_page(...)` puntúa de 0 a 100 usando título, URL, snippet,
contenido Markdown, score Tavily, región, idioma, año aparente, listas, tablas,
encabezados y número de candidatos. Clasifica las fuentes A–E y conserva
principalmente A/B/C. Las menciones incidentales de hardware o reproductores
dentro de un ranking válido no excluyen la página completa; se eliminan después
en el filtro de candidatos.

## Productividad, Map y Crawl

La productividad por dominio combina páginas elegibles, candidatos, diversidad
regional y lingüística, score medio, páginas distintas y duplicación. Se eligen
automáticamente hasta 10 dominios para Map y hasta cuatro para Crawl.

Map usa profundidad 2, amplitud 50, límite 60, sin enlaces externos, timeout
150 e instrucciones orientadas a rankings, comparaciones y listas regionales.
Las rutas preferidas incluyen `best-iptv`, `iptv`, `reviews`, `comparison`,
`providers` y `services`; se excluyen privacidad, términos, contacto, login,
autor, tag, player, app, device y box.

Crawl usa profundidad 2, amplitud 30, límite 25, extracción avanzada Markdown,
sin imágenes, sin enlaces externos y timeout 150. Solo opera sobre dominios con
estructura y rendimiento suficientes; no recorre indiscriminadamente el sitio.

## Extract de respaldo

El fallback toma URLs útiles de Search o Map que no tengan evidencia válida de
Crawl o Extract, que parezcan valiosas y que puedan completar dominios no
elegidos para Crawl. Selecciona hasta 60 URLs únicas y las divide en tres lotes
máximos de 20. Conserva éxitos, fallos, `request_id`, uso y hash del payload.

## Filtro dinámico de marcas

El filtro extrae candidatos desde encabezados, tablas, listas numeradas, bullets,
negritas y posiciones. Cada mención conserva texto original, nombre normalizado,
página, dominio, región, idioma, nivel, posición, operación, registro raw,
fragmento, tipo de evidencia y supporting row IDs.

Las clasificaciones posibles son:

- `IPTV_SERVICE_CANDIDATE`
- `REVIEW`
- `EXCLUDED_HARDWARE`
- `EXCLUDED_PLAYER_APP`
- `EXCLUDED_CHANNEL_OR_PLATFORM`
- `EXCLUDED_GENERIC_TERM`
- `EXCLUDED_OTHER`

La normalización solo aplica transformaciones seguras de espacios,
puntuación, mayúsculas y sufijos obvios. No fusiona nombres materialmente
distintos. El universo histórico FIX4 se usa como referencia, nunca como filtro
ni prioridad automática.

## Consolidación y ranking

Los nombres canónicos conservan todas sus variantes. La puntuación 0–100 asigna
hasta 50 puntos por dominios distintos, 25 por calidad A/B/C, 15 por actualidad
y 10 por diversidad regional e idiomática. Se generan la lista completa, Top 50
y Top 20 para pruebas reales.

## Presupuesto y reintentos

Los techos físicos son rígidos:

| Etapa | Solicitudes | Contenido máximo |
|---|---:|---:|
| Search | 24 | 240 resultados |
| Map | 10 | 600 URLs |
| Crawl | 4 | 100 páginas |
| Extract | 3 | 60 URLs |
| Total | 41 | — |

Existe un máximo de un retry por operación, solo para 429, 5xx o timeout. Cada
retry cuenta contra el techo físico de 41; si consume capacidad, las operaciones
posteriores se detienen antes de excederlo. No hay retry para 400, 401, 403,
configuración, presupuesto, selección vacía, respuesta válida vacía, corrupción
o fallo estructural permanente.

Antes de cada llamada se reserva la operación, se incrementa el contador y se
persisten checkpoint y `ATTEMPT_RESERVED`. Después se guarda la respuesta y se
registra `COMPLETED` o `FAILED`. Resume omite completadas, no repite fallos no
transitorios y bloquea reservas ambiguas. Un run `COMPLETE` no se ejecuta otra
vez.

## Salidas

El run genera los 26 artefactos contractuales: plan; raw Search, Crawl y Extract;
tablas de páginas, filtros, productividad, menciones, nombres canónicos,
exclusiones, revisión, matrices, cobertura, ranking, Top 50 y Top 20; ledger,
errores, métricas, reporte, checkpoint, manifest e integridad. Además guarda
`mapped_results.jsonl` para conservar la respuesta Map bruta y auditable.

Los CSV derivados conservan supporting row IDs. Todos los artefactos se escriben
en UTF-8 y mediante reemplazo atómico. `integrity_manifest.json` registra sus
hashes.

## Criterios de éxito

Objetivo deseado: 30–60 páginas útiles, 300–600 menciones, 80–150 nombres
únicos, Top 50 y Top 20. El mínimo metodológico aceptable es 30 páginas, 300
menciones, 60 candidatos únicos, trazabilidad, Top 50 y Top 20.

El dictamen de datos será `BULK_HARVEST_SIRVIO`,
`BULK_HARVEST_SIRVIO_PARCIALMENTE` o `BULK_HARVEST_NO_SIRVIO`. No alcanzar 80
nombres por sí solo no implica fracaso.

## Exclusiones y limitaciones

- No usa Crawl ni Research fuera del flujo delimitado.
- No investiga propiedad, entidad legal, legitimidad u oficialidad.
- No evalúa estabilidad, streaming, EPG, precio, soporte o trial.
- No resuelve ambigüedades individuales mediante búsquedas adicionales.
- El filtrado determinístico puede enviar nombres dudosos a `REVIEW`.
- La ejecución real depende de los resultados disponibles en ese momento y
  queda pendiente de revisión humana posterior a `COMPLETE`.
