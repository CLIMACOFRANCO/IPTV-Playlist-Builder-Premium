# BRAND-FIRST Research Method

## 1. Alcance y genealogia inmutable

`BRAND-FIRST-MARKET-UNIVERSE-1A-FIX2` reconstruye offline:

`1.035 menciones originales -> 757 registros depurados -> 692 PROVIDER historicos -> Top 50 historico exacto`.

La unidad primaria es `CANONICAL_BRAND`. FIX2 no reescribe los 692 `PROVIDER`: agrega interpretacion semantica, calidad de publicacion, independencia, colisiones, score diagnostico y elegibilidad. No atribuye dominios oficiales, operadores legales ni ecosistemas empresariales. No selecciona ninguna marca para investigacion externa.

## 2. Superficies separadas

El metodo produce dos superficies distintas:

1. `RANKING_DIAGNOSTICO_COMPLETO`: conserva las 692 filas, su score, `diagnostic_rank`, semantica, colisiones, calidad, independencia, penalizaciones y blockers.
2. `TOP50_ADJUDICATION_READY`: hasta 50 filas que cumplen todas las reglas estrictas. Estan listas para revision humana, pero no estan aprobadas ni validadas externamente.

El segundo conjunto no se rellena relajando reglas. Si hay menos de 50 elegibles, se exporta la cantidad real. No es ranking de calidad, legalidad u oficialidad.

## 3. Identificadores, procedencia e integridad

Los IDs se obtienen con SHA-256 sobre contenido normalizado: `source_id`, `source_row_id`, `mention_id`, `canonical_brand_id`, `alias_id`, `independence_group_id`, `platform_id`, `publisher_id`, `publication_id` y `replica_component_id`. No dependen del orden de ejecucion.

El runner exige diez insumos autoritativos, registra SHA-256 antes y despues y verifica:

- corpus JSON/CSV con las mismas 535 URL;
- Top 50 CSV/XLSX con filas y columnas equivalentes;
- reconstruccion historica exacta;
- inmutabilidad de insumos y runs previos;
- exactamente 19 entregables en un directorio nuevo.

## 4. Ranking historico

El Top 50 historico filtra `category == PROVIDER` y ordena por:

1. confianza `HIGH`, `MEDIUM`, `LOW`;
2. `recurrence_score` descendente;
3. dominios unicos descendentes;
4. plataformas descendentes;
5. URL de evidencia descendentes;
6. nombre canonico estable.

La formula preservada es:

```text
source_count
+ 2.0 * unique_domains_count
+ 1.5 * platform_count
+ 0.5 * min(evidence_url_count, 25)
```

Solo se declara `RECOVERED_EXACT` cuando las 50 filas y sus metricas coinciden.

## 5. MENTION_CONTEXT y semantica local

Cada aparicion exacta genera un `MENTION_CONTEXT` con:

- `exact_raw_variant`;
- `left_context` y `right_context` adyacentes;
- `sentence_or_fragment`;
- `mention_start` y `mention_end`;
- `source_id`, `source_row_id` y `query_id` cuando existe;
- `mention_use_type` y subtipo.

Tipos de uso:

- `NOMINAL_BRAND_USE`;
- `DESCRIPTIVE_GENERIC_USE`;
- `PRODUCT_OR_CATEGORY_USE`;
- `PLAYER_OR_APPLICATION_USE`;
- `BROADCASTER_OR_CHANNEL_USE`;
- `OTT_OR_TELECOM_USE`;
- `INFRASTRUCTURE_OR_TECHNICAL_USE`;
- `HARDWARE_OR_DEVICE_USE`;
- `EDITORIAL_OR_DIRECTORY_USE`;
- `UNRESOLVED_CONTEXT_USE`.

Las reglas son deterministas y se atan a la variante exacta, sus tokens adyacentes, puntuacion, verbos y frase nominal. Una palabra distante no decide el estado. `GENERIC_PHRASE_PATTERN` se reserva para frases funcionales explicitamente vinculadas; no existe una segunda lista global contradictoria.

Parametros configurables:

```text
MIN_NOMINAL_BRAND_USES_FOR_PLAUSIBLE = 2
MAX_INCOMPATIBLE_CONTEXT_RATIO = 0.50
MIN_DISTINCT_SUPPORTING_SOURCES = 2
MIN_ACCEPTABLE_SOURCE_QUALITY = D
```

`PLAUSIBLE_BRAND` requiere usos nominales suficientes, no dominados por usos incompatibles, y evidencia local de calidad aceptable. Dos fuentes son obligatorias para `TOP50_ADJUDICATION_READY`; el corpus no contiene nivel A que permita la excepcion de fuente unica.

Estados no comparables conservados en el universo historico pero inelegibles:

- `POSSIBLE_BROADCASTER_OR_CHANNEL`;
- `POSSIBLE_LEGAL_OTT`;
- `POSSIBLE_TELECOM_OR_PAYTV`;
- `POSSIBLE_INFRASTRUCTURE_TERM`;
- `POSSIBLE_HARDWARE_OR_DEVICE`;
- `POSSIBLE_EDITORIAL_OR_DIRECTORY`;
- `POSSIBLE_PLAYER_OR_PLATFORM`;
- `GENERIC_NAME_REQUIRES_REVIEW`;
- `POSSIBLE_EXTRACTION_ARTIFACT`;
- `INSUFFICIENT_LOCAL_EVIDENCE`;
- `UNRESOLVED`.

La inelegibilidad no demuestra inexistencia.

## 6. Taxonomia de colisiones

FIX2 no fusiona automaticamente ninguna colision. La normalizacion nominal localiza candidatos y luego evalua evidencia compatible o contradictoria:

- `ALIAS_DUPLICATE_CANDIDATE`: nombres casi equivalentes con contextos compatibles; compartir fuente aumenta confianza, pero no es requisito.
- `GENERIC_COLLISION`: permutaciones de frases de consulta, terminos funcionales o construcciones genericas.
- `TRUE_HOMONYM_CANDIDATE`: exige contextos localmente diferenciados, referencias y una razon explicita de incompatibilidad.
- `POSSIBLE_IMPERSONATION`: exige indicios locales de copia, imitacion o representacion como otra marca.
- `UNRESOLVED_NOMINAL_COLLISION`: similitud fuerte sin evidencia suficiente para decidir.

Se exportan `collision_type`, confianza, base, conteos de fuentes/contextos compartidos, contextos contradictorios, referencias y `requires_human_adjudication`. Un conteo compartido cero nunca se describe como soporte compartido. Toda colision pendiente bloquea `TOP50_ADJUDICATION_READY`.

## 7. Calidad de cada publicacion

La calidad se decide por publicacion, no por hostname. Se exportan por separado:

- `platform_type` y `publisher_id`;
- `publisher_identity`;
- `publication_quality`;
- `promotional_risk`;
- `off_topic_risk`;
- `self_promotion_risk`;
- `affiliate_risk`;
- `spam_risk`.

Niveles operativos:

- `B`: contexto tecnico/comunitario sustantivo, revisable y sin promocion dominante;
- `C`: review o comparativa con valor moderado y posible afiliacion/plataforma comercial;
- `D`: promocion, self-publishing, reseller o review comercial no independiente;
- `E`: spam, copia, off-topic, baja originalidad o promocion evidente en comunidad no relacionada;
- `UNKNOWN`: evidencia insuficiente.

Los pesos siguen siendo `A=1.00, B=0.80, C=0.50, D=0.20, E=0.00, UNKNOWN=0.20`, pero A no puede asignarse con el corpus actual. Toda fila declara `A_NOT_ASSESSABLE_FROM_CURRENT_CORPUS`; no se expone A como resultado producible.

Reddit, Hacker News, Trustpilot, YouTube y otras plataformas multiusuario no reciben B ni independencia editorial por hostname.

## 8. Independencia multiusuario

La jerarquia es:

```text
platform_id -> publisher_id -> publication_id -> independence_group_id
```

En plataformas multiusuario se usa autor, canal, cuenta o identidad local cuando existe. Si no existe, cada fuente conserva `UNRESOLVED_PUBLISHER`; compartir plataforma se registra como dependencia de plataforma, no como identidad editorial comun. Publicaciones del mismo publisher son dependientes. Publishers distintos no se fusionan automaticamente.

En sitios editoriales tradicionales, el mismo hostname puede formar `SAME_HOST_DEPENDENT`. Ningun singleton se presenta como independencia demostrada.

Campos de auditoria: `platform_dependency`, `publisher_dependency`, `hostname_dependency` y `editorial_independence_status`.

## 9. Replicas directas sin transitividad excesiva

Las aristas source-level se crean por:

- contenido exacto entre hosts;
- titulo y orden de marcas equivalente;
- lista de al menos ocho marcas con solapamiento `>= 0.85` y concordancia de orden `>= 0.75`.

Una fuente solo recibe `direct_replica_member=YES` si participa directamente en una arista. Las componentes conectadas conservan `replica_component_id`, pero la transitividad no inventa aristas ni absorbe otras paginas del hostname. Se exportan `direct_replica_edge_count`, `direct_replica_partner_ids` y `transitive_only_relationship`.

Recurrencia conservadora por marca y grupo:

- singleton no demostrado: maximo `0.50`;
- mismo hostname/publisher: maximo `0.75`;
- replica probable: `0.25` con una pagina y maximo `0.50` con presencia repetida;
- duplicacion exacta/probable: maximo `0.50`.

## 10. Score diagnostico y elegibilidad estricta

El score diagnostico de las 692 filas combina independencia, recurrencia ponderada por calidad, diversidad de fuentes, consultas, idiomas, geografia explicita y trazabilidad. Como no hay fechas fiables, recencia es `NOT_AVAILABLE` y su peso se redistribuye globalmente de forma identica.

Se mantienen penalizaciones transparentes por duplicacion, promocion, alias, colision, concentracion, trazabilidad, replicas, baja originalidad, evidencia insuficiente, frase generica, artefacto, player y contexto no comparable. El score queda entre 0 y 100 y produce `diagnostic_rank` para las 692.

FIX3 separa estrictamente el ranking diagnostico de readiness. Primero se calculan semantica, evidencia, calidad, publishers, grupos, promocion y score; despues se asigna `readiness_status`; finalmente `adjudication_ready_eligible` se deriva de ese estado. Solo `TRACEABLE_FOR_FUTURE_PRIORITIZATION` puede publicarse.

Umbrales de readiness, definidos como constantes y no calibrados para llenar 50 filas:

- `MIN_ACCEPTABLE_SOURCE_COUNT_FOR_READY=2`;
- `MIN_DISTINCT_PUBLISHERS_FOR_READY=2`;
- `MIN_DISTINCT_GROUPS_FOR_READY=2`;
- `MIN_DIAGNOSTIC_SCORE_FOR_READY=5.0`;
- `MAX_HIGH_PROMOTIONAL_RELATION_RATIO=0.60`;
- `MIN_NON_PROMOTIONAL_ACCEPTABLE_SOURCE_COUNT=2`;
- `MIN_SEMANTIC_CONFIDENCE_FOR_READY=MEDIUM`;
- `MIN_ACCEPTABLE_SOURCE_QUALITY=D`.

Una fuente B o C puede ser aceptable si no tiene spam/off-topic HIGH, no es replica directa/probable y conserva evidencia nominal local. Una D, ademas, debe tener `promotional_risk` distinto de HIGH. E y UNKNOWN nunca cuentan. El minimo D se aplica mediante la jerarquia de calidad, no es una constante declarativa sin uso.

Para `TOP50_ADJUDICATION_READY` se exige simultaneamente:

- `semantic_status=PLAUSIBLE_BRAND`;
- `semantic_confidence` MEDIUM o HIGH;
- score positivo y al menos 5.0;
- al menos dos fuentes aceptables;
- al menos dos publishers y dos grupos de independencia aceptables;
- concentracion promocional no bloqueante: superar 0.60 solo bloquea cuando hay menos de dos fuentes aceptables no promocionales;
- ninguna colision pendiente;
- ningun blocker semantico, de calidad o independencia;
- `requires_human_adjudication=NO`.

`adjudication_blockers` es JSON determinista. Cada elemento contiene `blocker_code`, `blocker_basis`, `blocker_supporting_row_ids` y `severity`. Se exportan tambien los conteos aceptables, promocionales y de independencia, ademas de los riesgos de fragmento embebido y etiqueta geografica/generica.

La superficie publica entre 0 y 50 filas: `published_row_count=min(available_adjudication_ready_count, 50)`. No existe backfill ni relajacion. Cada fila publicada declara `publication_limit`, `list_is_truncated`, `no_human_approval_yet` y `no_external_validation`.

## 11. Consultas, idiomas y geografias

Una consulta solo aporta contexto mediante la relacion marca-fuente que la respalda. La matriz conserva `linked_query_contexts` y `query_supporting_row_ids`. Portugues, espanol e ingles se detectan sin doble conteo; una consulta sin geografia explicita conserva `NOT_AVAILABLE`. El TLD no demuestra geografia.

## 12. Outputs y referencias

Los 19 entregables mantienen sus nombres. Los principales contratos FIX3 son:

- `06_provider_universe_692.csv`: universo diagnostico completo;
- `09_source_quality_registry.csv`: calidad y riesgos por publicacion;
- `10_source_independence_groups.csv`: plataforma, publisher, publicacion y replicas directas;
- `12_brand_recurrence_metrics.csv`: score/rank diagnostico, contextos, colisiones y blockers;
- `13_brand_seed_readiness.csv`: fuente autoritativa de readiness, sin aprobacion humana;
- `14_top50_recalibrated_offline.csv`: superficie `TOP50_ADJUDICATION_READY`, entre 0 y 50 filas sin relleno;
- `15_historical_vs_recalibrated_comparison.csv`: historico vs rank diagnostico vs adjudication-ready;
- `16` y `17`: sesgos, distribuciones, alertas y limitaciones.

El validador descubre y valida todas las columnas `*_ids` y `member_sources`, incluyendo referencias semanticas, consultas, colisiones, menciones, candidatos y partners de replica. El reporte cuenta referencias validadas por nombre de campo.

## 13. Operacion offline y reproducibilidad

El guard bloquea `socket.connect`, `socket.create_connection`, `socket.getaddrinfo` y `urllib.request.urlopen`. El scan estatico rechaza Tavily, requests, dotenv, `os.getenv`, `os.environ` y lecturas de credenciales.

```powershell
python .\scripts\build_brand_first_market_universe.py --validate-only
python .\scripts\build_brand_first_market_universe.py --dry-run
python .\scripts\build_brand_first_market_universe.py --execute
```

`--execute` crea un `run_<YYYYMMDD_HHMMSS>` nuevo y falla si ya existe. Los CSV usan UTF-8 con BOM; JSON y Markdown se validan; las escrituras son atomicas.

La construccion se repite dos veces en memoria. El hash logico excluye solo inventario temporal, manifest y reporte de validacion. Mismos insumos y codigo producen el mismo hash logico.

## 14. Limites

La evidencia local esta sesgada por consultas iniciales, idiomas, geografias, SEO, afiliacion, reseller, duplicacion y ausencia de fechas. `UNKNOWN` no significa falso, y `PLAUSIBLE_BRAND` no prueba identidad, calidad, legalidad u oficialidad. Toda decision final requiere revision humana posterior y autorizada.

## 15. Correcciones de calibracion FIX4

FIX4 distingue una compactacion canonica de un substring accidental. Una variante
nominal puede conservar identidad cuando concatena los tokens distintivos del
canonico en el mismo orden, con o sin espacios, guiones, mayusculas y el sufijo
de servicio `TV` o `IPTV`. Por ejemplo, `Free Go TV` y `FreeGoTV` son la misma
forma canonica si el contexto local es nominal. Esta excepcion no cubre una
marca mayor distinta, perdida de tokens distintivos, categorias descriptivas o
geograficas, ni terminos tecnicos; esos casos siguen sujetos a los riesgos
semanticos y de fragmento.

`UNKNOWN PUBLISHER` no equivale a publisher independiente. Cada fuente conserva
su `source_id` y `publication_id`, pero un publisher no resuelto no recibe
`publisher_id` util para diversidad ni crea independencia positiva. Los estados
exportados separan `RESOLVED_PUBLISHER`, `PLATFORM_USER_RESOLVED`,
`UNRESOLVED_PUBLISHER`, `SHARED_PLATFORM_UNRESOLVED` y
`REPLICA_OR_DEPENDENT`. Reddit, YouTube, Hacker News y plataformas equivalentes
solo aportan diversidad cuando existe una identidad local recuperable; Trustpilot
puede resolverla desde una ruta `/review/...`. Las fuentes no resueltas no se
fusionan arbitrariamente y las replicas directas conservan su agrupacion.

Las metricas exportan `resolved_acceptable_publisher_count`,
`unresolved_acceptable_publisher_count`,
`resolved_acceptable_independence_group_count`,
`unresolved_independence_evidence_count`, `publisher_diversity_eligible` e
`independence_diversity_eligible`. Los minimos de readiness usan exclusivamente
la evidencia resuelta que cuenta para diversidad.

El validador vuelve a calcular las 692 filas desde la matriz de relaciones,
calidad, riesgos, evidencia nominal, replicas, publishers resueltos, grupos,
semantica, score, colisiones y constantes. No acepta como evidencia los flags
exportados de readiness, elegibilidad o blockers. Si el Top esta vacio, primero
debe comprobar que la recomputacion independiente encuentra cero elegibles; por
ello `all([])` nunca basta para validar la publicacion, metadata o strictness.
Una publicacion vacia sigue siendo valida cuando esa comprobacion independiente
la justifica. Esta verificacion es una auditoria asistida por IA; no es una
adjudicacion humana.
