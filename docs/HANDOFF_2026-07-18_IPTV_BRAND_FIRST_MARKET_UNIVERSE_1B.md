# HANDOFF — IPTV BRAND-FIRST MARKET UNIVERSE 1B

## 1. Metadatos

- Fecha de creacion: 2026-07-14
- Fecha de actualizacion y renombre: 2026-07-18
- Proyecto: IPTV Playlist Builder Premium
- Fase actual verificada: `BRAND-FIRST-MARKET-UNIVERSE-1B`
- Subhito actual: `TAVILY-SMOKE-TEST-01`
- Estado: preparacion offline del runner para ejecucion real desde PowerShell
- Ruta del proyecto: `C:\Proyectos\IPTV-Playlist-Builder-Premium`
- Baseline versionado vigente: `cbc0ea5a874a9f94ece643cbe47dd5385ee705ec`
- Nombre actual del handoff: `docs\HANDOFF_2026-07-18_IPTV_BRAND_FIRST_MARKET_UNIVERSE_1B.md`
- Nombre historico superado: `docs\HANDOFF_2026-07-14_IPTV_RESEARCH_TAVILY_PHASE2.md`

Este handoff es una guia de continuidad. No es, por si solo, prueba del estado
real del proyecto. La politica permanente `HANDOFF REALITY-CHECK CONTRACT`
aparece al final del documento y debe aplicarse antes de continuar cualquier
hito.

## 2. Objetivo general

Se esta construyendo una base de inteligencia comercial y OSINT sobre proveedores IPTV/OTT para identificar marcas, dominios candidatos, empresa juridica, pais, domicilio, aplicaciones, paneles, revendedores, tecnologia observable, transparencia, licencias publicamente demostradas o no, antecedentes legales y senales de riesgo.

Este trabajo no evalua todavia la calidad real del streaming. Tampoco debe declarar legalidad o ilegalidad sin evidencia publica suficiente.

## 3. Alcance y limites

- Investigacion basada en fuentes publicas.
- Tavily puede usarse como motor de adquisicion cuando exista autorizacion
  expresa. Las llamadas reales se ejecutan desde PowerShell conforme al
  `TAVILY EXECUTION CONTRACT`; Codex prepara y audita offline.
- Una aparicion aislada en rankings no es prueba suficiente.
- M3U, Xtream, APK o cripto no son prueba automatica de ilegalidad.
- Se deben separar afirmaciones comerciales, testimonios, fuentes independientes e inferencias tecnicas.
- Se debe preservar trazabilidad de URLs, consultas, checkpoints y resultados.
- No se deben reprocesar investigaciones ya realizadas.
- No se deben repetir consultas Tavily ya completadas.
- No se debe ejecutar el lote 2 sin autorizacion expresa.
- No se deben modificar artefactos V1/V2 existentes.

## 4. Cronologia resumida

1. Investigacion inicial de operadores y proveedores IPTV/OTT.
2. Cambio de enfoque hacia marcas comerciales comparables a Weib TV, Telelatino, Magis TV, etc.
3. Definicion de metodologia de due diligence.
4. Instalacion de Tavily.
5. Ejecucion del corpus inicial.
6. Limpieza y normalizacion.
7. Seleccion Top 50.
8. Ejecucion V1 y auditoria de ruido.
9. Rediseno V2.
10. Correccion del uso de Tavily SDK.
11. Ejecucion correcta del piloto V2.
12. Auditoria de las 50 evidencias aceptadas y 5 ambiguas.
13. Cierre V3/V4 y cierre forense Voco preservados como historia metodologica.
14. Reorientacion oficial a BRAND-FIRST en `dbff5ac`.
15. Ejecucion offline 1A y secuencia: run inicial, FIX1, FIX2, FIX3 y FIX4.
16. Inicio y cancelacion segura de FIX5; no se creo un run FIX5.
17. Cierre documental de 1A y congelacion del baseline FIX4.
18. Commit y push de cierre: `cbc0ea5`.
19. Apertura de `BRAND-FIRST-MARKET-UNIVERSE-1B`.
20. Dos intentos bloqueados del smoke test: `run_20260717_235220` y
    `run_20260718_000536`; ambos consumieron cero llamadas Tavily.
21. Estado actual: preparar offline un runner auditable y entregar un comando
    PowerShell exacto para la ejecucion real.

## 5. Descubrimiento inicial con Tavily

Hechos confirmados:

- 42 consultas ejecutadas.
- 535 fuentes unicas.
- 1.035 nombres detectados.

Archivos:

- `research\output\best_iptv_2026\tavily_corpus_20260713_222351.json`
- `research\output\best_iptv_2026\tavily_corpus_20260713_222351.csv`
- `research\output\best_iptv_2026\brands_consolidated_20260713_222351.csv`
- `research\output\best_iptv_2026\best_iptv_2026_20260713_222351.xlsx`

Script:

- `scripts\research_best_iptv_2026.py`

## 6. Limpieza y normalizacion

Hechos confirmados:

- Total inicial: 1.035
- Total depurado: 757
- Falsos positivos eliminados: 128
- Aliases fusionados: 150

Distribucion:

- PROVIDER: 692
- PLAYER: 5
- PLATFORM: 3
- LEGAL_OTT: 8
- FORUM_OR_DIRECTORY: 1
- UNKNOWN: 48

Archivos:

- `research\output\best_iptv_2026\brands_cleaned_20260713.csv`
- `research\output\best_iptv_2026\brands_rejected_20260713.csv`
- `research\output\best_iptv_2026\best_iptv_2026_cleaned_20260713.xlsx`
- `research\output\best_iptv_2026\cleaning_report_20260713.md`

Script:

- `scripts\clean_best_iptv_2026.py`

## 7. Due diligence preliminar Top 50

Hechos confirmados:

- 50 marcas unicas.
- Solo categoria PROVIDER.
- No se realizaron nuevas consultas Tavily en esta fase.

Estados:

- NEEDS_IDENTITY_RESOLUTION: 48
- PROCEED_TO_EXTERNAL_VERIFICATION: 2

Archivos:

- `research\output\best_iptv_2026\top50_due_diligence_preliminary_20260713.csv`
- `research\output\best_iptv_2026\top50_due_diligence_preliminary_20260713.xlsx`
- `research\output\best_iptv_2026\top50_due_diligence_report_20260713.md`
- `research\output\best_iptv_2026\top50_query_plan_20260713.json`

El plan contiene:

- 50 marcas.
- 12 categorias.
- 1.654 consultas futuras preparadas.
- Consultas no ejecutadas masivamente.

Script:

- `scripts\due_diligence_best_iptv_2026.py`

## 8. Tavily V1

El primer buscador ejecuto:

- 120 consultas para el lote 1.
- 625 URLs unicas.
- 0 errores de Tavily tras consolidacion.

Se detecto un fallo de exportacion Excel por `IllegalCharacterError`. La correccion aplicada incluyo:

- limpieza de caracteres XML/Excel ilegales;
- serializacion segura de listas, diccionarios, sets y tuplas;
- limite de 32.000 caracteres por celda;
- validacion antes de exportar.

Archivos V1 principales:

- `research\output\best_iptv_2026\top50_external_evidence_20260713.csv`
- `research\output\best_iptv_2026\top50_external_evidence_20260713.xlsx`
- `research\output\best_iptv_2026\top50_external_evidence_20260713.json`
- `research\output\best_iptv_2026\top50_external_verification_report_20260713.md`

Carpeta de trabajo V1:

- `research\output\best_iptv_2026\tavily_due_diligence\`

## 9. Auditoria de calidad V1

Hechos confirmados:

- Marcas lote 1: 10
- URLs unicas contabilizadas: 625
- Pares marca-URL auditados: 950
- Precision global: 0.1863
- Ruido global: 0.6597
- Falsos positivos/irrelevantes: 430
- Homonimos: 41
- Duplicados: 236
- Dictamen: FAIL_REQUIRES_QUERY_REDESIGN
- Recomendacion: no ejecutar lote 2.

Precision por marca:

- Krooz TV: 0.3824
- Free Go TV: 0.0000
- Voco TV: 0.1549
- Terea TV: 0.2375
- Digita Line IPTV: 0.1299
- Eagle Cast TV: 0.2656
- IPTVGREAT: 0.1600
- Zorba IPTV: 0.1127
- Sonix IPTV: 0.1639
- DigitaLizard IPTV: 0.3390

Falso positivo confirmado de Voco/IHG:

- 18 evidencias de Voco TV clasificadas como HOMONYM.
- Dominios como `ihg.com`, `ihgplc.com` y `voco.dental`.
- Hoteles y odontologia no relacionados.

Archivos:

- `research\output\best_iptv_2026\batch1_quality_audit_20260713.csv`
- `research\output\best_iptv_2026\batch1_quality_audit_20260713.xlsx`
- `research\output\best_iptv_2026\batch1_quality_report_20260713.md`
- `research\output\best_iptv_2026\query_corrections_for_batches_2_5_20260713.json`

Script:

- `scripts\audit_tavily_batch1_quality.py`

## 10. Rediseno V2

El buscador V2 anadio:

- busquedas exactas por marca;
- aliases;
- terminos negativos globales y especificos;
- `relevance_score` de 0 a 100;
- aceptacion con score >= 50;
- ambiguas con score 30-49;
- rechazo con score < 30;
- deduplicacion por URL canonica, titulo y hash;
- modo dry-run;
- modo piloto;
- carpeta separada V2;
- consultas reducidas a 8 por marca;
- no reutilizacion automatica de resultados ruidosos V1.

Dry-run validado:

- 5 marcas.
- Maximo 40 consultas.
- 8 consultas por marca.
- No se llamo a Tavily.

Marcas piloto:

- Krooz TV
- Voco TV
- DigitaLizard IPTV
- Free Go TV
- Sonix IPTV

Archivos dry-run:

- `research\output\best_iptv_2026\query_plan_v2_preview_20260713.json`
- `research\output\best_iptv_2026\query_plan_v2_preview_20260713.md`

## 11. Problema 401 y causa raiz

Hechos confirmados:

- La prueba directa con `TavilyClient` funcionaba.
- El script devolvia 401 Unauthorized.
- Se comprobo que el script usaba llamada HTTP manual a `https://api.tavily.com/search`.
- Se sustituyo por el SDK oficial: `TavilyClient` y `client.search(...)`.
- La credencial de Tavily fue validada sin registrar ni exponer ningun valor secreto.
- Red y SDK funcionaban.
- El problema raiz era la llamada HTTP manual.
- El script fue corregido.
- `py_compile` fue correcto.

No incluir ninguna API key ni fragmentos secretos en el handoff ni en reportes.

## 12. Piloto V2 ejecutado correctamente

Hechos confirmados:

- Marcas piloto: 5
- Consultas ejecutadas: 40
- Consultas omitidas por checkpoint: 0
- Errores: 0
- Resultados brutos: 316
- Aceptados: 50
- Ambiguos: 5
- Rechazados: 261
- URLs unicas: 55

Metricas por marca:

| Marca | Total | Aceptadas | Ambiguas | Rechazadas | precision_proxy | noise_proxy | Dominio candidato | Confianza |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Krooz TV | 64 | 20 | 2 | 42 | 0.3438 | 0.6562 | `krooz-tvs.com` | HIGH |
| Voco TV | 60 | 9 | 0 | 51 | 0.1500 | 0.8500 | `vocotv.org` | HIGH |
| DigitaLizard IPTV | 64 | 9 | 3 | 52 | 0.1875 | 0.8125 | `digitalizard.app` | HIGH |
| Free Go TV | 64 | 0 | 0 | 64 | 0.0000 | 1.0000 | NOT_IDENTIFIED | NOT_IDENTIFIED |
| Sonix IPTV | 64 | 12 | 0 | 52 | 0.1875 | 0.8125 | `sonix-iptv.com` | HIGH |

Dictamen automatico actual:

- FAIL_REQUIRES_QUERY_REDESIGN

Recomendacion automatica actual:

- No autorizar lote 2.

Archivos V2 principales:

- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_evidence_20260713.csv`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_evidence_20260713.xlsx`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_evidence_20260713.json`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_quality_report_20260713.md`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\checkpoint.json`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\query_log.jsonl`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\raw_results.jsonl`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\accepted_results.jsonl`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\ambiguous_results.jsonl`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\rejected_results.jsonl`

Carpeta de trabajo V2:

- `research\output\best_iptv_2026\tavily_due_diligence_v2\`

## 13. Interpretacion metodologica resuelta

El indicador actual `precision_proxy` es metodologicamente cuestionable porque calcula:

```text
accepted / total_results
```

## 13A. Cierre posterior del micro-piloto de familias de dominio Voco TV (2026-07-15)

### Alcance y autorizacion excepcional

Se autorizo de forma excepcional un micro-piloto real, acotado a Voco TV, mediante el runner independiente `scripts\discover_iptv_domain_families.py`. Esta autorizacion no habilito el lote 2, no determino un dominio oficial y no amplio la autorizacion a otras marcas o consultas.

El run real que debe preservarse es:

- `research\output\best_iptv_2026\domain_family_discovery_voco_micro_pilot\run_20260715_023727\`

### Primera ejecucion real

- Se realizaron 12 llamadas Tavily.
- Nueve consultas terminaron correctamente y produjeron 72 resultados reales.
- `voco_df_01_identity_variants` fallo tres veces porque la consulta superaba el limite de 400 caracteres.
- Los 72 resultados iniciales quedaron preservados mediante checkpoint y artefactos del run.
- Ninguna consulta ya completada se repitio durante la reparacion posterior.

### Correccion offline y controles preventivos

- Q1 se redujo a 255 caracteres, conservando la intencion de identidad y variantes.
- Se incorporo un preflight obligatorio con maximo de 400 caracteres para todas las consultas.
- Los errores deterministas, incluidos query demasiado largo, parametros invalidos, autenticacion y solicitudes mal formadas, se clasifican como no reintentables.
- Se incorporo un modo repair exclusivo para una consulta explicitamente seleccionada en estado `FAILED`.
- El modo repair rechaza consultas `COMPLETED`, cambios incompatibles en otras consultas y selecciones ambiguas.
- La validacion offline paso con 87 de 87 autopruebas y 13 de 13 comprobaciones del plan.

### Reparacion real de Q1

- Consulta reparada: `voco_df_01_identity_variants`.
- Motivo: `QUERY_LENGTH_LIMIT`.
- Estado final: `COMPLETED`.
- Intentos anteriores: 3.
- Intentos de reparacion: 1 segun el checkpoint por consulta.
- Resultados nuevos: 8.
- Llamadas de red de la reparacion: 1.
- Llamadas Tavily de la reparacion: 1.
- Exit code: 0.
- Estado del run: `EXECUTION_COMPLETED`.
- `resumed_run`: true.
- `checkpoint_reused`: true.
- Resultados historicos: 72.
- Resultados combinados: 80.
- Duplicados eliminados durante resume: 0.
- Consultas discovery completadas: 8 de 8.
- Controles completados: 2 de 2.
- `technical_failure` final: false, respaldado por el estado completo de las diez consultas y `EXECUTION_COMPLETED`.

Caveat de serializacion: el campo superior `repair_attempts` del manifest permanece en 0, pero el checkpoint de Q1 registra `repair_attempts: 1` y `attempts: 1`. Para el intento de la consulta reparada, el checkpoint es la fuente granular autoritativa. No se modifico el run para corregir retrospectivamente este detalle.

### Metricas finales automaticas

- `raw_result_count_discovery`: 64.
- `known_domain_recovery_rate`: 0.375.
- `spontaneous_vocotv_ai_recovery`: FALSE.
- `new_candidate_domain_count`: 14.
- `relevant_domain_precision`: 0.13178294573643412 (13.18 %).
- `hotel_noise_rate`: 0.0.
- `dental_noise_rate`: 0.0.
- `linked_domain_count`: 110.
- `new_useful_relationship_count`: 186.
- `domain_family_expansion_index`: 25.0.
- `unresolved_identity_rate`: 0.0.
- `duplicate_rate`: 0.359375.
- Rendimiento util de Q1: 0.

### Veredictos y decision humana

- `SAFETY_VERDICT`: `SAFETY_PASS`.
- `DISCOVERY_VERDICT`: `DISCOVERY_PARTIAL_LOW_PRECISION`.
- El veredicto automatico `V3_UTILITY_PASS` no se acepta como conclusion definitiva.
- Dictamen operativo: `V3_UTILITY_REQUIRES_FINAL_AUDIT`.
- La precision de 13.18 %, la ausencia de recuperacion espontanea de `vocotv.ai` y el rendimiento util cero de Q1 impiden aprobar la utilidad real de V3 sin auditoria final.
- No existe un dominio oficial confirmado.
- El lote 2 permanece bloqueado.

### Artefactos y politica de versionado

- Auditoria offline existente: `research\output\best_iptv_2026\domain_family_discovery_voco_micro_pilot\audit_run_20260715_023727\`.
- Dry-run final: `research\output\best_iptv_2026\domain_family_discovery_voco_micro_pilot\dry_run_20260715_025410\`.
- La politica actual ignora todo `research\`; por tanto, el run real, la auditoria y el dry-run se preservan localmente y no se fuerzan en Git.
- Los artefactos versionables deliberados de este cierre son el runner y este handoff unico.
- El PID 28448 se considera un probable proceso huerfano y no fue terminado.
- La API key estaba disponible en el entorno para la ejecucion autorizada, pero su valor no se registro ni debe incluirse en ningun artefacto.
- Durante este cierre documental se realizaron cero llamadas Tavily, cero llamadas de red de investigacion y se consumieron cero creditos adicionales.

### Proxima tarea unica historica (completada por la auditoria final offline)

Estado histórico superado por la Sección 27 — Reorientación estratégica oficial BRAND-FIRST.

Auditar offline los 80 registros finales combinados y recalcular:

- candidatos realmente relevantes;
- relaciones realmente utiles;
- precision real;
- clasificacion operator, reseller, infrastructure y noise;
- utilidad real de V3;
- valor marginal de Q1.

No ejecutar nuevas consultas. No autorizar el lote 2 hasta completar esta auditoria final.

Ese calculo penalizaba los resultados correctamente rechazados. Por eso se creo una auditoria real sobre las evidencias retenidas que calcula:

- `acceptance_rate`
- `retained_rate`
- `accepted_precision`
- `false_acceptance_rate`
- `ambiguous_precision`
- `rejection_selectivity`

La pregunta correcta es:

```text
Cuantas de las 50 evidencias aceptadas son realmente correctas?
```

Esa auditoria ya fue ejecutada sin usar Tavily.

## Auditoría real de evidencias aceptadas V2

Hecho nuevo confirmado:

- `scripts\audit_pilot_v2_accepted_evidence.py`

Validaciones:

- `py_compile` correcto.
- Tavily no usado.
- Aceptadas auditadas: 50.
- Ambiguas auditadas: 5.

Metricas reales:

- `acceptance_rate`: 0.1582
- `retained_rate`: 0.1741
- `accepted_precision`: 0.1800
- `false_acceptance_rate`: 0.3600
- `ambiguous_precision`: 0.8000
- `rejection_selectivity`: 0.8238

Clasificacion de las 50 aceptadas:

- TRUE_POSITIVE_DIRECT: 8
- TRUE_POSITIVE_INDIRECT: 1
- UNRESOLVED: 23
- FALSE_POSITIVE_RESELLER: 17
- FALSE_POSITIVE_AFFILIATE: 1

Resultados por marca:

- Krooz TV:
  - `accepted_precision`: 0.2500
  - `false_acceptance_rate`: 0.2000
  - dominio candidato: `krooz-tvs.com`
  - estado: PROBABLE
- Voco TV:
  - `accepted_precision`: 0.2222
  - `false_acceptance_rate`: 0.2222
  - dominio candidato: `vocotv.org`
  - estado: PROBABLE
  - no conserva evidencia aceptada relacionada con IHG, hoteles u odontologia
- DigitaLizard IPTV:
  - `accepted_precision`: 0.0000
  - `false_acceptance_rate`: 0.6667
  - dominio candidato: `digitalizard.app`
  - estado: REJECTED
- Free Go TV:
  - `accepted_precision`: 0.0000
  - `false_acceptance_rate`: 0.0000
  - dominio: NOT_IDENTIFIED
- Sonix IPTV:
  - `accepted_precision`: 0.1667
  - `false_acceptance_rate`: 0.5000
  - dominio candidato: `sonix-iptv.com`
  - estado: PROBABLE

Dictamen global:

- FAIL

Decision vigente:

- No autorizar lote 2.
- No ejecutar nuevas consultas Tavily.
- Ajustar filtros de aceptacion y reglas de oficialidad.
- El principal error es aceptar revendedores y afiliados como evidencia valida.
- La alta tasa de rechazo no es el problema principal.
- El problema principal es la baja precision real del conjunto aceptado.

Archivos generados:

- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_20260714.csv`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_20260714.xlsx`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_report_20260714.md`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_filter_adjustments_20260714.json`

## Próxima tarea única

Estado histórico superado por la Sección 27 — Reorientación estratégica oficial BRAND-FIRST.

Modificar unicamente:

- `scripts\run_top50_tavily_due_diligence.py`

Objetivo:

Crear una version V3 de la logica de aceptacion y oficialidad, sin realizar nuevas consultas Tavily.

Usar como insumos:

- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_20260714.csv`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_report_20260714.md`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_filter_adjustments_20260714.json`

Requisitos conceptuales V3:

- separar `evidence_relevance`, `source_authority` y `officiality_score`;
- un revendedor no puede aceptarse como evidencia oficial;
- un afiliado no puede confirmar dominio oficial;
- una coincidencia exacta de marca no basta;
- una fuente sin identidad suficiente debe quedar UNRESOLVED;
- los revendedores deben clasificarse como RESELLER_SIGNAL;
- los afiliados deben clasificarse como PROMOTIONAL_SIGNAL;
- para TRUE_POSITIVE_DIRECT exigir dominio coherente, contenido atribuible y al menos una senal adicional de oficialidad;
- usar unicamente las 55 evidencias existentes para simular V3;
- no usar Tavily;
- no ejecutar lote 2.

Criterios minimos antes de autorizar un nuevo piloto:

- `accepted_precision` simulada >= 0.80
- `false_acceptance_rate` simulada <= 0.10
- cero revendedores aceptados como evidencia directa
- cero afiliados aceptados como fuente oficial
- `digitalizard.app` permanece REJECTED salvo nueva evidencia independiente
- Voco TV mantiene exclusiones de IHG, hoteles y odontologia

## Criterios para autorizar lote 2

- `accepted_precision` global >= 0.80
- `false_acceptance_rate` global <= 0.10
- ningun dominio oficial se confirma solo por coincidencia nominal
- Voco TV no conserva evidencia de IHG, hoteles u odontologia
- revendedores y rankings afiliados no se clasifican como fuente oficial

Estos criterios no se cumplieron en la auditoria real V2. Lote 2 no esta autorizado.

## 16. Salidas historicas de la auditoria V2

Ya fueron generadas:

- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_20260714.csv`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_20260714.xlsx`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_report_20260714.md`
- `research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_filter_adjustments_20260714.json`

## 17. Scripts existentes

- `scripts\research_best_iptv_2026.py`
- `scripts\clean_best_iptv_2026.py`
- `scripts\due_diligence_best_iptv_2026.py`
- `scripts\run_top50_tavily_due_diligence.py`
- `scripts\audit_tavily_batch1_quality.py`
- `scripts\audit_pilot_v2_accepted_evidence.py`

## 18. Script historico para modificar (SUPERADO)

Esta instruccion fue completada y reemplazada por el cierre BRAND-FIRST 1A.
No debe ejecutarse como tarea vigente.

- `scripts\run_top50_tavily_due_diligence.py`

## 19. Decisiones tecnicas historicas (NO VIGENTES COMO PROXIMA TAREA)

Estas decisiones describen la etapa V2/V3. Se preservan como trazabilidad y
quedan subordinadas a las secciones 27-29 y a los dos contratos permanentes.

- Usar SDK oficial Tavily.
- No usar requests manuales.
- No ejecutar lotes 2-5.
- No repetir consultas ya completadas.
- Preservar V1 y V2 separados.
- Mantener checkpoints.
- Conservar `raw_results`, `rejected_results`, `errors` y `query_log`.
- No modificar archivos originales.
- No exponer API keys.
- Ejecutar nuevas busquedas solo con autorizacion expresa.
- La auditoria real V2 ya fue completada.
- Redisenar V3 usando solo archivos existentes de auditoria.
- Simular V3 sobre las 55 evidencias existentes antes de autorizar nuevas consultas.

## 20. Riesgos abiertos

- Dominios candidatos podrian ser revendedores o clones.
- Coincidencia nominal no confirma dominio oficial.
- Rankings SEO pueden replicarse entre si.
- Una alta tasa de rechazo no fue el problema principal.
- La baja precision real del conjunto aceptado es el problema principal.
- La evidencia de licencias puede no ser publica.
- Ausencia de evidencia no equivale automaticamente a ilegalidad.
- Riesgo de homonimos.
- Riesgo confirmado de revendedores y afiliados aceptados como evidencia valida.

## 21. Estado operativo historico de la fase V2/V3

Estado historico: FASE 2 EN CURSO en el momento de esta seccion.

Piloto V2 tecnico completado.
Auditoria real completada.
Dictamen: FAIL.
Lote 2 no autorizado.

NO ejecutar nuevas consultas Tavily.

Siguiente paso unico historico (completado por V3/V4):

- redisenar la logica de aceptacion V3 sin usar Tavily.

## 22. Comandos utiles historicos (NO EJECUTAR COMO SIGUIENTE PASO)

Comandos de lectura y validacion, sin secretos:

```powershell
cd "C:\Proyectos\IPTV-Playlist-Builder-Premium"

python -m py_compile .\scripts\run_top50_tavily_due_diligence.py

python .\scripts\run_top50_tavily_due_diligence.py --pilot-brands "Krooz TV,Voco TV,DigitaLizard IPTV,Free Go TV,Sonix IPTV" --pause-seconds 1 --dry-run
```

## 23. Prompt historico para un nuevo hilo (SUPERADO POR LA SECCION 29)

Bloque listo para copiar y pegar:

```text
Continuamos el proyecto IPTV Playlist Builder Premium.

Lee primero:

docs/HANDOFF_2026-07-18_IPTV_BRAND_FIRST_MARKET_UNIVERSE_1B.md

No reproceses investigaciones.
No repitas consultas Tavily.
No ejecutes el lote 2.
No modifiques artefactos V1 o V2.

Estado confirmado:

- piloto V2 técnico completado;
- 40 consultas ejecutadas sin errores;
- 50 evidencias aceptadas y 5 ambiguas auditadas;
- accepted_precision real: 0.1800;
- false_acceptance_rate: 0.3600;
- 17 revendedores y 1 afiliado fueron aceptados incorrectamente;
- dictamen global: FAIL.

La siguiente tarea histórica, ya completada, era rediseñar la lógica de aceptación V3 en:

scripts\run_top50_tavily_due_diligence.py

Usa exclusivamente:

research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_20260714.csv
research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_accepted_audit_report_20260714.md
research\output\best_iptv_2026\tavily_due_diligence_v2\pilot_v2_filter_adjustments_20260714.json

No uses Tavily.

Simula la lógica V3 sobre las 55 evidencias existentes y demuestra:

- accepted_precision simulada >= 0.80;
- false_acceptance_rate simulada <= 0.10;
- cero revendedores aceptados como evidencia directa;
- cero afiliados aceptados como fuente oficial.

Solo después de esa validación se podrá considerar un nuevo piloto.
```

## 25. Auditoria final offline y Attribution-First Domain Family Method V4

### Auditoria final offline aceptada

La auditoria humana de los 80 resultados finales concluyo:

- dictamen: `FINAL_OFFLINE_AUDIT_REQUIRES_METHOD_REDESIGN`;
- 64 resultados discovery, 16 controles y 41 resultados discovery unicos auditables;
- 23 duplicados discovery;
- 14 candidatos automaticos, de los cuales solo uno era plausible antes de aplicar compuertas V4;
- 186 relaciones auditadas y cero relaciones fuertes o de apoyo atribuibles para identidad;
- `vocotv.ai` no fue recuperado espontaneamente;
- no se demostro propiedad comun ni existe un dominio oficial confirmado;
- lote 2 permanece bloqueado.

### Objetivo y resultado de V4

Se creo el evaluador independiente:

- `scripts\evaluate_domain_family_attribution_v4.py`
- pruebas: `tests\test_evaluate_domain_family_attribution_v4.py`
- replay local: `research\output\best_iptv_2026\domain_family_discovery_voco_micro_pilot\method_redesign_v4_replay_run_20260715_023727\`

V4 separa aparicion, actividad comercial, reseller, affiliate, reviews, infraestructura y controles de la identidad atribuible. Usa compuertas explicitas, deduplicacion e `independence_group`; no utiliza una suma opaca de puntos.

Dictamen aceptado: `ATTRIBUTION_METHOD_V4_OFFLINE_PASS`.

Este PASS valida la reproducibilidad, trazabilidad y capacidad de abstencion del metodo. No identifica un operador oficial.

### Metricas V4

- resultados discovery brutos: 64;
- resultados discovery unicos: 41;
- duplicados: 23/64 = 0.359375;
- precision relevante auditable: 18/41 = 0.43902439024390244;
- grupos independientes de evidencia atribuible: 20;
- relaciones atribuibles de identidad: 0/186;
- relaciones de infraestructura: 77;
- relaciones reseller: 2;
- relaciones genericas: 54;
- referencias externas/reviews: 22;
- ruido: 31;
- dominios no resueltos: 16/131;
- candidatos nuevos plausibles despues de compuertas: 0;
- operadores probables: 0;
- dominios relacionados probables: 0;
- dominios reseller: 9;
- leakage de identidad desde clases excluidas y controles: 0.

### Clasificaciones principales V4

- `vocotviptv.com`: `RESELLER`, confianza media. Tiene tres grupos de apoyo, actividad comercial y conflicto reseller, pero ninguna senal fuerte ni diversidad suficiente.
- `vocotvusa.net`: `RESELLER`, confianza media. Tiene actividad comercial y senales reseller, pero cero grupos fuertes o de apoyo que superen las compuertas.
- `vocotv.ai`: `UNRESOLVED`, confianza baja y `CONTROL_INDUCED`; cero recuperacion espontanea.
- `vocoiptv.com`: `UNRESOLVED`; actividad comercial sin atribucion de propiedad u operacion.

### Trazabilidad de los 20 grupos y compuertas fallidas

El replay conserva 2 grupos `IDENTITY_STRONG` y 18 `IDENTITY_SUPPORTING`. Una senal localmente atribuible no basta para resolver identidad. Cada uno de los 20 grupos fue reevaluado contra:

- presencia de al menos una senal fuerte por dominio;
- dos categorias atribuibles diferentes;
- dos grupos independientes;
- convergencia entre senales fuertes y de apoyo;
- ausencia de conflictos reseller, review u homonimo;
- relacion interdominio atribuible para `POSSIBLE_RELATED_DOMAIN`.

Los 20 grupos terminaron `FAIL_ABSTAIN`. Ningun dominio reunio simultaneamente una senal fuerte, dos categorias, independencia, convergencia y ausencia de conflicto. Ademas, ninguna de las 186 relaciones fue `IDENTITY_STRONG` o `IDENTITY_SUPPORTING`, por lo que ningun dominio supero la compuerta `POSSIBLE_RELATED_DOMAIN`.

Artefactos locales de trazabilidad:

- `identity_evidence_gate_trace_v4.csv`
- `identity_evidence_gate_trace_v4.md`
- `domain_identity_gap_matrix_v4.csv`
- `domain_identity_gap_matrix_v4.md`
- `targeted_external_verification_protocol_v1.md`

### Validacion e integridad

- `py_compile`: PASS sin residuos;
- `unittest`: 18/18 PASS;
- `pytest`: `NOT_AVAILABLE`; no se instalo por la restriccion offline;
- run original antes/despues: `286501151DB0DCFAA6383C0AB718B1F26250E7FA91D231C962EAB0B8B67A857C`;
- auditoria final antes/despues: `E67364695B94A18278823963F46C37A05661D551E78E4CF38B3DFB47EE394F8E`;
- Tavily, red de investigacion, credenciales y creditos: 0;
- ningun dominio oficial confirmado;
- lote 2 bloqueado.

### Caveats metodologicos

- La ausencia de evidencia no es evidencia negativa.
- `IDENTITY_STRONG` o `IDENTITY_SUPPORTING` describe una unidad aceptable para evaluar, no una conclusion suficiente por si sola.
- Repeticion, actividad comercial, palabra `official`, infraestructura, hosting, Cloudflare, procesadores de pago, reviews, controles o coincidencias tecnicas aisladas no demuestran propiedad.
- El protocolo externo V1 es solo diseno y no autoriza accesos ni consultas.

### Proxima tarea unica vigente

Estado histórico superado por la Sección 27 — Reorientación estratégica oficial BRAND-FIRST.

REVISAR Y, SOLO CON AUTORIZACION EXPRESA, EJECUTAR UNA VERIFICACION EXTERNA DIRIGIDA Y LIMITADA SOBRE LOS DOMINIOS SEMILLA PRIORIZADOS, UTILIZANDO EL PROTOCOLO V1 Y LAS COMPUERTAS V4.

## 26. Cierre forense definitivo TEV1 de la familia Voco (2026-07-16)

### Dictamen y alcance

Dictamen definitivo: `VOCO_DOMAIN_FAMILY_UNRESOLVED_AFTER_TARGETED_VERIFICATION`.

La evidencia confirma una superficie comercial VocoTV operativa en `vocotviptv.com`, pero no identifica de forma atribuible una entidad juridica, propietario, operador juridico, data controller, merchant, billing entity ni jurisdiccion. El dictamen no niega que el sitio opere; registra que no puede atribuirse juridicamente su operacion a una entidad determinada.

No se emitio `OFFICIAL_DOMAIN`, `CONFIRMED_OFFICIAL_DOMAIN` ni `VERIFIED_OWNER`.

### Cronologia completa

1. Adquisicion inicial: 12 consultas Tavily completadas produjeron 59 resultados internos; tres capturas HTTP originales quedaron preservadas. El consumo reconstruido fue 30 unidades.
2. Recuperacion forense offline: se reconstruyeron 62 filas normalizadas sin red, sin credenciales y sin modificar el run real.
3. Repair HTTP derivado: cuatro accesos logicos y ocho requests fisicos elevaron el consumo acumulado a 38/40. Se obtuvo una captura raiz HTTP 200; tres cadenas quedaron incompletas porque el limite impidio solicitar el tercer salto calculado.
4. Evaluacion combinada offline: integro 59 resultados Tavily, tres capturas originales y una captura raiz. Produjo 63 filas y priorizo solo Terms y Privacy para las dos unidades restantes.
5. Dos accesos finales: se solicitaron exactamente `https://www.vocotviptv.com/terms/` y `https://www.vocotviptv.com/privacy-policy/`; ambos devolvieron HTTP 200, sin redirects. Row IDs: `final_http_80ec9ac102d47aaa3171b849` y `final_http_1fa871718eaa215ec5a38519`.
6. Cierre final offline: integro las dos capturas sin red adicional y reevaluo las compuertas V4 sobre los cuatro dominios.

Presupuesto definitivo: 40/40; restante: 0. Se prohibe repetir las 12 consultas Tavily, repetir los dos accesos finales o seguir consumiendo red para la familia Voco.

### Evidencia final de Terms

- Titulo: `Terms & Conditions – VocoTV`; actualizacion declarada: 14 de septiembre de 2025.
- Presenta `VocoTV` como marca/etiqueta contractual y como proveedor del servicio, pero no nombra razon social, operador juridico, propietario, merchant, seller, registro empresarial, identificador tributario, domicilio ni billing entity.
- Contacto observado: WhatsApp `+212714633888`; el correo visible permanece como placeholder ofuscado.
- Billing: cobro anticipado y autorrenovacion con metodo no especificado. Reembolso delegado a `/refund-policy/`; procesador no nombrado.
- La clausula de ley aplicable conserva `{Your Business Country}`. Por tanto no existe jurisdiccion atribuible.
- El footer afirma `VocoTV © 2025`, señal de marca sin valor de identidad juridica fuerte.
- Conflictos/plantilla: metadatos usan `VocoTV.com` mientras el canonical usa `vocotviptv.com`; el HTML declara haber sido copiado de `tvplansiptvstore.com/terms.html`.
- Hash de contenido: `914519a584b3abfba16c23ba362ce011a5478c513676749f2184dc3c614de990`.

### Evidencia final de Privacy

- Titulo: `Privacy Policy – VocoTV`; actualizacion declarada: 14 de septiembre de 2025.
- No nombra data controller, data processor, entidad juridica, propietario, operador, DPO, persona de contacto, domicilio, pais ni jurisdiccion.
- Los pronombres `we` y `our`, y la marca VocoTV, no se trataron como entidad juridica.
- Bases declaradas: consentimiento, intereses legitimos y ejecucion contractual. Retencion generica ligada a fines declarados y obligaciones legales/fiscales/contables.
- Derechos declarados: acceso, rectificacion, supresion y opt-out. Contacto por WhatsApp `+212714633888`.
- Menciona un payment processor sin nombrarlo y Google Analytics como ejemplo de proveedor analitico. No identifica hosting provider ni billing entity.
- No contiene referencias explicitas a GDPR, CCPA o UK GDPR ni una clausula identificable de transferencias internacionales.
- Conflicto/plantilla: el HTML declara haber sido copiado de `tvplansiptvstore.com/privacy-policy.html`.
- Hash de contenido: `fb3e305648cad95d606488c6569967e4e6d987b1ec080935ac355e6dac99947c`.

### Integracion, relaciones y compuertas V4

La integracion final contiene 65 filas normalizadas, 43 URLs exactas observadas, 37 URLs canonicas y 45 grupos de independencia. El recuento directo del CSV combinado previo es 41 URLs exactas, aunque su metrica historica declaraba 40; al añadir las dos URLs finales con slash, el recuento fisico final es 43. Esta correccion de metrica no altera ninguna fuente.

Señales: 0 `IDENTITY_STRONG` y 1 `IDENTITY_SUPPORTING` heredada del contacto/raiz. Terms aporta `BRAND_SELF_ASSERTION` y `LEGAL_TEMPLATE_ONLY`; Privacy aporta `BRAND_SELF_ASSERTION` y `PRIVACY_TEMPLATE_ONLY`; WhatsApp es `CONTACT_ONLY`. Los placeholders, pronombres, copyright, structured data, analytics y dominio no fueron elevados a identidad fuerte.

Relacion VibeFlixTV observada: la captura raiz preserva enlaces de pricing/checkout a `wp.vibeflixtv.com`. Terms y Privacy no mencionan VibeFlixTV. El enlace demuestra una relacion de checkout, no propiedad comun, merchant identity, billing entity ni control compartido.

Resultado por dominio:

- `vocotviptv.com`: `UNRESOLVED`; existe superficie operativa de marca y evidencia first-party, pero no entidad nombrada, convergencia ni ausencia de conflictos materiales.
- `vocotvusa.net`: `UNRESOLVED`; sin nueva captura final y sin identidad atribuible suficiente.
- `vocotv.ai`: `UNRESOLVED`; sin nueva captura final y sin identidad atribuible suficiente.
- `vocoiptv.com`: `UNRESOLVED`; sin nueva captura final y sin identidad atribuible suficiente.

Compuertas: entidad nombrada FAIL; dos categorias independientes FAIL; convergencia FAIL; relacion atribuible dominio-entidad FAIL. Para `vocotviptv.com`, ausencia de conflictos materiales tambien FAIL por placeholder de jurisdiccion y procedencia de plantilla. En los otros tres dominios no se observo conflicto nuevo, pero las restantes compuertas fallan por insuficiencia.

### Integridad, outputs y runner

Fuentes inmutables, hashes recursivos antes y despues:

- run real: `394358D228C00EA7B52827D27EDF9741149020ECA3FDEC4270538C7C23861579`;
- recuperacion offline: `0040B91903F31537826CCB3D80959D2E9AD2E3F7491FFD96A05061007CA24B25`;
- repair HTTP: `DB656E2F983F8F583BF2909850AE146DA1C892067BB2699D4CF3A2ED4985BED6`;
- evaluacion combinada: `2861542AAD41DA3B99B7B69E1D6E969ECF5243DA7C71206ADAF24EDAD50ED8F6`;
- dos capturas finales: `3483C2D30999A25F9C0ED0EBE724007EA9E70F198610FCCC840FDF19E3FDA935`.

Todos permanecieron identicos. Output derivado final:

`research/output/best_iptv_2026/domain_family_discovery_voco_micro_pilot/targeted_external_verification_v1_final_offline_closure_20260716_002456/`

El directorio contiene los 21 artefactos forenses, CSV de señales/relaciones/compuertas, cuatro dossiers, reporte de cierre, protocolo reutilizable, metricas, manifiesto de integridad y validacion del runner.

Archivos versionables actuales:

- `scripts/run_targeted_external_verification_v1.py`;
- `tests/test_run_targeted_external_verification_v1.py`;
- `docs/HANDOFF_2026-07-18_IPTV_BRAND_FIRST_MARKET_UNIVERSE_1B.md`.

El runner ahora detecta localmente cualquier run hermano final completado a 40/40 antes de crear output o inicializar red. Esto bloquea la repeticion de los dos accesos finales. Se mantienen la omision de consultas Tavily ya completadas, contadores de requests fisicos separados de eventos de redirect, `supporting_row_ids` obligatorios y la prohibicion de clasificaciones oficiales.

Validacion offline: `py_compile` PASS; unittest focalizado 44/44 PASS; JSON 4/4, JSONL 8/8, CSV 10/10 y Markdown 7/7 PASS; 166 filas CSV con `supporting_row_ids` validas; escaneo de patrones de valores secretos con cero hallazgos. No se leyo `TAVILY_API_KEY`, no se hicieron llamadas Tavily, HTTP, DNS ni sockets, y no se modifico el PID protegido.

### Riesgos y metodo reutilizable

Riesgos cerrados: recuperacion de evidencia, dos capturas finales, contabilidad 40/40, repeticion accidental del acceso final, trazabilidad por row ID y abstencion V4.

Riesgos que permanecen: identidad juridica, controller, jurisdiccion, merchant/billing entity y naturaleza de la relacion VibeFlixTV siguen sin resolver. No deben abordarse con mas red en Voco bajo este presupuesto agotado.

Metodo para la siguiente familia: seleccionar desde corpus offline, congelar hashes, deduplicar sin perder procedencia, separar marca/contacto/plantilla/pago/infraestructura de identidad, exigir entidad nombrada + dos categorias independientes + convergencia + ausencia de conflicto + relacion dominio-entidad, y abstenerse si falla cualquier compuerta. Todo nuevo micro-piloto requiere presupuesto propio y autorizacion expresa.

### Proxima tarea unica: decision controlada, no autorizada

Estado histórico superado por la Sección 27 — Reorientación estratégica oficial BRAND-FIRST.

Elegir expresamente una sola alternativa; ninguna queda seleccionada ni autorizada por este handoff:

A. Seleccionar otra familia ya presente en el corpus offline.
B. Aplicar primero V4 offline a candidatos existentes.
C. Preparar un micro-piloto nuevo, limitado y separado, sujeto a autorizacion previa.

No abrir lote 2 ni ejecutar red como siguiente paso automatico.

## 27. Reorientación estratégica oficial BRAND-FIRST (2026-07-16)

Esta sección es la decisión estratégica autoritativa vigente. Prevalece sobre cualquier sección histórica denominada "Próxima tarea", "Próxima tarea única" o equivalente que aparezca anteriormente en este handoff. Las decisiones históricas se preservan como trazabilidad, pero las que se indican como suspendidas o reemplazadas no deben ejecutarse.

### 27.1 Decisión estratégica aprobada

El proyecto adopta oficialmente un enfoque **BRAND-FIRST**.

La marca comercial será la unidad primaria de descubrimiento, análisis de mercado y selección de semillas. Los dominios no originarán por sí solos familias empresariales: serán activos candidatos observados alrededor de una marca y deberán clasificarse posteriormente como operador, dominio relacionado, revendedor, afiliado, clon, aplicación, panel, checkout, infraestructura, ruido o no resuelto.

La entidad jurídica será una conclusión de atribución y no una premisa.

Orden conceptual vigente:

`FUENTE DE MERCADO → BRAND_MENTION → CANONICAL_BRAND → BRAND_SEED → PROVISIONAL_DOMAIN_CLUSTER → V4 ATTRIBUTION → ATTRIBUTED_BRAND_ECOSYSTEM → LEGAL_OPERATOR`, solo si existe evidencia suficiente.

Principios operativos:

- La marca organiza la investigación.
- La evidencia decide la atribución.
- El dominio es un activo candidato.
- La entidad jurídica es una conclusión posterior.

### 27.2 Corrección conceptual del hito anterior

El hito `V4_OFFLINE_CANDIDATE_PRIORITIZATION_COMPLETE` fue técnicamente reproducible y permanece versionado, pero su interpretación correcta es limitada.

No fue:

- una comparación entre 50 marcas;
- una priorización global del mercado IPTV;
- una selección entre 50 proveedores;
- una identificación de diez familias empresariales;
- una confirmación de diez operadores.

Fue:

- una priorización exploratoria de diez clústeres nominales de dominios;
- derivada principalmente de tres marcas raíz: DigitaLizard IPTV, Krooz TV y Sonix IPTV;
- construida mediante patrones nominales y evidencias del corpus local;
- sin identidad empresarial atribuida;
- sin dominio oficial confirmado;
- sin operador legal identificado.

El archivo `research/output/best_iptv_2026/tavily_due_diligence_v2/pilot_v2_accepted_audit_20260714.csv` contiene 50 filas de evidencia, pero únicamente cuatro valores `brand_name`:

- Krooz TV: 20 filas;
- Sonix IPTV: 12 filas;
- Voco TV: 9 filas;
- DigitaLizard IPTV: 9 filas.

La quinta marca del piloto fue Free Go TV, pero produjo cero evidencias aceptadas y por ello no aparece en ese CSV. Después de excluir Voco por su cierre definitivo, el análisis anterior quedó reducido a tres marcas raíz.

Las diez unidades del ranking anterior deben denominarse `PROVISIONAL_NOMINAL_DOMAIN_CLUSTERS` o, en español, **clústeres nominales provisionales de dominios**. No deben denominarse familias confirmadas.

### 27.3 Valor que se conserva del trabajo anterior

No se revierte ni se descarta:

- el corpus inicial;
- la limpieza de marcas;
- el Top 50 histórico;
- V1, V2 y V3;
- el método V4;
- el cierre forense Voco;
- los runners;
- las pruebas;
- los checkpoints;
- los `supporting_row_ids`;
- los inventarios de dominios;
- el plan de adopción de Tavily Agent Skills;
- el script de priorización de clústeres.

V4 se conserva como la capa downstream de atribución. La reorientación no invalida V4; corrige el momento en que debe aplicarse:

1. primero se descubre y prioriza la marca;
2. después se investiga su ecosistema de dominios;
3. finalmente se aplica V4.

### 27.4 Genealogía histórica que debe reconstruirse

Cadena histórica conocida:

- 42 consultas generales;
- 535 fuentes únicas;
- 1.035 nombres detectados;
- 757 registros depurados;
- 128 falsos positivos eliminados;
- 150 aliases fusionados;
- 692 registros clasificados como `PROVIDER`;
- Top 50 histórico;
- lote 1 de 10 marcas;
- piloto V2 de 5 marcas;
- 4 marcas con evidencias aceptadas;
- 3 marcas raíz después del cierre de Voco;
- 10 clústeres nominales provisionales.

Esta reducción debe auditarse para identificar:

- reglas de limpieza;
- aliases;
- exclusiones;
- calidad de fuentes;
- independencia de fuentes;
- duplicación SEO;
- sesgos geográficos;
- sesgos lingüísticos;
- sesgos por recurrencia;
- razones de ingreso o exclusión del Top 50.

### 27.5 Nueva taxonomía oficial

**BRAND_MENTION**: aparición literal de un nombre comercial en una fuente.

**CANONICAL_BRAND**: nombre normalizado de marca después de revisar ortografía, aliases y posibles homónimos.

**BRAND_SEED**: marca canónica seleccionada para investigación profunda.

**PROVISIONAL_DOMAIN_CLUSTER**: conjunto de dominios nominal o técnicamente relacionados con una marca, sin atribución demostrada.

**ATTRIBUTED_BRAND_ECOSYSTEM**: conjunto de dominios, aplicaciones, contactos, pagos y entidades cuya relación fue demostrada mediante evidencia suficiente.

**LEGAL_OPERATOR**: entidad jurídica atribuida a la operación solo cuando supera las compuertas metodológicas.

Estados de alias:

- `ALIAS_CONFIRMED`;
- `ALIAS_PROBABLE`;
- `ALIAS_NOMINAL_ONLY`;
- `POSSIBLE_IMPERSONATION`.

### 27.6 Separación de los dos sistemas metodológicos

**SISTEMA 1 — BRAND MARKET INTELLIGENCE**

Responde:

- qué marcas existen;
- en qué fuentes aparecen;
- con qué recurrencia;
- en cuántos grupos independientes;
- con qué vigencia;
- con qué cobertura geográfica y lingüística;
- cuáles merecen investigación profunda.

**SISTEMA 2 — BRAND ATTRIBUTION AND RESOLUTION**

Responde:

- qué dominios están relacionados;
- cuál puede ser operador;
- cuáles son revendedores;
- cuáles son clones o afiliados;
- qué aplicación, publisher o checkout aparece;
- qué entidad jurídica puede atribuirse;
- si debe emitirse `UNRESOLVED`.

V4 pertenece al Sistema 2. La próxima fase debe completar primero el Sistema 1.

### 27.7 Fuentes “Best IPTV 2026” y su uso correcto

Las páginas del tipo `Best IPTV Services 2026`, `Best IPTV Providers 2026`, `Top IPTV Subscriptions 2026` o `IPTV Services Review 2026` pueden utilizarse para descubrir marcas, pero no deben tratarse automáticamente como fuentes expertas, independientes o probatorias.

Debe separarse expresamente:

`valor para descubrir marcas ≠ valor para evaluar calidad ≠ valor para demostrar identidad ≠ valor para demostrar legalidad`.

Taxonomía futura de fuentes:

- Nivel A: publicación especializada con autoría y metodología;
- Nivel B: comunidad técnica, medio reconocido o foro con contexto;
- Nivel C: comparador o ranking con afiliación declarada;
- Nivel D: reseller, proveedor o contenido promocional;
- Nivel E: contenido copiado, spam o ruido.

Las fuentes C y D pueden generar candidatos, pero no elevar por sí solas reputación, oficialidad ni identidad.

### 27.8 Independencia de fuentes

Múltiples páginas no equivalen necesariamente a múltiples fuentes independientes. Las futuras auditorías deben detectar:

- textos idénticos;
- mismo orden de marcas;
- mismas tablas;
- mismos errores;
- mismo autor;
- misma empresa;
- misma red de dominios;
- mismo código de afiliado;
- mismo contacto;
- mismo template;
- republicaciones.

Una red de páginas relacionadas debe contarse como un solo `independence_group` cuando corresponda.

### 27.9 Reorientación de Tavily

Tavily se utilizará en dos etapas diferentes.

**ETAPA DE UNIVERSO DE MARCAS**

- Search para localizar fuentes y rankings;
- Map para descubrir secciones relevantes de sitios fuente;
- Extract para recuperar listas, tablas, metodología y marcas;
- Crawl bloqueado por defecto;
- Research bloqueado por defecto.

**ETAPA DE INVESTIGACIÓN DE UNA MARCA**

- Map del dominio candidato;
- revisión humana offline;
- Extract de páginas seleccionadas;
- Search únicamente para vacíos;
- V4 offline;
- decisión humana.

Tavily Agent Skills será una capa de adquisición y no una capa de atribución. V4 seguirá siendo la capa de atribución.

### 27.10 Créditos Tavily disponibles

Datos operativos registrados:

- plan mensual observado: 4.000 créditos;
- contador confirmado después de la prueba básica: 548/4000;
- la API funciona;
- la prueba consumió exactamente un crédito.

La disponibilidad de créditos no constituye autorización automática de consumo. Los créditos deben utilizarse con:

- presupuesto previo;
- human approval;
- ledger;
- deduplicación de consultas;
- hashes;
- checkpoints;
- raw evidence preservation;
- stop conditions;
- medición de valor informativo por crédito.

No se deben consumir créditos solamente porque están disponibles.

### 27.11 Decisiones suspendidas

Se suspende `V4-OFFLINE-FAMILY-CONSOLIDATION-1B`.

No se debe continuar consolidando Digitalizard o Krooz como siguiente tarea automática.

No se autoriza todavía:

- piloto Digitalizard;
- piloto Krooz;
- piloto Sonix;
- lote 2;
- instalación de Tavily Agent Skills;
- Tavily Crawl;
- Tavily Research;
- nuevas consultas;
- selección definitiva de una marca.

### 27.12 Roadmap aprobado en 2026-07-16 (HISTORICO; 1A YA COMPLETADA)

**BRAND-FIRST-MARKET-UNIVERSE-1A**: reconstrucción y auditoría completamente offline del universo histórico de marcas.

**BRAND-FIRST-MARKET-UNIVERSE-1B**: ampliación controlada del universo mediante Tavily, basada en fuentes, rankings, múltiples regiones e idiomas.

**BRAND-SEED-PRIORITIZATION-1C**: priorización de marcas canónicas para investigación profunda.

**BRAND-ATTRIBUTION-PILOT-1D**: investigación individual de una marca semilla mediante:

`Map → revisión humana → Extract → Search de vacíos → V4 → operador, reseller, clon o UNRESOLVED`.

### 27.13 Tarea historica 1A (COMPLETADA Y SUPERADA)

La tarea que era proxima en 2026-07-16 fue
`BRAND-FIRST-MARKET-UNIVERSE-1A`. Quedo completada, congelada, committeada y
pusheada en `cbc0ea5`; no debe ejecutarse de nuevo.

Objetivo: reconstruir completamente offline el universo histórico ya existente y hacer visible:

- los 1.035 nombres originales;
- los 757 registros depurados;
- los 692 `PROVIDER`;
- el Top 50 histórico;
- aliases;
- fuentes;
- recurrencia;
- independencia;
- exclusiones;
- criterios de selección;
- sesgos;
- trazabilidad.

No seleccionar todavía una marca para investigación externa.

### 27.14 Fuentes locales mínimas para 1A

- `research/output/best_iptv_2026/tavily_corpus_20260713_222351.json`
- `research/output/best_iptv_2026/tavily_corpus_20260713_222351.csv`
- `research/output/best_iptv_2026/brands_consolidated_20260713_222351.csv`
- `research/output/best_iptv_2026/brands_cleaned_20260713.csv`
- `research/output/best_iptv_2026/brands_rejected_20260713.csv`
- `research/output/best_iptv_2026/cleaning_report_20260713.md`
- `research/output/best_iptv_2026/top50_due_diligence_preliminary_20260713.csv`
- `research/output/best_iptv_2026/top50_due_diligence_preliminary_20260713.xlsx`
- `research/output/best_iptv_2026/top50_due_diligence_report_20260713.md`
- `research/output/best_iptv_2026/top50_query_plan_20260713.json`

### 27.15 Entregables de 1A (CREADOS; PLAN HISTORICO COMPLETADO)

Los siguientes se planificaron en esta seccion y despues fueron creados en el
run autoritativo `run_20260717_051437`:

1. `01_source_inventory.csv`
2. `02_raw_brand_mentions.csv`
3. `03_canonical_brand_universe.csv`
4. `04_brand_alias_map.csv`
5. `05_brand_exclusions.csv`
6. `06_provider_universe_692.csv`
7. `07_historical_top50.csv`
8. `08_top50_selection_trace.csv`
9. `09_source_quality_registry.csv`
10. `10_source_independence_groups.csv`
11. `11_brand_source_matrix.csv`
12. `12_brand_recurrence_metrics.csv`
13. `13_brand_seed_readiness.csv`
14. `14_top50_recalibrated_offline.csv`
15. `15_historical_vs_recalibrated_comparison.csv`
16. `16_market_universe_bias_report.md`
17. `17_brand_first_market_universe_report.md`
18. `18_integrity_manifest.json`
19. `19_runner_validation_report.md`

Artefactos versionables que fueron creados y versionados:

- `scripts/build_brand_first_market_universe.py`
- `tests/test_build_brand_first_market_universe.py`
- `docs/BRAND_FIRST_RESEARCH_METHOD.md`

Estos archivos existen, estan versionados y forman parte del commit de cierre
`cbc0ea5a874a9f94ece643cbe47dd5385ee705ec`. La frase historica que afirmaba
que no existian quedo superada por Git y el disco.

### 27.16 Restricciones historicas aplicadas a BRAND-FIRST-MARKET-UNIVERSE-1A

- cero Tavily;
- cero HTTP;
- cero DNS;
- cero sockets;
- cero credenciales;
- cero instalaciones;
- cero fuentes nuevas;
- no modificar runs históricos;
- no abrir lote 2;
- no investigar individualmente Digitalizard, Krooz o Sonix;
- no declarar dominios oficiales;
- no hacer commit ni push antes de revisión humana;
- preservar hashes antes y después;
- mantener `supporting_row_ids`;
- no modificar PID 28448.

### 27.17 Criterios historicos de aceptacion de 1A

Un PASS exige:

- inventariar todo el universo disponible;
- mostrar exactamente los 692 `PROVIDER`;
- listar exactamente el Top 50 histórico;
- rastrear cada marca a sus fuentes;
- diferenciar fuentes independientes y duplicadas;
- explicar aliases y exclusiones;
- reconstruir `1.035 → 757 → 692 → 50`;
- identificar sesgos;
- producir un ranking recalibrado offline;
- no seleccionar aún la próxima marca externa;
- preservar todos los artefactos fuente.

Dictámenes permitidos:

- `BRAND_FIRST_MARKET_UNIVERSE_OFFLINE_COMPLETE`
- `BRAND_FIRST_MARKET_UNIVERSE_REQUIRES_FIXES`
- `BRAND_FIRST_MARKET_UNIVERSE_INSUFFICIENT_TRACEABILITY`
- `BRAND_FIRST_MARKET_UNIVERSE_BLOCKED_BY_INTEGRITY`

### 27.18 Ejecucion y cierre verificado de 1A (2026-07-17)

Estado oficial verificado:

`BRAND_FIRST_MARKET_UNIVERSE_1A_OFFLINE_BASELINE_FROZEN_WITH_KNOWN_LIMITATIONS`

El documento versionado
`docs/BRAND_FIRST_1A_OFFLINE_BASELINE_CLOSURE.md`, el manifest, los reportes y
los hashes del run final confirman:

- genealogia: 1.035 menciones originales -> 757 registros canonicos depurados
  -> 692 `PROVIDER` historicos -> Top 50 historico exacto;
- 175 `PLAUSIBLE_BRAND`;
- 0 `TRACEABLE_FOR_FUTURE_PRIORITIZATION`;
- 0 adjudication-ready y 0 filas publicadas;
- 19 entregables;
- 151 pruebas registradas como PASS;
- 44.625 referencias validadas;
- 692 filas recomputadas sin errores;
- hashes de los 18 entregables no circulares verificados;
- hashes de los 10 insumos autoritativos sin cambios;
- cero red, cero seleccion externa y cero lectura de credenciales en 1A.

El cero significa exclusivamente: **cero marcas publicables bajo el corpus
local y los criterios FIX4**. No significa cero marcas reales, cero proveedores,
ilegalidad, mala calidad comercial, ranking definitivo, validacion externa ni
adjudicacion humana.

### 27.19 Inventario y cronologia real de runs 1A

Se encontraron fisicamente 12 runs, todos ignorados por Git y preservados:

| Etapa | Run | Estado |
|---|---|---|
| Inicial | `run_20260716_162527` | historico inicial |
| FIX1 intermedio | `run_20260716_172455` | intermedio |
| FIX1 intermedio | `run_20260716_173115` | intermedio |
| FIX1 | `run_20260716_173407` | cierre historico FIX1 |
| FIX2 intermedio | `run_20260716_210112` | intermedio |
| FIX2 | `run_20260716_210719` | cierre historico FIX2 |
| FIX3 intermedio | `run_20260717_001010` | intermedio |
| FIX3 intermedio | `run_20260717_001334` | intermedio |
| FIX3 | `run_20260717_002331` | cierre historico FIX3 |
| FIX4 intermedio | `run_20260717_050245` | intermedio |
| FIX4 intermedio | `run_20260717_050956` | intermedio |
| FIX4 | `run_20260717_051437` | autoritativo y congelado |

Cada run contiene 19 archivos, incluido manifest y reportes; no se encontraron
checkpoints en esta familia. El run autoritativo no lo es por ser el ultimo,
sino porque lo identifican el documento de cierre versionado, su manifest, las
validaciones PASS y el commit de cierre.

Hash logico FIX4 verificado:

`B2D3B232EE3FC0C345D48816B230A6A30D0DA67CC2ED53A4175B474D3FF40FF7`

El encabezado historico del reporte final aun dice `FIX3`; no cambia la
autoridad FIX4, que queda resuelta por el documento de cierre, el manifest, la
calibracion FIX4 presente en metodo/runner/tests y el hash logico congelado.

### 27.20 FIX5 cancelado y regla de reapertura

FIX5 fue iniciado y detenido antes de producir un run. El backup fisico existe
en:

`C:\Proyectos\IPTV-Playlist-Builder-Premium_FIX5_ABORTED_20260717_053940`

La comparacion SHA-256 confirma que:

- el runner actual difiere del runner abortado respaldado;
- el test actual coincide exactamente con el test respaldado;
- el metodo actual coincide exactamente con el metodo respaldado;
- no existe ningun run FIX5 bajo el inventario 1A;
- el hash logico final restaurado coincide con FIX4.

El documento de cierre registra que los cambios parciales se deshicieron con
la funcion Deshacer de Codex. La cifra visual aproximada `+230/-31`, la ausencia
historica de procesos Python justo despues de la interrupcion y la afirmacion de
que no se usaron `git reset`, `git restore` o `git clean` no pueden demostrarse
retrospectivamente mediante el arbol Git o los artefactos actuales; se conservan
solo como contexto reportado, no como prueba forense independiente.

FIX5 queda cancelado. No se autoriza FIX6 por perfeccionismo. 1A solo puede
reabrirse si aparece un defecto material demostrado que cambie decisiones o
resultados; no la reabren refactors, nombres, cosmetica, pruebas sin impacto u
optimizaciones innecesarias.

### 27.21 Cierre documental, commit y push de 1A

El commit `cbc0ea5a874a9f94ece643cbe47dd5385ee705ec`, mensaje
`research: freeze brand-first 1A offline baseline`, agrego exactamente:

- `docs/BRAND_FIRST_1A_OFFLINE_BASELINE_CLOSURE.md`;
- `docs/BRAND_FIRST_RESEARCH_METHOD.md`;
- `scripts/build_brand_first_market_universe.py`;
- `tests/test_build_brand_first_market_universe.py`.

Estado Git verificado el 2026-07-18 antes de esta actualizacion:

- rama: `main`;
- `HEAD`: `cbc0ea5a874a9f94ece643cbe47dd5385ee705ec`;
- `origin/main`: `cbc0ea5a874a9f94ece643cbe47dd5385ee705ec`;
- divergencia: `0 0`;
- working tree: limpio.

Este commit reemplaza a `dbff5ac` como baseline operativo, sin borrar ni
reescribir la historia anterior.

### 27.22 Apertura real de 1B y smoke test pendiente

Fase actual: `BRAND-FIRST-MARKET-UNIVERSE-1B`.

Subhito: `TAVILY-SMOKE-TEST-01`.

Objetivo: comprobar si Tavily Search aporta evidencia web nueva, actual,
diferenciada y trazable para una marca candidata y un control negativo, sin
crear ranking, aprobar proveedores, decidir legalidad ni reabrir 1A.

Consultas congeladas:

1. `"DigitaLizard IPTV" official website company`
2. `"DigitaLizard IPTV" reviews app reseller operator`
3. `"IPTV Smarters Pro" official website player application`
4. `"IPTV Smarters Pro" IPTV subscription provider`

Presupuesto: cuatro llamadas Search, `depth basic`, maximo cinco resultados por
consulta y maximo teorico de 20 resultados. Extract, Map, Crawl, Research y
Agent Skills permanecen fuera de alcance.

### 27.23 Intentos bloqueados de 1B preservados

El inventario fisico contiene dos runs bloqueados, no uno:

- `run_20260717_235220`;
- `run_20260718_000536`.

Ambos contienen cinco archivos y sus manifests/reportes declaran:

- `BRAND_FIRST_1B_TAVILY_SMOKE_TEST_BLOCKED_NO_API_KEY`;
- 0 busquedas;
- 0 llamadas consumidas;
- 0 resultados, URLs y dominios;
- cero archivos versionados modificados;
- cero commit y cero push.

No demuestran fallo de Tavily, clave invalida ni fallo de conectividad. Solo
demuestran que esas tareas Codex no recibieron `TAVILY_API_KEY` y aplicaron el
stop condition. Ninguno debe reutilizarse ni modificarse. El smoke test real
debe crear un run nuevo.

Los artefactos de `run_20260718_000536` verifican Python 3.12.10 de forma
indirecta mediante el manifest 1A, `tavily-cli 0.1.4`, la ayuda admitida por la
CLI y la ausencia de busquedas. La autenticacion `tvly --status` en una sesion
PowerShell y la conectividad a `api.tavily.com:443` fueron reportadas fuera del
repositorio, pero no tienen log o artefacto local verificable en este reality
check. Deben reconfirmarse en PowerShell antes de la ejecucion real, sin copiar
la clave a Codex.

## TAVILY EXECUTION CONTRACT — LECCIÓN APRENDIDA OBLIGATORIA

1. ChatGPT diseña objetivo, consultas, presupuesto, stop conditions, criterios
   de aceptacion y prompt para Codex.
2. Codex prepara offline runner, tests, dry-run, carpetas, manifest, ledger y
   comando PowerShell exacto.
3. Codex no ejecuta las llamadas Tavily reales.
4. Codex no necesita recibir `TAVILY_API_KEY`.
5. No se resuelve el flujo entregando la clave a Codex.
6. No se crea ni modifica por defecto
   `$env:USERPROFILE\.codex\.env`.
7. PowerShell ejecuta en una sesion donde `tvly --status` confirme
   autenticacion, con el comando exacto, presupuesto, limite de llamadas, stop
   conditions y persistencia de JSON/logs.
8. Despues, Codex audita offline los outputs y ChatGPT interpreta si SIRVIO,
   SIRVIO PARCIALMENTE o NO SIRVIO.
9. Si Codex informa `TAVILY_API_KEY NOT_AVAILABLE`, eso no invalida una clave
   existente en PowerShell ni autoriza reconfigurar secretos, crear `.env`,
   copiar la clave o cambiar este flujo.
10. Tavily real se ejecuta desde PowerShell. Codex prepara, pero no consume
    Tavily.

## HANDOFF REALITY-CHECK CONTRACT

1. El handoff es una guia de continuidad, no una base de datos
   autoautenticada.
2. Al comenzar cada hilo o sesion se verifican rama, HEAD, `origin/main`,
   divergencia, working tree, git log reciente, historial de archivos criticos,
   arbol versionado, archivos y runs reales, manifests, hashes, checkpoints y
   reportes.
3. Git y la evidencia material del disco prevalecen sobre afirmaciones
   desactualizadas del handoff.
4. Un nuevo hilo no ejecuta la proxima tarea descrita hasta confirmar que sigue
   pendiente.
5. Todo archivo descrito como planificado se comprueba en Git y disco.
6. Todo commit descrito como esperado se compara con HEAD y `origin/main`.
7. Todo run descrito como ultimo se contrasta con el inventario fisico, sus
   manifests y sus reportes; el timestamp no confiere autoridad.
8. Ante contradiccion, no se altera el proyecto para hacer coincidir el
   handoff: se corrige el handoff, se preserva el dato anterior como historico y
   se documenta la evidencia resolutiva.
9. La verificacion ocurre antes de modificar codigo, ejecutar runners, consumir
   Tavily, instalar paquetes, crear commits o continuar un hito.
10. Esta politica es permanente y debe aparecer en todos los handoffs futuros
    del proyecto.

### 27.24 Terminologia permanente

- VALIDACION AUTOMATICA
- AUDITORIA SEMANTICA ASISTIDA POR IA
- ADJUDICACION HUMANA
- APROBACION HUMANA FINAL

Una evaluacion realizada solo por IA no se denomina revision humana. No se
afirma que el usuario adjudico un resultado sin una decision expresa.

### 27.25 Estado global y proxima tarea unica

- preparacion metodologica: completada;
- cierre de 1A: completado;
- diseño del smoke test: completado;
- CLI y contrato PowerShell: preparados documentalmente; autenticacion y red
  deben reconfirmarse en la sesion de ejecucion;
- ejecucion Tavily real de 1B: pendiente;
- analisis de resultados: pendiente.

Proxima tarea unica:

`BRAND-FIRST-MARKET-UNIVERSE-1B / TAVILY-SMOKE-TEST-01 / OFFLINE-RUNNER-PREPARATION`

Codex debe preparar offline el runner auditable, presupuesto de cuatro llamadas,
stop conditions, JSON, CSV, reporte, ledger y manifest; validar `py_compile`,
tests y dry-run sin red; y entregar un unico comando PowerShell exacto. No debe
leer la API key ni ejecutar Tavily. El usuario ejecutara despues el comando en
PowerShell y Codex auditara el nuevo run offline.

Estimacion orientativa, no promesa: 10-20 minutos para preparar el runner, 2-10
minutos para ejecutar cuatro llamadas, 10-20 minutos para normalizar/revisar,
25-50 minutos totales para el smoke test y 45-90 minutos adicionales para un
micro-piloto posterior.

## 28. Estado operativo vigente para el próximo hilo

- repositorio verificado: `C:\Proyectos\IPTV-Playlist-Builder-Premium`;
- rama verificada antes de esta actualizacion: `main`;
- `HEAD` verificado: `cbc0ea5a874a9f94ece643cbe47dd5385ee705ec`;
- `origin/main` local verificado: `cbc0ea5a874a9f94ece643cbe47dd5385ee705ec`;
- divergencia verificada: `0 0`;
- working tree inicial: limpio;
- 1A: cerrada, congelada, committeada y pusheada;
- run 1A autoritativo: `run_20260717_051437`;
- hash logico FIX4: `B2D3B232EE3FC0C345D48816B230A6A30D0DA67CC2ED53A4175B474D3FF40FF7`;
- FIX5: cancelado; no existe run FIX5;
- fase actual: `BRAND-FIRST-MARKET-UNIVERSE-1B`;
- subhito: `TAVILY-SMOKE-TEST-01`;
- runs 1B bloqueados preservados: `run_20260717_235220` y
  `run_20260718_000536`;
- ejecucion Tavily real: pendiente;
- lugar de ejecucion Tavily real: PowerShell, no Codex;
- proxima tarea unica: `OFFLINE-RUNNER-PREPARATION`;
- lote 2, Extract, Map, Crawl, Research, ranking y adjudicacion de proveedor:
  no autorizados.

La referencia `origin/main` es la referencia local observada; este reality check
no uso `git fetch` ni red. Despues de esta actualizacion el working tree debe
contener exclusivamente este handoff modificado y permanecer sin commit hasta
revision humana.

## 29. Prompt vigente para iniciar el nuevo hilo

```text
Continuamos el proyecto IPTV Playlist Builder Premium.

Directorio:

C:\Proyectos\IPTV-Playlist-Builder-Premium

Lee primero como documento de continuidad, pero valida su vigencia contra Git
y el disco antes de tratarlo como fuente autoritativa:

docs\HANDOFF_2026-07-18_IPTV_BRAND_FIRST_MARKET_UNIVERSE_1B.md

REGLA DE INICIO OBLIGATORIA — HANDOFF REALITY-CHECK CONTRACT

No confies ciegamente en el handoff.

Antes de ejecutar cualquier tarea:

1. compara el handoff contra:
   - git log;
   - git status;
   - HEAD;
   - origin/main local;
   - divergencia;
   - historial de archivos criticos;
   - arbol Git;
   - archivos reales en disco;
   - runs reales;
   - manifests;
   - hashes;
   - checkpoints;
   - reportes;

2. confirma que la proxima tarea descrita sigue pendiente;

3. identifica trabajo realizado despues de la ultima actualizacion;

4. si hay contradiccion, Git y la evidencia material del disco prevalecen;
   no alteres el proyecto para hacer coincidir el handoff;

5. detente si la realidad no puede reconciliarse.

Dictamenes iniciales permitidos:

HANDOFF_REALITY_CHECK_PASS
HANDOFF_REALITY_CHECK_REQUIRES_UPDATE
HANDOFF_REALITY_CHECK_BLOCKED_BY_UNRECONCILED_STATE

FASE ACTUAL ESPERADA

BRAND-FIRST-MARKET-UNIVERSE-1B
TAVILY-SMOKE-TEST-01

BASELINE CERRADA

1A esta cerrada, committeada y pusheada.

Commit esperado, sujeto a verificacion:

cbc0ea5a874a9f94ece643cbe47dd5385ee705ec

Estado esperado, sujeto a verificacion:

- rama main;
- HEAD = origin/main local;
- divergencia 0 0;
- working tree limpio.

No reabrir 1A. No ejecutar FIX5 ni iniciar nuevos FIX offline.

RUN AUTORITATIVO 1A ESPERADO

run_20260717_051437

Hash logico esperado:

B2D3B232EE3FC0C345D48816B230A6A30D0DA67CC2ED53A4175B474D3FF40FF7

Interpretacion del cero: cero marcas publicables bajo el corpus local y FIX4.
No significa cero marcas reales en el mercado.

TAVILY EXECUTION CONTRACT — LECCION APRENDIDA OBLIGATORIA

ChatGPT diseña -> Codex prepara y valida offline -> Codex entrega comando
PowerShell -> PowerShell ejecuta Tavily -> Codex y ChatGPT auditan offline.

Codex no ejecuta Tavily real, no necesita TAVILY_API_KEY y no debe recibirla.
No crear ni modificar:

$env:USERPROFILE\.codex\.env

PowerShell debe reconfirmar `tvly --status` en la sesion que ejecutara el
comando. Los artefactos locales verifican Python 3.12.10 y tavily-cli 0.1.4,
pero este reality check no pudo verificar desde Git o disco la autenticacion ni
la conectividad reportadas fuera del repositorio.

RUNS BLOQUEADOS A PRESERVAR

run_20260717_235220
run_20260718_000536

Ambos tuvieron cero busquedas, cero llamadas y cero resultados porque las
tareas Codex no heredaron la variable. No reutilizarlos ni modificarlos.

SMOKE TEST REAL PENDIENTE

DigitaLizard IPTV:

Q1: "DigitaLizard IPTV" official website company
Q2: "DigitaLizard IPTV" reviews app reseller operator

IPTV Smarters Pro:

Q3: "IPTV Smarters Pro" official website player application
Q4: "IPTV Smarters Pro" IPTV subscription provider

Presupuesto:

- 4 llamadas Search;
- depth basic;
- maximo 5 resultados por consulta;
- sin Extract, Map, Crawl, Research ni Agent Skills.

PROXIMA TAREA UNICA

BRAND-FIRST-MARKET-UNIVERSE-1B
TAVILY-SMOKE-TEST-01
OFFLINE-RUNNER-PREPARATION

Codex debe:

- no usar red;
- no leer la API key;
- no ejecutar Tavily;
- preparar un runner offline auditable;
- implementar presupuesto y stop conditions;
- preparar JSON, CSV, reporte, ledger y manifest;
- validar py_compile, tests y dry-run sin red;
- entregar un unico comando PowerShell exacto;
- no hacer git add, commit ni push.

Despues, el usuario ejecutara el comando desde PowerShell y se auditara el run
nuevo offline.

No iniciar Extract, Map, Crawl, Research, investigacion de 692 marcas, ranking,
adjudicacion de proveedor ni declaraciones de legalidad.

Antes de cada prompt para Codex, indicar modelo, razonamiento, velocidad y
estado Max/Ultra.

Objetivo inmediato: ejecutar el smoke test real desde PowerShell y dictaminar
SIRVIO, SIRVIO PARCIALMENTE o NO SIRVIO.
```

## 30. Actualizacion autoritativa: preparacion offline del runner (2026-07-18)

Esta seccion es aditiva y prevalece sobre las referencias historicas de las
secciones 28 y 29 que presentaban `cbc0ea5...` como `HEAD` actual, describian
este handoff como modificado pero no committeado o mantenian
`OFFLINE-RUNNER-PREPARATION` como trabajo aun no iniciado. Esas afirmaciones
quedaron historicamente superadas por Git y por la preparacion offline aqui
documentada; no se borran para preservar la trazabilidad.

### 30.1 Reality check reconciliado

Dictamen de entrada: `HANDOFF_REALITY_CHECK_REQUIRES_UPDATE`.

- repositorio: `C:\Proyectos\IPTV-Playlist-Builder-Premium`;
- rama: `main`;
- `HEAD`: `6a8e129afc1a16c11e36d991f5bd708d9f9f7030`;
- `origin/main` local: `6a8e129afc1a16c11e36d991f5bd708d9f9f7030`;
- divergencia: `0 0`;
- working tree inicial de esta intervencion: limpio;
- blob del handoff en `HEAD` y en disco antes de editar:
  `6749aa8699806005235b13556c786aec80e659f2`;
- no existia un runner, test, dry-run persistido ni smoke test real posterior;
- la unica diferencia entre `cbc0ea5...` y `6a8e129...` era el rename/update
  documental de este handoff.

Reconciliacion de commits:

- `cbc0ea5a874a9f94ece643cbe47dd5385ee705ec` sigue siendo el baseline
  metodologico y versionado de cierre de 1A;
- `6a8e129afc1a16c11e36d991f5bd708d9f9f7030` es el commit documental de
  apertura y continuidad de 1B;
- el handoff cargado si fue committeado en `6a8e129...`; las frases anteriores
  que decian lo contrario son historia superada;
- esta nueva seccion 30 vuelve a dejar el handoff modificado localmente, sin
  `git add`, commit ni push, para revision humana junto con el runner y tests.

### 30.2 Runs protegidos y hashes antes de preparar

Algoritmo de hash de arbol: SHA-256 de la union ordenada de
`ruta_relativa|SHA256_ARCHIVO_EN_MAYUSCULAS`, separada por LF.

- FIX4 autoritativo `run_20260717_051437`: 19 archivos; hash de arbol
  `f21e2f16a7e67fc259328ff7d97520e02ab3bc3f6a33bb5223d3786f299f3b31`;
  su manifest y reporte conservan el hash logico
  `B2D3B232EE3FC0C345D48816B230A6A30D0DA67CC2ED53A4175B474D3FF40FF7`;
- bloqueado `run_20260717_235220`: 5 archivos; hash de arbol
  `2c5c1a050a79eed81255fa399843fc1ba24d7b41eb728d1b954d9c7451a910b3`;
- bloqueado `run_20260718_000536`: 5 archivos; hash de arbol
  `68edb29e1c39e97210b590b854f1b4cd3efbc33d1db8bb8e5277e8cffbed9f34`.

Los dos runs 1B bloqueados continuan declarando cero busquedas, cero llamadas,
cero resultados y bloqueo por falta de credencial en aquellas tareas Codex.
No fueron reutilizados ni modificados. Los tres hashes permanecieron identicos
despues de las pruebas offline.

### 30.3 Runner y pruebas preparados

Archivos nuevos:

- `scripts\run_brand_first_market_universe_1b_tavily_smoke_test_01.py`;
- `tests\test_run_brand_first_market_universe_1b_tavily_smoke_test_01.py`.

Ruta prevista para un run real nuevo:

`research\output\best_iptv_2026\brand_first_market_universe_1b\tavily_smoke_test_01\run_YYYYMMDD_HHMMSS`

Contrato congelado del runner:

- hash canonico del plan:
  `705f46e9873801e581039a6f116a7905524764ec91eb0465798fed2c989fd7fe`;
- cuatro consultas exactas, IDs, roles y orden congelados;
- Tavily Search mediante `tvly search`;
- `basic`, maximo 5 resultados, cuatro llamadas fisicas absolutas, una por
  consulta y cero reintentos;
- las opciones de answer, imagenes y raw content adicional no se pasan a la
  CLI;
- el intento se reserva y el checkpoint se reemplaza atomicamente antes de
  iniciar cada proceso;
- cero resultados completa la consulta sin reintento;
- autenticacion/permisos, presupuesto, plan, configuracion, JSON no
  estructurado, checkpoint ambiguo, run historico, hash incompatible o run
  hermano ya completado detienen el flujo;
- `--dry-run` no invoca backend, autenticacion ni entorno y no crea un run;
- solo `--execute` puede invocar Search; `--resume-run` es un modificador de
  `--execute` y valida plan, runner, configuracion, hashes e integridad antes de
  omitir consultas `COMPLETED`;
- los estados y artefactos requeridos se escriben de forma atomica;
- stderr y payloads se sanitizan antes de persistirlos;
- el runner no lee, comprueba, imprime ni administra `TAVILY_API_KEY`.

Backend local inspeccionado sin autenticacion ni red:

- version: `tavily-cli 0.1.4`;
- `tvly search` disponible;
- flags reales: `--json`, `--depth basic`, `--max-results 5`;
- answer, imagenes y raw content adicional quedan desactivados al omitir sus
  flags opcionales.

### 30.4 Validaciones offline

- `py_compile`: PASS para runner y tests, con `PYTHONPYCACHEPREFIX` dirigido a
  una ruta temporal externa al repositorio;
- `unittest` focalizado: 18/18 PASS;
- `pytest`: no disponible localmente; no se instalo;
- dry-run completo: `DRY_RUN_OFFLINE_PASS`;
- plan: cuatro consultas y presupuesto 4/4 validados;
- schemas con backend falso: 4 JSON, 3 JSONL, 2 CSV y 1 Markdown PASS;
- normalizacion reproducible, preservacion raw, ledger, checkpoint atomico,
  resume y stop conditions: PASS;
- escaneo de patrones de secretos: cero hallazgos persistidos;
- `__pycache__` del runner/tests dentro del repositorio: cero archivos nuevos;
- hashes protegidos antes/despues: identicos.

Durante esta preparacion: llamadas Tavily 0; HTTP 0; DNS 0; sockets 0;
credenciales leidas 0; creditos consumidos 0; commit/push 0. La ejecucion real
continua pendiente y debe originarse en PowerShell.

### 30.5 Unico comando PowerShell autorizado para la ejecucion futura

No ejecutar desde Codex. Copiar y pegar como un solo bloque en la sesion
PowerShell del usuario:

```powershell
& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    Set-Location -LiteralPath $projectRoot

    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'

    $tvlyCommand = Get-Command tvly -ErrorAction SilentlyContinue
    if (-not $tvlyCommand) {
        Write-Error 'Tavily CLI was not found. No search was executed.'
        exit 3
    }

    $statusErrorFile = [System.IO.Path]::GetTempFileName()

    try {
        $authenticationJson = & tvly --status --json 2> $statusErrorFile
        $authenticationExitCode = $LASTEXITCODE
        $authenticationText = ($authenticationJson | Out-String).Trim()

        if ($authenticationExitCode -ne 0) {
            Write-Error "Tavily authentication was not confirmed. Exit code: $authenticationExitCode. No search was executed."
            exit 3
        }

        if ([string]::IsNullOrWhiteSpace($authenticationText)) {
            Write-Error 'Tavily returned an empty authentication status. No search was executed.'
            exit 3
        }

        try {
            $null = $authenticationText | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            Write-Error 'Tavily returned an invalid JSON authentication status. No search was executed.'
            exit 3
        }
    }
    finally {
        Remove-Item -LiteralPath $statusErrorFile -Force -ErrorAction SilentlyContinue
    }

    $runnerOutput = & python -B .\scripts\run_brand_first_market_universe_1b_tavily_smoke_test_01.py --execute --approval-token 'BRAND-FIRST-1B-TAVILY-SMOKE-TEST-01' --execution-origin powershell 2>&1
    $runnerExitCode = $LASTEXITCODE
    $runPathLine = $runnerOutput | Where-Object { $_ -like 'RUN_DIR=*' } | Select-Object -Last 1
    $runnerOutput |
        Where-Object { $_ -notlike 'RUN_DIR=*' } |
        ForEach-Object { Write-Output $_ }

    if ($runPathLine) {
        Write-Output $runPathLine
    }
    else {
        Write-Error 'The runner did not report a run directory.'
    }
    exit $runnerExitCode
}
```

Estado al cerrar esta preparacion:

`OFFLINE_RUNNER_PREPARATION_COMPLETE_PENDING_POWERSHELL_EXECUTION`

### 30.6 Hotfix de la compuerta PowerShell (2026-07-18)

El bloque original de la seccion 30.5 comparaba texto con una expresion regular
que podia confundir un estado negativo terminado en `AVAILABLE` con una
confirmacion positiva. Ese bloque no debe ejecutarse y fue sustituido in situ
por la unica version vigente de la seccion 30.5.

La compuerta corregida comprueba primero que `tvly` exista, reserva stderr en un
archivo temporal, deja stdout separado, exige exit code cero, exige stdout no
vacio y obliga a que stdout sea JSON valido mediante `ConvertFrom-Json`. Ante
cualquier fallo sale con codigo 3 antes de alcanzar el runner. El `finally`
elimina el archivo temporal sin imprimir su contenido. No se modificaron las
consultas, presupuesto, approval token, origen PowerShell, manejo de `RUN_DIR`
ni propagacion del exit code del runner.

Validacion offline del hotfix: parser AST PowerShell con cero errores; un unico
comando `tvly --status --json`; stdout y stderr separados; un
`ConvertFrom-Json`; cuatro salidas `exit 3` dentro de tres ramas `if` y un
`catch`; runner situado despues del `finally`; expresion regular defectuosa
ausente; unittest focalizado 18/18 PASS; `py_compile` PASS. No se ejecuto el
bloque, Tavily, red ni ninguna lectura de credenciales.

Estado del hotfix:

`POWERSHELL_AUTH_GATE_HOTFIX_COMPLETE_PENDING_EXECUTION`

## 31. Auditoria offline posterior a la ejecucion real (2026-07-18)

Esta seccion es aditiva. Registra el unico run real del smoke test y prevalece
sobre el estado anterior que lo describia como pendiente. No autoriza repetir,
reanudar ni reparar retrospectivamente el run.

### 31.1 Reality check posterior

- repositorio: `C:\Proyectos\IPTV-Playlist-Builder-Premium`;
- rama: `main`;
- `HEAD` y `origin/main` local:
  `6a8e129afc1a16c11e36d991f5bd708d9f9f7030`;
- divergencia: `0 0`;
- cambios de preparacion preservados: este handoff modificado, runner untracked
  y tests untracked;
- unico run nuevo:
  `run_20260718_014913`;
- hermanos presentes: solo los bloqueados historicos
  `run_20260717_235220` y `run_20260718_000536`;
- el usuario ejecuto una sola vez el bloque PowerShell autorizado;
- el error interactivo posterior que trato `else` como comando independiente
  ocurrio al introducir el bloque linea por linea, despues de que el runner
  devolviera `RUN_DIR`; no es un segundo run ni la causa del estado interno.

### 31.2 Congelacion inicial del run

- archivos: 10;
- bytes totales: 55,613;
- hash SHA-256 de arbol:
  `734cd73bd74d8c5c344e6b9446c7d3d00bf0b21f3062e54dc63e0cd108ced1d3`;
- runner actual y registrado:
  `03f4cb8f9fcf5ec3683e94fe722a4fc90ada4c0404ee5e3df17a032610d14fd2`;
- hash canonico del plan:
  `705f46e9873801e581039a6f116a7905524764ec91eb0465798fed2c989fd7fe`;
- hash del archivo `query_plan.json`:
  `f11cd6cfdd282f58527900bb6748ed804b9ad2b14795774865c43ca8cb955b19`;
- hash del bloque PowerShell documentado:
  `d1a9fae2d702c533e1a8fd633d1f1458bf1888e7f73c4979199a0e677a0efd20`.

Hashes de arbol protegidos:

- FIX4 `run_20260717_051437`:
  `f21e2f16a7e67fc259328ff7d97520e02ab3bc3f6a33bb5223d3786f299f3b31`;
- bloqueado `run_20260717_235220`:
  `2c5c1a050a79eed81255fa399843fc1ba24d7b41eb728d1b954d9c7451a910b3`;
- bloqueado `run_20260718_000536`:
  `68edb29e1c39e97210b590b854f1b4cd3efbc33d1db8bb8e5277e8cffbed9f34`.

### 31.3 Inventario material

| Artefacto | Bytes | Registros | SHA-256 |
|---|---:|---:|---|
| `query_plan.json` | 1,648 | 1 plan / 4 consultas | `f11cd6cfdd282f58527900bb6748ed804b9ad2b14795774865c43ca8cb955b19` |
| `manifest.json` | 3,054 | 1 objeto | `cb6b4edeefa2e287240ad304ce0ec035e410f511877ddd1337df77713fa7e4e6` |
| `checkpoint.json` | 2,042 | 1 objeto / 4 estados | `eaffaf93d96cb633e6d741e36c5af0a669d3daac317f1cad48d80b8b9e5d8f05` |
| `query_ledger.jsonl` | 1,546 | 3 intentos | `6534f24907cb9f2afd9b8f062fbfdcf3b3ad927e6cc7abd999bf3f3e4fc9e2a0` |
| `raw_results.jsonl` | 13,120 | 2 envelopes / 10 resultados | `b86751d975e840c39283070085146e314a6ca31f3a61dd9bd086b215432867fd` |
| `normalized_results.csv` | 14,498 | 10 filas | `fa0166fe987df1483ff9b51248b2e8cb0192cc3bc88c4ee2c152331ac2b6b3d2` |
| `domain_summary.csv` | 1,045 | 8 dominios | `b0c6da90cea1f547e59f7e59bcbe0ca642ae9861eade92da60ad3cf648a9ba5b` |
| `errors.jsonl` | 3,255 | 1 error | `d50046a6e1fde9445168c84cdcf89f73a5ac860ef295b6de8eccb89b8fa4e358` |
| `smoke_test_report.md` | 910 | 1 reporte | `959e066d09e6591f6415efea416609d714553f504e7c14466e973f239e41b33b` |
| `integrity_manifest.json` | 14,495 | 9 hashes no circulares | `22f6ac4bbb330c66d931c7151505543960a6977b85d9f35f9f921cec66b1840f` |

Todos existen y sus formatos JSON, JSONL, CSV o Markdown son validos.

### 31.4 Estado tecnico reconstruido

- run ID: `run_20260718_014913`;
- estado final: `FAILED_TECHNICAL`;
- creado: `2026-07-18T05:49:13.828630+00:00`;
- actualizado: `2026-07-18T05:49:21.135060+00:00`;
- el schema no guarda `started_at` ni `finished_at` a nivel run;
- ventana reconstruida desde ledger:
  `2026-07-18T05:49:13.997854+00:00` a
  `2026-07-18T05:49:21.105621+00:00`;
- backend: `tvly-cli-search`, `tavily-cli 0.1.4`;
- origen disponible: `originated_from_powershell=true`;
- presupuesto: 4;
- llamadas reservadas: 3;
- llamadas fisicas realizadas: 3;
- llamadas restantes: 1;
- `COMPLETED`: 2;
- `FAILED`: 1;
- `BLOCKED`: 0;
- `PENDING`: 1;
- retries: 0;
- consultas repetidas: 0;
- maximo de una reserva por consulta: respetado;
- presupuesto absoluto: respetado.

| Secuencia | Query ID | Estado | Intentos | Llamada | Exit | Resultados preservados |
|---:|---|---|---:|---:|---:|---:|
| 1 | `digitalizard_q1_official_company` | `COMPLETED` | 1 | 1 | 0 | 5 |
| 2 | `digitalizard_q2_reviews_reseller_operator` | `COMPLETED` | 1 | 2 | 0 | 5 |
| 3 | `smarters_q3_official_player_application` | `FAILED` | 1 | 3 | 1 | 0 |
| 4 | `smarters_q4_subscription_provider` | `PENDING` | 0 | - | - | 0 |

Manifest, checkpoint y reconstruccion del ledger coinciden: 3 llamadas, dos
completadas, una fallida y 10 resultados. Q3 fallo dentro de la CLI al serializar
un caracter `U+1F4FA` bajo CP1252 (`UnicodeEncodeError`); no fue error de
autenticacion, permisos o parsing del runner. La llamada fisica ya habia sido
intentada, pero no quedo respuesta raw preservada. Q4 nunca fue llamada.

### 31.5 Metricas de resultados preservados

- resultados brutos embebidos: 10;
- resultados normalizados: 10;
- `BRAND_CANDIDATE`: 10;
- `NEGATIVE_CONTROL`: 0;
- URLs exactas unicas: 9;
- URLs canonicas unicas: 9;
- duplicados exactos: 1;
- duplicados canonicos: 1;
- hostnames: 8;
- dominios registrables: 8;
- sin URL, titulo, snippet o score: 0 en cada campo;
- score minimo: `0.46147847`;
- score maximo: `0.76554126`;
- score promedio: `0.613150255`;
- interseccion de dominios entre Q1 y Q2: `digitalizard.app`;
- interseccion candidato/control: no medible porque el control conserva cero
  resultados.

Distribucion mecanica: `digitalizard.app` 2; `trustpilot.com` 2; y una fila
cada uno para `digitalizard.io`, `digitalizard-iptv.com`,
`digitallizardiptv.io`, `digital-lizard-iptv.com`, `digitalizard.com` y
`digitalizard.eu`.

Valor marginal: llamada 1 aporto 5 URLs; llamada 2 aporto 5 filas y 4 URLs
canonicas nuevas frente a Q1; llamada 3 aporto cero evidencia preservada por el
fallo tecnico; la llamada 4 no existio. Promedio: 3.33 filas normalizadas por
llamada fisica realizada, o 5 por llamada completada.

### 31.6 Trazabilidad e integridad

- plan congelado, orden, IDs y texto: PASS;
- integrity manifest y sus 9 archivos no circulares: PASS;
- hashes de envelopes raw: 2/2 PASS;
- IDs raw estables: 2/2 PASS;
- hashes de filas normalizadas contra el item raw por rank: 10/10 PASS;
- IDs normalizados estables: 10/10 PASS;
- URLs canonicas reproducidas: 10/10 PASS;
- query IDs de raw, normalized y ledger contenidos en el plan: PASS;
- referencias ledger a raw existentes: 2/2 PASS;
- IDs raw duplicados: 0;
- IDs normalizados duplicados: 0;
- hallazgos de secretos: 0;
- stderr sensible o headers de autorizacion persistidos: 0;
- consultas adicionales: 0;
- Extract, Map, Crawl, Research o Agent Skills: 0.

La unica fila de errores contiene un traceback tecnico sanitizado de la CLI y
no contiene credenciales.

### 31.7 Auditoria semantica offline

DigitaLizard ya existia nominalmente en 1A con estado
`REQUIRES_SOURCE_REVIEW` y concentracion promocional alta. El run aporta ocho
URLs canonicas nuevas de las nueve unicas; la URL base de Trustpilot para la
variante `digitallizard.com` ya estaba en el registro 1A.

Q1 recupero cinco superficies plausiblemente relacionadas y autoafirmadas como
servicios de suscripcion. Son `PLAUSIBLY_RELEVANT`,
`FIRST_PARTY_SELF_ASSERTION` y `SUBSCRIPTION_PROVIDER_CLAIM`, pero no prueban
identidad comun ni oficialidad:

- `norm_54196b8dc1be8ea352ba530d`;
- `norm_b0e797ac2d2c67dba7433802`;
- `norm_c5d59813cd6d553302fe18e8`;
- `norm_43cb687a330b565c2ef96d92`;
- `norm_3415776163f12d92dd9534b0`.

La multiplicidad de dominios y variantes de spelling mantiene una relacion
`UNRESOLVED` y riesgo `HOMONYM_OR_NOISE`; no permite elevar una autoafirmacion
a identidad demostrada.

Q2 aporto informacion diferente: dos referencias de reviews en Trustpilot,
una repeticion de la superficie `.app`, un blog con `RESELLER_SIGNAL` y otra
superficie autoafirmada `.eu`:

- `norm_53c106fd147380bbbb8500a5` y
  `norm_568de049333f5a76834b0e80`: `INDEPENDENT_REFERENCE` y
  `REVIEW_OR_RANKING`, con valor limitado para identidad;
- `norm_e9b86942010c01bb4e8a97bd`: repeticion
  `FIRST_PARTY_SELF_ASSERTION`;
- `norm_66a8fd61ab7c96d1baa96628`: `RESELLER_SIGNAL`, sin demostrar que la
  entidad sea el reseller;
- `norm_73a3319a859c90501f17aaee`: `FIRST_PARTY_SELF_ASSERTION` y
  `SUBSCRIPTION_PROVIDER_CLAIM`.

No se preservo evidencia de Q3 y Q4 no se ejecuto. Por tanto no puede evaluarse
si el control recuperaba correctamente `PLAYER_APPLICATION`, si confundia
player con proveedor ni si media precision conceptual. El control negativo no
funciono como instrumento auditable en este run.

### 31.8 Valor informativo, dictamen y continuidad

El smoke test demostro que `Search/basic/max_results=5` puede descubrir
superficies nuevas y trazables para la marca candidata. La relevancia topical
de las diez filas preservadas es alta, pero la precision de identidad sigue
sin resolver, predomina la autoafirmacion y falta por completo el control
negativo. Cuatro llamadas habrian sido suficientes para la pregunta tecnica,
pero solo dos completaron y tres fueron intentadas.

No quedo demostrada oficialidad, operador, legalidad, legitimidad, calidad de
proveedor ni diferenciacion candidato/control.

Dictamen del smoke test:

`SIRVIO_PARCIALMENTE`

Decision de continuidad:

`B. HACER UN FIX OFFLINE DEL RUNNER, SIN NUEVAS LLAMADAS.`

El fix debe estudiar el fallo de encoding CP1252/UTF-8 y validarse con mocks o
fixtures Unicode. No autoriza reanudar este run, repetir Q3, ejecutar Q4, crear
otro run, consumir la llamada restante ni iniciar 1B controlado.

### 31.9 Estado de cierre

- ejecuciones del run: 1;
- repeticion o resume: 0;
- llamadas Tavily adicionales durante la auditoria: 0;
- HTTP, DNS o sockets adicionales: 0;
- credenciales leidas: 0;
- creditos adicionales: 0;
- commit/push: 0.

Dictamen tecnico de auditoria:

`POST_EXECUTION_OFFLINE_AUDIT_COMPLETE`

## 32. Fix offline de Unicode en Windows (2026-07-18)

Esta seccion es aditiva y documenta `WINDOWS-UTF8-OFFLINE-FIX-01`. No cambia
el dictamen semantico del run real, no completa el smoke test y no autoriza
ejecutar ni reanudar consultas.

### 32.1 Causa y estado preservado

El runner lanzaba `tvly` mediante `subprocess.run` con stdout y stderr
capturados como texto, pero sin `encoding` ni `errors` explicitos. En Windows,
el proceso Python de `tavily-cli 0.1.4` escribia hacia un pipe y selecciono
CP1252. Al intentar emitir el emoji U+1F4FA durante Q3, la CLI lanzo
`UnicodeEncodeError` antes de producir un documento JSON completo. Cambiar
solamente la pagina de codigos de la consola no garantiza el encoding de un
pipe de Python.

El runner preservo correctamente un unico intento fallido, el exit code y el
traceback tecnico sanitizado. El estado historico permanece:

- Q1: `COMPLETED`, 5 resultados;
- Q2: `COMPLETED`, 5 resultados;
- Q3: `FAILED`, un solo intento y sin evidencia JSON completa;
- Q4: `PENDING` y nunca ejecutada;
- retries: 0;
- fallo de autenticacion o permisos: no;
- dictamen: `SIRVIO_PARCIALMENTE`;
- decision: `B. HACER UN FIX OFFLINE DEL RUNNER, SIN NUEVAS LLAMADAS.`

### 32.2 Correccion minima aplicada

El camino controlado que invoca `tvly` ahora fuerza de manera temporal y no
secreta `PYTHONUTF8=1` y `PYTHONIOENCODING=utf-8`. Conserva la herencia normal
del proceso mediante `env=None`: no copia, enumera, imprime ni persiste el
entorno. Solo consulta, sustituye y restaura esos dos nombres no sensibles.

La captura usa bytes (`text=False`) y stdout/stderr se decodifican
explicitamente como UTF-8 estricto. El JSON Unicode valido se conserva sin
reemplazos. Un byte invalido genera `TVLY_OUTPUT_DECODE_ERROR`, queda
sanitizado y falla en el primer intento sin retry. El manifest solo registra
el contrato no sensible de encoding, nunca valores del entorno.

El bloque PowerShell vigente de la seccion 30.5 se sincronizo con el generado
por el runner. Es una unica unidad `& { ... }`, establece las dos defensas
UTF-8 antes de la compuerta, mantiene `tvly --status --json`, el token de
aprobacion, `--execution-origin powershell`, `RUN_DIR` y la propagacion del
exit code. Esta actualizacion no ejecuto el bloque.

### 32.3 Pruebas y validacion exclusivamente offline

El conjunto focalizado contiene 23 pruebas y cubre ASCII, JSON UTF-8 con
emoji, espanol, guion largo, griego y CJK; stderr Unicode; bytes fragmentados;
stdout vacio; JSON invalido; exit code no cero; autenticacion simulada fallida;
ausencia de retry; persistencia Unicode en raw y CSV; hashes e IDs
reproducibles; entorno falso no filtrado; schemas; secretos; y reproduccion
del fallo historico CP1252. La ejecucion falsa completa procesa exactamente
las cuatro consultas con cuatro llamadas simuladas.

Resultados: `py_compile` PASS; unittest 23/23 PASS; pytest no instalado y no
instalado por esta tarea; parser AST PowerShell sin errores; dry-run PASS con
cero llamadas, cero autenticaciones y cero lecturas de entorno; validaciones
JSON, JSONL, CSV y Markdown PASS; escaneo de secretos sin hallazgos; y
`git diff --check` PASS.

### 32.4 Hashes e inmutabilidad

Los hashes SHA-256 de arbol iniciales y finales de los runs son identicos:

- `run_20260718_014913`:
  `734cd73bd74d8c5c344e6b9446c7d3d00bf0b21f3062e54dc63e0cd108ced1d3`;
- `run_20260717_051437`:
  `f21e2f16a7e67fc259328ff7d97520e02ab3bc3f6a33bb5223d3786f299f3b31`;
- `run_20260717_235220`:
  `2c5c1a050a79eed81255fa399843fc1ba24d7b41eb728d1b954d9c7451a910b3`;
- `run_20260718_000536`:
  `68edb29e1c39e97210b590b854f1b4cd3efbc33d1db8bb8e5277e8cffbed9f34`.

Hashes de archivos de trabajo antes y despues del fix:

- runner: `03f4cb8f9fcf5ec3683e94fe722a4fc90ada4c0404ee5e3df17a032610d14fd2`
  -> `b09a6e7d143a4d03255600d4f688a0d2855d6676e98cef801d0aef9e69caf939`;
- pruebas: `9edd3f53071de35b05a9aa13a5be47da0a2559869a23a125664baa293de6687a`
  -> `71c0cb8b185e0c3fec65e7c62c73e44e5cd9336e7932479296747ee6cf338ec5`;
- handoff antes del fix:
  `542d326211c2b3bd41e86c4b026701252b3974aed40d0ec8b8b75c14a0557312`.

El hash final del propio handoff se registra en el cierre externo, porque
incluirlo dentro del mismo archivo volveria a modificarlo.

### 32.5 Cierre y limite de autorizacion

Durante esta tarea: Tavily 0; HTTP 0; DNS 0; sockets 0; credenciales leidas o
enumeradas 0; creditos 0; commit/push 0. El run real y los historicos quedaron
byte-identicos. No se autoriza `--resume-run`, repetir Q3, ejecutar Q4, crear un
nuevo run ni iniciar 1B controlado. El smoke test continua incompleto y sujeto
a revision humana.

Dictamen tecnico:

`WINDOWS_UTF8_OFFLINE_FIX_COMPLETE_PENDING_HUMAN_REVIEW`

## 33. Preparacion del runner API de completitud (2026-07-18)

Esta seccion es aditiva y registra la decision humana expresa posterior al fix
UTF-8 de la CLI. La estrategia vigente abandona cualquier reparacion adicional
de `tavily-cli`: la futura completitud se realizara mediante un runner separado
que usa el SDK oficial `tavily-python`. Codex solo preparo y valido ese camino
offline; no ejecuto Tavily ni leyo credenciales.

### 33.1 Autorizacion y limites

El run parcial
`research/output/best_iptv_2026/brand_first_market_universe_1b/tavily_smoke_test_01/run_20260718_014913`
permanece inmutable con SHA-256 de arbol
`734cd73bd74d8c5c344e6b9446c7d3d00bf0b21f3062e54dc63e0cd108ced1d3`.
Q1 y Q2 ya son validas y no forman parte del runner nuevo.

La autorizacion futura queda limitada a:

- Q3 `smarters_q3_official_player_application_api_recovery`: una unica
  repeticion tecnica por perdida de la respuesta CLI bajo CP1252;
- Q4 `smarters_q4_subscription_provider_api_completion`: primera ejecucion;
- presupuesto absoluto: maximo 2 llamadas Search;
- una llamada por consulta y cero retries;
- `search_depth="basic"`, `max_results=5`, `auto_parameters=False`,
  `include_answer=False`, `include_images=False` e
  `include_raw_content=False`;
- sin Extract, Map, Crawl, Research ni Agent Skills.

Esta autorizacion no permite modificar o reanudar el run parcial, repetir Q1 o
Q2, ampliar consultas ni superar dos llamadas.

### 33.2 Runner separado y credenciales

El runner nuevo es
`scripts/run_brand_first_1b_tavily_api_completion.py`. Crea exclusivamente un
run nuevo bajo
`research/output/best_iptv_2026/brand_first_market_universe_1b/tavily_smoke_test_01_api_completion/run_<timestamp>`
y no ofrece modo resume.

El SDK local `tavily-python 0.7.26` esta disponible y su `TavilyClient.search`
acepta todos los parametros congelados. Solo durante una futura ejecucion
aprobada, el runner consulta por nombre `TAVILY_API_KEY` en el entorno heredado
del proceso PowerShell para inicializar `TavilyClient`. No enumera el entorno,
no imprime o persiste el valor, no lo agrega al comando y sanitiza errores. Si
la variable falta, se detiene antes de crear el cliente, el run o una llamada.

El approval token obligatorio es
`BRAND-FIRST-1B-API-COMPLETION-01` y el origen obligatorio es PowerShell.

### 33.3 Contrato de ejecucion y artefactos

El runner reserva y checkpointa cada intento antes de llamar. Cada consulta
tiene como maximo un intento; un error detiene el run sin retry y deja la
consulta siguiente pendiente. La llamada SDK usa exactamente la consulta
congelada y los seis parametros autorizados.

Los nueve artefactos son `query_plan.json`, `manifest.json`,
`checkpoint.json`, `query_ledger.jsonl`, `raw_results.jsonl`,
`normalized_results.csv`, `errors.jsonl`, `completion_report.md` e
`integrity_manifest.json`. El manifest declara la repeticion tecnica autorizada
de Q3, que Q1/Q2 no se repiten, presupuesto, llamadas usadas, resultados,
vinculo al run parcial y ausencia de secretos. El integrity manifest compara
el hash inicial/final del run parcial y verifica los otros ocho artefactos.

### 33.4 Validacion offline

Las 12 pruebas focalizadas usan exclusivamente un `TavilyClient` falso y
cubren: Q3/Q4 exactas; maximo dos llamadas; cero retries; exclusion de Q1/Q2;
Unicode con emoji, tildes, ene, guion largo, griego y CJK; JSON/JSONL/CSV y
Markdown UTF-8; cinco resultados; cero resultados; autenticacion ausente;
errores 401 y 429; sanitizacion; hashes e IDs reproducibles; checkpoint antes y
despues de cada consulta; approval token; origen PowerShell; y preservacion del
run parcial.

Resultados: `py_compile` PASS; unittest 12/12 PASS; dry-run PASS con cero
lecturas de credenciales, cero clientes, cero red y ningun run creado;
ejecucion falsa completa 2/2 llamadas simuladas PASS; schemas PASS; parser AST
PowerShell sin errores; escaneo de secretos sin hallazgos; `git diff --check`
PASS. No se instalo ningun paquete.

### 33.5 Bloque PowerShell preparado, no ejecutado

El unico bloque vigente para la futura ejecucion API es autocontenido, comprueba
la disponibilidad de la variable sin imprimirla, ejecuta solo el runner API,
propaga el exit code y conserva `RUN_DIR`:

```powershell
& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No API call was made.'
        exit 3
    }

    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'

    $runnerOutput = & python -B .\scripts\run_brand_first_1b_tavily_api_completion.py --execute --approval-token 'BRAND-FIRST-1B-API-COMPLETION-01' --execution-origin powershell 2>&1
    $runnerExitCode = $LASTEXITCODE
    $runPathLine = $runnerOutput | Where-Object { $_ -like 'RUN_DIR=*' } | Select-Object -Last 1
    $runnerOutput |
        Where-Object { $_ -notlike 'RUN_DIR=*' } |
        ForEach-Object { Write-Output $_ }

    if ($runPathLine) {
        Write-Output $runPathLine
    }
    elseif ($runnerExitCode -eq 0) {
        Write-Error 'The runner did not report a run directory.'
        exit 2
    }
    exit $runnerExitCode
}
```

El bloque no fue ejecutado durante esta preparacion. La ejecucion API continua
pendiente de que el usuario lo ejecute manualmente desde PowerShell.

Estado tecnico:

`API_COMPLETION_RUNNER_READY_FOR_POWERSHELL_EXECUTION`

## 34. Auditoria consolidada offline y cierre metodologico (2026-07-18)

Esta seccion es aditiva. Consolida exclusivamente el run parcial
`run_20260718_014913` y el run API nombrado `run_20260718_032124`. Los dos
arboles fuente permanecieron inmutables y no se ejecuto Tavily, `tvly`, ningun
runner, red ni lectura de credenciales durante la auditoria.

### 34.1 Reality check y discrepancia operacional

- repositorio: `C:\Proyectos\IPTV-Playlist-Builder-Premium`;
- rama: `main`;
- `HEAD` y `origin/main` local:
  `6a8e129afc1a16c11e36d991f5bd708d9f9f7030`;
- divergencia: `0 0`;
- hash inicial/final de `run_20260718_014913`:
  `734cd73bd74d8c5c344e6b9446c7d3d00bf0b21f3062e54dc63e0cd108ced1d3`;
- hash inicial/final de `run_20260718_032124`:
  `475c835d7c1643dfa9d10e5632d707e7ac8ba01fb1809e160cbabbdf12a1543f`.

No pudo confirmarse la ausencia de un tercer run real. El inventario contiene
tambien `run_20260718_031814` y `run_20260718_031913`; ambos declaran
`EXECUTION_COMPLETED`, dos llamadas, Q3/Q4 completadas, un intento por consulta
y cero errores. Sus hashes de arbol son, respectivamente,
`d8bb92778a2963c87c5df2a2ae69563a0ef12154c2017e3447620b7f15148847` y
`79e4413e8bb8b0967b21c9bda4c6e99132f84ec05eecb0cecd7518a6b8095122`.
No se modificaron ni se incorporaron a la consolidacion semantica.

Por tanto, en los dos runs nombrados existen cuatro llamadas completadas con
evidencia, pero cinco intentos fisicos: Q1, Q2, Q3 CLI fallida, Q3 API recovery
y Q4 API. Al incluir los dos runs API adicionales observados, el inventario
registra nueve intentos fisicos, no cuatro. Esta discrepancia bloquea un cierre
tecnico limpio aunque no invalida la auditoria metodologica de las 20 filas
nombradas.

### 34.2 Estado tecnico de los runs nombrados

`run_20260718_014913` conserva:

- Q1 `COMPLETED`, 5 resultados y un intento;
- Q2 `COMPLETED`, 5 resultados y un intento;
- Q3 `FAILED` por `TVLY_PROCESS_ERROR`, un intento, sin raw completo;
- Q4 `PENDING`, cero intentos;
- tres llamadas fisicas, cero retries y un error tecnico sanitizado.

`run_20260718_032124` conserva:

- estado `EXECUTION_COMPLETED`;
- Q3 API recovery `COMPLETED`, 5 resultados y un intento;
- Q4 API completion `COMPLETED`, 5 resultados y un intento;
- dos llamadas, cero retries, `errors.jsonl` vacio;
- Q1/Q2 ausentes;
- hash inicial/final del run parcial identico.

La recomputacion independiente valido planes, manifests, checkpoints, ledgers,
raw JSONL, CSV normalizado, reports Markdown, integrity manifests, errores,
presupuestos, consultas, intentos, hashes de artefactos, raw IDs, normalized
IDs, URLs canonicas, dominios y trazabilidad ledger -> raw -> normalized. No
hubo mismatches internos ni hallazgos de secretos en los dos runs nombrados.

### 34.3 Metricas consolidadas

- consultas logicas con evidencia preservada: 4/4;
- resultados: 20, cinco por consulta;
- URLs canonicas unicas: 19;
- dominios registrables unicos: 18;
- duplicados exactos: 1;
- resultados aproximadamente relevantes: 19/20;
- resultados con ruido u homonimia de identidad: 3/20;
- first-party autoafirmados: 8;
- referencias independientes: 3;
- reviews/rankings: 2;
- senales de reseller: 4;
- promociones/afiliados: 6;
- player/application: 5;
- software product: 5;
- subscription provider claims: 5;
- unresolved respecto de identidad u oficialidad: 19.

La relevancia es topical y puede solaparse con ruido de identidad: dos fichas
de apps en Q3 son conceptualmente players pero no prueban ser el producto
oficial, y un resultado Q4 es un nombre cercano con perfil SEO.

Promedios de score:

- Q1: `0.70366526`;
- Q2: `0.52263525`;
- Q3 API: `0.69645206`;
- Q4 API: `0.68317711`.

### 34.4 DigitaLizard

Q1 recupero cinco superficies comerciales autoafirmadas en cinco dominios.
Son utiles para discovery, pero no prueban dominio oficial, operador comun,
entidad juridica, calidad, legalidad ni legitimidad.

Q2 aporto dos superficies de Trustpilot, una repeticion exacta de
`digitalizard.app/euro-iptv`, un blog con senal de reseller/SEO y una nueva
superficie `.eu`. Frente a Q1, su valor marginal es cuatro URLs y tres dominios
nuevos, con mayor diversidad de tipo de evidencia. En conjunto Q1/Q2 contienen
nueve URLs unicas y ocho dominios; ocho de esas nueve URLs son nuevas frente al
corpus 1A. Predomina la autoafirmacion y la relacion entre variantes de spelling
y dominios permanece `UNRESOLVED`.

### 34.5 IPTV Smarters Pro y control negativo

Q3 recupero cinco resultados de player/software: app stores, una explicacion
comunitaria y una superficie de descarga plausiblemente first-party. Q4
recupero cuatro superficies claras de suscripcion, reseller o promocion y un
resultado SEO de nombre cercano. Q3 y Q4 no comparten URL ni dominio.

El control negativo funciono: Q3 representa IPTV Smarters Pro como
player/aplicacion y Q4 provoca vendedores, resellers y sitios que usan o se
aproximan al nombre para vender suscripciones. La diferencia conceptual es
clara; la oficialidad de superficies concretas sigue sin demostrarse.

### 34.6 Valor marginal y dictamen metodologico

- Q1: 5 URLs y 5 dominios nuevos dentro del smoke test; discovery fuerte,
  identidad debil;
- Q2: 4 URLs y 3 dominios marginales; agrega reviews y senal de reseller;
- Q3: 5 URLs y 5 dominios; establece el lado player/software del control;
- Q4: 5 URLs y 5 dominios; expone proveedores, promociones y ruido
  interpretable.

Dictamen del metodo para los dos runs nombrados:

`SIRVIO`

Las cuatro consultas tienen evidencia preservada y trazable; DigitaLizard
aporta superficies nuevas y utiles para discovery; el control diferencia
player de proveedor; el ruido es interpretable; y
`Search/basic/max_results=5` demuestra utilidad para ampliar 1B. El dictamen
no evalua identidad, calidad, legalidad o legitimidad.

Decision de continuidad:

`A. CERRAR SMOKE TEST Y DISEÑAR BRAND-FIRST-MARKET-UNIVERSE-1B CONTROLADO.`

Esta decision no autoriza llamadas nuevas. Antes de cualquier uso adicional de
Tavily debe reconciliarse offline el origen y estatus de los dos runs API
adicionales y disenar el contrato controlado de 1B.

### 34.7 Artefactos derivados y cierre tecnico

Los outputs derivados, ignorados por Git y separados de los runs fuente, estan
en:

`research/output/best_iptv_2026/brand_first_market_universe_1b/tavily_smoke_test_01_consolidated_audit/audit_20260718_033013`

Artefactos: `consolidated_results.csv`, `semantic_audit.csv`,
`query_comparison.csv`, `domain_comparison.csv`,
`consolidated_metrics.json`, `consolidated_audit_report.md` e
`integrity_manifest.json`.

Validaciones: JSON PASS; JSONL fuente PASS; CSV PASS; Markdown PASS; schemas
PASS; hashes de artefactos PASS; trazabilidad 20/20 PASS; secretos 0;
inmutabilidad de ambos runs nombrados PASS; `git diff --check` PASS. Durante la
auditoria: llamadas Tavily adicionales 0; red adicional 0; credenciales leidas
0; creditos adicionales 0; commit/push 0.

La auditoria consolidada esta completa, pero la discrepancia del inventario
impide usar el dictamen tecnico `COMPLETE` hasta reconciliar los dos runs API
adicionales.

Dictamen tecnico:

`CONSOLIDATED_OFFLINE_AUDIT_REQUIRES_FIXES`

## 35. Cierre minimo de duplicados API y apertura del piloto multirregional (2026-07-18)

Esta seccion es aditiva y reemplaza operativamente, sin borrar historia, la
incertidumbre de 34.1/34.7 y el bloque PowerShell de 33.5. Durante esta
intervencion no se ejecuto Tavily, no hubo red, no se leyo ninguna credencial,
no se consumieron creditos y no se hizo `git add`, commit ni push.

### 35.1 Tres ejecuciones API accidentales preservadas

La aclaracion humana confirma que el mismo bloque se ejecuto manualmente tres
veces porque `exit $runnerExitCode` cerraba la ventana antes de poder revisar
el resultado. No fueron retries internos ni consultas nuevas. Los tres runs se
preservan sin modificacion.

La verificacion offline independiente valido en cada run: nueve artefactos,
integrity manifest, plan exacto Q3/Q4, checkpoint `EXECUTION_COMPLETED`, dos
llamadas, un intento por consulta, cinco resultados por consulta, diez filas
normalizadas, ledger -> raw -> normalized, Q1/Q2 ausentes, cero errores y cero
retries. Los tres contienen las mismas diez URLs y scores.

- `run_20260718_031814`:
  `API_COMPLETION_RUN_AUTHORITATIVE`; hash de arbol
  `d8bb92778a2963c87c5df2a2ae69563a0ef12154c2017e3447620b7f15148847`.
- `run_20260718_031913`:
  `ACCIDENTAL_DUPLICATE_EXECUTION_PRESERVED`; hash de arbol
  `79e4413e8bb8b0967b21c9bda4c6e99132f84ec05eecb0cecd7518a6b8095122`.
- `run_20260718_032124`:
  `ACCIDENTAL_DUPLICATE_EXECUTION_PRESERVED`; hash de arbol
  `475c835d7c1643dfa9d10e5632d707e7ac8ba01fb1809e160cbabbdf12a1543f`.

Contabilidad fisica corregida:

- ejecuciones API manuales: `3`;
- llamadas API por ejecucion: `2`;
- llamadas API observadas: `6`;
- retries internos: `0`;
- intentos CLI previos: `3`;
- intentos fisicos observados totales: `9`.

El dictamen metodologico del smoke test se mantiene usando solo el primer run
completo como autoridad:

`SIRVIO`

### 35.2 Guardia API y correccion de PowerShell

`scripts/run_brand_first_1b_tavily_api_completion.py` ahora busca primero un
run completo compatible, prioriza explicitamente `run_20260718_031814` y
bloquea antes de leer `TAVILY_API_KEY`, crear cliente, crear directorio o hacer
una llamada. Al bloquear, el runner imprime el `RUN_DIR` autoritativo.

El bloque que devuelve `powershell_block()` ya no contiene ningun `exit`, no
cierra la ventana y siempre imprime `RUNNER_EXIT_CODE`. Cuando el runner
informa un run, conserva e imprime `RUN_DIR`, y muestra
`DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED`. El bloque historico de 33.5 queda
expresamente superseded y no debe volver a ejecutarse.

### 35.3 Contrato del piloto amplio

Se preparo el runner separado
`scripts/run_brand_first_1b_multiregion_pilot.py` para
`SEARCH-MAP-EXTRACT-MULTIREGION-PILOT-01`. El flujo congelado es:

1. Search de fuentes de mercado.
2. Seleccion humana offline de 1 a 5 fuentes.
3. Map solo sobre esas fuentes aprobadas.
4. Seleccion humana offline de 1 a 10 paginas concretas halladas por Search o
   Map.
5. Extract de una URL concreta por operacion.
6. Consolidacion offline de marcas, procedencia e independencia.

El runner implementa `--dry-run`, `--execute`, token exacto, origen PowerShell,
checkpoint antes de cada intento, reserva de presupuesto, resume sin repetir
operaciones completadas, escrituras atomicas UTF-8, JSON/JSONL/CSV/Markdown,
sanitizacion, manifests de integridad y guardia contra cualquier run compatible
ya creado. Una seleccion invalida se bloquea antes de leer la credencial o
crear el cliente. Los archivos de seleccion son las unicas entradas humanas
mutables y se vuelven a incorporar al manifest de integridad antes de Map o
Extract.

Crawl y Research tienen contrato visible con `designed=true`,
`authorized=false` y `executable_stage=false`. No existe una ruta automatica
que pueda invocarlos; requieren revision del piloto y autorizacion humana
separada.

### 35.4 Consultas propuestas y presupuesto exacto

Las diez consultas estan orientadas a fuentes, no a dominios individuales:

1. `best IPTV services 2026 comparison USA Canada`
2. `IPTV providers reviews 2026 USA Canada`
3. `IPTV services community recommendations forum USA Canada`
4. `IPTV providers Europe 2026 comparison reviews`
5. `best IPTV services UK Germany France 2026`
6. `mejores servicios IPTV Europa 2026 comparativa`
7. `mejores servicios IPTV 2026 Latinoamerica comparativa`
8. `proveedores IPTV resenas Mexico Argentina Colombia`
9. `servicios IPTV Latinoamerica recomendaciones comunidad`
10. `IPTV provider directory market comparison 2026`

Presupuesto rigido visible antes de ejecutar:

- Search: `10` operaciones;
- Map: `5` operaciones maximas;
- Extract: `10` operaciones maximas;
- presupuesto operativo global: `25`;
- techo absoluto global: `30`;
- retries automaticos: `0`.

Autenticacion, rate limit, presupuesto agotado o respuesta estructuralmente
invalida detienen el flujo. Dos errores genericos con la misma firma tambien
lo detienen. Cada operacion tiene como maximo un intento.

### 35.5 Taxonomia, independencia, artefactos y metricas

El plan congela los niveles A-E pedidos y las nueve senales de independencia:
texto duplicado, mismo orden de marcas, template, empresa, autor, contacto, red
de dominios, codigo de afiliado y republicacion.

Se preparan los quince outputs solicitados y cuatro artefactos operativos
adicionales: `source_selection.json`, `extract_selection.json`,
`operation_ledger.jsonl` y `errors.jsonl`. Los schemas de menciones y
candidatos conservan `supporting_row_ids`; los envelopes Search/Map/Extract
conservan operation ID, URL, hash y payload sanitizado para procedencia
completa.

`pilot_metrics.json` prepara: marcas mencionadas, marcas nuevas frente al
historico, repeticion independiente, fuentes A-E, cobertura regional y
linguistica, duplicacion exacta/SEO, ruido, valor informativo por operacion y
valor marginal de Search, Map y Extract. Las metricas que requieren criterio
humano permanecen explicitamente
`PENDING_OFFLINE_CONSOLIDATION`, no se inventan durante adquisicion.

### 35.6 Validacion offline y unico comando futuro

Pruebas focalizadas: runner API `13/13` PASS; runner multirregional `7/7` PASS;
total `20/20` PASS. Cubren mocks exactos de Search/Map/Extract, presupuesto,
auth, respuesta estructural invalida, cero retries, checkpoint, resume/no-op
sin nuevas lecturas ni llamadas, selecciones offline, schemas, UTF-8, secretos,
guardias y PowerShell sin `exit`. `py_compile`, dry-run y `git diff --check`
tambien pasan.

Este es el unico comando PowerShell futuro vigente. No fue ejecutado. Solo
inicia Search; si imprime `RUN_DIR`, no debe repetirse y el siguiente paso es
la seleccion offline anterior a Map:

```powershell
& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No Tavily operation was made.'
        $runnerExitCode = 3
    }
    else {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'

        $runnerOutput = & python -B .\scripts\run_brand_first_1b_multiregion_pilot.py --execute --approval-token 'BRAND-FIRST-1B-MULTIREGION-PILOT-01' --execution-origin powershell 2>&1
        $runnerExitCode = $LASTEXITCODE
        $runPathLine = $runnerOutput | Where-Object { $_ -like 'RUN_DIR=*' } | Select-Object -Last 1
        $runnerOutput |
            Where-Object { $_ -notlike 'RUN_DIR=*' } |
            ForEach-Object { Write-Output $_ }

        if ($runPathLine) {
            Write-Output $runPathLine
        }
        elseif ($runnerExitCode -eq 0) {
            Write-Error 'The runner did not report a run directory.'
            $runnerExitCode = 2
        }
    }
    Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"
    Write-Output 'NEXT_STAGE=OFFLINE_SOURCE_SELECTION_BEFORE_MAP'
    Write-Output 'DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED'
}
```

Estado de esta intervencion: Tavily nuevo `0`; red `0`; credenciales leidas
`0`; creditos nuevos `0`; commit/push `0`.

Dictamen final:

`MULTIREGION_PILOT_OFFLINE_PREPARATION_COMPLETE_PENDING_HUMAN_REVIEW`

## 36. Seleccion offline de fuentes anterior a Map (2026-07-18)

Esta seccion es aditiva y supersede unicamente el comando Search de 35.6, que
ya fue ejecutado por el usuario. La revision fue completamente offline: no se
ejecuto Search, Map, Extract, Crawl, Research ni Tavily; no hubo red, lectura
de credenciales, consumo adicional de creditos, `git add`, commit o push.

### 36.1 Estado Search verificado

- run: `run_20260718_041625`;
- estado: `AWAITING_OFFLINE_SOURCE_SELECTION`;
- Search: `10/10` consultas completadas, un intento por consulta;
- llamadas: `10`;
- resultados: `49` (`9 x 5` y `1 x 4`);
- URLs unicas: `41`;
- dominios unicos: `29`;
- errores: `0`;
- retries: `0`;
- Map/Extract: `0/0` operaciones;
- presupuesto restante antes de Map: Map `5`, Extract `10`, global `15`.

Rama `main`; `HEAD` y `origin/main` local
`6a8e129afc1a16c11e36d991f5bd708d9f9f7030`; divergencia `0 0`.

### 36.2 Duplicacion, clasificacion e independencia

Hay ocho filas duplicadas sobre siete URLs repetidas. El post de Reddit en
`r/xfinity` aparece tres veces; seis URLs aparecen dos veces. Entre URLs
distintas, dos posts de Indie Hackers conservan un snippet exacto, senal fuerte
de template o republicacion. Los clusters multi-URL del mismo dominio son:
Indie Hackers `4`, YouTube `4`, Reddit `3`, Geek Vibes Nation `2`, IPTV Service
Radar `2`, IssueWire `2` y SlideShare `2`. Compartir plataforma no demuestra
por si solo misma autoria, pero impide contar esas paginas como publicaciones
independientes sin revision posterior. Empresa, autor, contacto, codigo de
afiliado, red empresarial y orden identico de marcas entre dominios distintos
permanecen no confirmados con evidencia Search.

Reclasificacion offline conservadora de las 41 URLs unicas, basada solo en
URL, titulo y snippet: A `0`, B `5`, C `23`, D `7`, E `6`. No se concede A
porque Search no demuestra conjuntamente autoria visible y metodologia. B
agrupa foros con contexto; C, comparadores/rankings; D, promocion directa; E,
ruido o uso oportunista de plataformas. Los niveles son de discovery y no
prueban reputacion, oficialidad, calidad o legalidad.

### 36.3 Fuentes aprobadas para Map

| Prioridad | Dominio | Region / idioma | Nivel | Independence group | Motivo y expectativa | Riesgo principal |
|---:|---|---|:---:|---|---|---|
| 1 | `redflagdeals.com` | Norteamerica / en | B | `IG-MAP-01-REDFLAGDEALS-FORUM` | Foro canadiense no basado en ranking; Map puede hallar discusiones y servicios nombrados. | Anecdotico, potencialmente antiguo o promocional. |
| 2 | `iptvserviceradar.com` | Europa / en | C | `IG-MAP-02-IPTVSERVICERADAR` | Comparador dedicado con varias marcas y paginas por pais. | Sesgo editorial o afiliado; un solo grupo. |
| 3 | `guru99.com` | Europa / es | C | `IG-MAP-03-GURU99-ES` | Guia estructurada en espanol con navegacion localizada. | Metodologia e independencia no demostradas. |
| 4 | `tapatalk.com` | Latinoamerica / es | B | `IG-MAP-04-TAPATALK-MEXICO-FORUM` | Foro mexicano contextual, util para nombres y alias regionales. | Semilla de 2020; contenido posiblemente obsoleto. |
| 5 | `softwaretestinghelp.com` | Multirregion / en | C | `IG-MAP-05-SOFTWARETESTINGHELP` | Lista mundial extensa y jerarquia editorial navegable. | Ranking potencialmente afiliado; discovery solamente. |

Las cinco semillas pertenecen a cinco dominios e independence groups distintos.
Cubren Norteamerica, Europa, Latinoamerica y multirregion, ademas de ingles y
espanol. Se evitaron rankings repetidos de Indie Hackers, IssueWire,
SlideShare, Reddit fuera de contexto y superficies claramente promocionales.

El artefacto requerido por el runner fue actualizado atomicamente en:

`research/output/best_iptv_2026/brand_first_market_universe_1b/search_map_extract_multiregion_pilot_01/run_20260718_041625/source_selection.json`

Conserva el schema exacto
`brand_first_market_universe_1b_multiregion_pilot.v1`, estado `APPROVED`, cinco
URLs observadas por Search y un `supporting_row_ids` valido por seleccion. No se
alteraron plan, registry, raw Search, ledger, manifest, checkpoint, errores ni
integrity manifest. El runner incorporara el input humano al integrity manifest
inmediatamente antes de adquirir el cliente de Map.

### 36.4 Preflight offline y siguiente comando

Preflight PASS: schema, cinco supporting row IDs, URLs pertenecientes al
registry, cinco dominios unicos, niveles A-E, presupuesto Map, contrato CLI,
estado del checkpoint, integrity con `source_selection.json` como unica entrada
mutable, guardia de run compatible, resume Map-only, parser PowerShell y
ausencia de `exit`. Credenciales leidas `0`, clientes creados `0`, operaciones
de red `0`. `git diff --check` PASS.

Este es el unico bloque PowerShell futuro vigente. No fue ejecutado. Continua
el run existente, invoca solo `--stage map`, tiene cinco selecciones y no puede
ejecutar Search ni Extract:

```powershell
& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    $runDir = 'C:\Proyectos\IPTV-Playlist-Builder-Premium\research\output\best_iptv_2026\brand_first_market_universe_1b\search_map_extract_multiregion_pilot_01\run_20260718_041625'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No Map operation was made.'
        $runnerExitCode = 3
    }
    else {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'

        $runnerOutput = & python -B .\scripts\run_brand_first_1b_multiregion_pilot.py --resume-run $runDir --stage map --approval-token 'BRAND-FIRST-1B-MULTIREGION-PILOT-01' --execution-origin powershell 2>&1
        $runnerExitCode = $LASTEXITCODE
        $runnerOutput |
            Where-Object { $_ -notlike 'RUN_DIR=*' } |
            ForEach-Object { Write-Output $_ }
    }
    Write-Output "RUN_DIR=$runDir"
    Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"
    Write-Output 'NEXT_STAGE=OFFLINE_PAGE_SELECTION_BEFORE_EXTRACT'
}
```

Dictamen:

`OFFLINE_SOURCE_SELECTION_COMPLETE_PENDING_MAP_EXECUTION`

## 37. Seleccion offline de paginas anterior a Extract (2026-07-18)

Esta seccion es aditiva y supersede unicamente el comando Map de 36.4, que ya
fue ejecutado por el usuario. La revision fue completamente offline: no se
ejecuto Search, Map, Extract, Crawl, Research ni Tavily; no hubo red, lectura
de credenciales, creditos adicionales, `git add`, commit o push.

### 37.1 Estado Map verificado

- run: `run_20260718_041625`;
- estado: `AWAITING_OFFLINE_EXTRACT_SELECTION`;
- Search: `10` completadas, sin repeticion;
- Map: `5/5` completadas, `0` fallidas, un intento por operacion;
- resultados Map: `0 + 50 + 50 + 0 + 19 = 119` paginas;
- dominios efectivos: `3`;
- URLs Map unicas: `119`; duplicados exactos: `0`;
- errores: `0`; retries: `0`;
- Extract: `0` operaciones y `0` envelopes;
- presupuesto antes de Extract: Extract `10`, global `10`.

El ledger contiene cinco `ATTEMPT_RESERVED`, cinco `RAW_EVIDENCE` y cinco
`COMPLETED` para Map. RedFlagDeals y Tapatalk devolvieron cero paginas;
IPTV Service Radar y Guru99 devolvieron 50 cada uno, y Software Testing Help
19. Los outputs historicos de Search y Map permanecieron byte-identicos durante
esta seleccion.

### 37.2 Analisis y paginas aprobadas

La distribucion efectiva es IPTV Service Radar `50`, Guru99 `50` y Software
Testing Help `19`. Guru99 contiene 15 pares estructurales raiz/`es`; no se
seleccionaron ambas copias. Se eligieron ocho paginas, todas nivel C, porque las
dos fuentes B no produjeron URLs Map. La muestra mantiene tres independence
groups y cubre Europa, Norteamerica, Latinoamerica, multirregion, ingles y
espanol.

| # | Dominio | Pagina | Region / idioma | Independence group | Objetivo | Riesgo |
|---:|---|---|---|---|---|---|
| 1 | `iptvserviceradar.com` | `/best-iptv-europe-providers` | Europa / en | `IG-MAP-02-IPTVSERVICERADAR` | Ranking amplio europeo y orden de marcas. | Afiliacion; mismo grupo que 2-3. |
| 2 | `iptvserviceradar.com` | `/best-iptv-brazil-providers` | Latinoamerica / en | `IG-MAP-02-IPTVSERVICERADAR` | Comparar Brasil con Guru99 en espanol. | Template compartido. |
| 3 | `iptvserviceradar.com` | `/best-iptv-canada-providers-2026` | Norteamerica / en | `IG-MAP-02-IPTVSERVICERADAR` | Ranking Canada y senales 2026. | Actualidad inferida por slug. |
| 4 | `guru99.com` | `/es/best-iptv-spain.html` | Europa / es | `IG-MAP-03-GURU99-ES` | Tabla/lista localizada en espanol. | Comparador comercial. |
| 5 | `guru99.com` | `/es/best-iptv-brazil.html` | Latinoamerica / es | `IG-MAP-03-GURU99-ES` | Comparacion cruzada de Brasil. | Localizacion de template. |
| 6 | `guru99.com` | `/es/best-usa-iptv.html` | Norteamerica / es | `IG-MAP-03-GURU99-ES` | Vista en espanol de marcas USA. | Posible solapamiento con version en ingles. |
| 7 | `softwaretestinghelp.com` | `/iptv-services-worldwide` | Multirregion / en | `IG-MAP-05-SOFTWARETESTINGHELP` | Lista mundial de tercer publisher. | Ranking afiliado y mezcla regional. |
| 8 | `softwaretestinghelp.com` | `/best-iptv-usa-service-providers` | Norteamerica / en | `IG-MAP-05-SOFTWARETESTINGHELP` | Comparar USA entre publishers. | Puede solapar la lista mundial. |

Se descartaron `111` paginas: `47` de IPTV Service Radar, `47` de Guru99 y
`17` de Software Testing Help. Los motivos principales fueron rankings
regionales adicionales del mismo template, 15 pares Guru99 raiz/es, reviews de
un solo proveedor, apps/players/dispositivos, paginas genericas o de
metodologia/categoria, temas de deportes/free trial/reseller y regiones fuera
del alcance. No se gasto presupuesto en multiples copias del mismo ranking.

### 37.3 Artefacto, preflight y guardias

`extract_selection.json` quedo `APPROVED` con ocho URLs Map unicas. Cada fila
conserva map row ID, map operation, selection source, raw Map record, semilla,
mapped URL, dominio, region, idioma, nivel, independence group, motivos,
riesgos y cadena `maprow_* -> source_*`.

El plan de seleccion usa schema
`brand_first_market_universe_1b_extract_selection_plan.v1` y hash canonico:

`2a4074133e881507bf2722f90c5e2aa9497f883adfb2f20ec9a7e7e20d584a0d`

Preflight PASS: schema, hash, ocho URLs unicas, ocho referencias Map, ocho
cadenas de supporting row IDs, presupuesto, UTF-8, secretos `0`, integrity con
`extract_selection.json` como unica entrada mutable, CLI Extract-only y parser
PowerShell. Antes y despues del preflight: Search `10`, Map `5`, Extract `0`,
global `15`; credenciales `0`, clientes `0`, red `0`.

El runner fue endurecido de forma acotada: Search solo puede reanudarse desde
`SEARCH_READY/SEARCH_IN_PROGRESS`, Map desde
`AWAITING_OFFLINE_SOURCE_SELECTION/MAP_IN_PROGRESS` y Extract desde
`AWAITING_OFFLINE_EXTRACT_SELECTION/EXTRACT_IN_PROGRESS`. Una etapa ya
superada queda `BLOCKED_STAGE` antes de leer credencial o crear cliente. Las
siete pruebas focalizadas pasan.

Si se ejecutan las ocho selecciones, se usaran `8/10` operaciones Extract y
`23/25` globales; quedaran dos operaciones sin usar. Extract sigue pendiente.

### 37.4 Unico comando futuro para Extract

Este bloque no fue ejecutado. Continua exclusivamente el run existente e
invoca solo `--stage extract`:

```powershell
& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    $runDir = 'C:\Proyectos\IPTV-Playlist-Builder-Premium\research\output\best_iptv_2026\brand_first_market_universe_1b\search_map_extract_multiregion_pilot_01\run_20260718_041625'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No Extract operation was made.'
        $runnerExitCode = 3
    }
    else {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'

        $runnerOutput = & python -B .\scripts\run_brand_first_1b_multiregion_pilot.py --resume-run $runDir --stage extract --approval-token 'BRAND-FIRST-1B-MULTIREGION-PILOT-01' --execution-origin powershell 2>&1
        $runnerExitCode = $LASTEXITCODE
        $runnerOutput |
            Where-Object { $_ -notlike 'RUN_DIR=*' } |
            ForEach-Object { Write-Output $_ }
    }
    Write-Output "RUN_DIR=$runDir"
    Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"
    Write-Output 'NEXT_STAGE=OFFLINE_CONSOLIDATION_AND_PILOT_EVALUATION'
    Write-Output 'DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED'
}
```

Dictamen:

`OFFLINE_PAGE_SELECTION_COMPLETE_PENDING_EXTRACT_EXECUTION`

## 38. Fix minimo del preflight Extract anterior a reserva (2026-07-18)

Esta seccion supersede unicamente el bloque Extract de 37.4. El diagnostico y
la correccion fueron completamente offline: no se ejecuto Tavily, Search, Map
ni Extract real; no hubo red, lectura de `TAVILY_API_KEY`, creditos, otro run,
instalaciones, `git add`, commit o push. Los resultados Search/Map y
`extract_selection.json` no fueron modificados.

### 38.1 Causa exacta y evidencia

El runner no contiene `return -1`, `sys.exit(-1)` ni un codigo funcional `-1`.
El `-1` observado fue una terminacion `SystemExit(-1)` que escapaba sin
normalizar desde la frontera de inicializacion del cliente. `main()` solo
capturaba `RunnerBlocked`, por lo que PowerShell recibia el codigo nativo `-1`
sin causa humana.

La secuencia esta acotada por evidencia de disco. El intento actualizo
`integrity_manifest.json` a `2026-07-18T08:51:00.442067+00:00` e incorporo el
hash correcto de `extract_selection.json`, de modo que ya habia superado plan,
seleccion, manifest, checkpoint, integrity y guardia de etapa. En cambio,
checkpoint, ledger, `extracted_pages.jsonl` y `errors.jsonl` quedaron intactos:
Search `10`, Map `5`, Extract `0`, global `15`, cero `ATTEMPT_RESERVED` Extract.
El segundo parseo de seleccion y la creacion en memoria de ocho operaciones
tambien pasan sobre el run real. La unica frontera restante anterior al primer
checkpoint Extract era `acquire_client()`.

Una prueba focalizada reproduce exactamente `SystemExit(-1)` en esa frontera:
antes del fix escapaba; ahora se convierte en
`BLOCKED_CLIENT_INITIALIZATION`, codigo `5`, con el mensaje de que no se reservo
ninguna operacion. Integrity, checkpoint y ledger permanecen byte-identicos.

### 38.2 Fix minimo

- codigos definidos: exito `0`, configuracion/integridad `2`, autenticacion
  `3`, presupuesto `4`, fallo tecnico `5`;
- lectura/creacion del cliente captura `SystemExit` y excepciones inesperadas,
  sanitiza la causa y devuelve codigo `5`;
- `main()` tiene fallback explicito para terminaciones o fallos no previstos;
- el cliente se construye antes de refrescar integrity, evitando mutar el run
  si la inicializacion falla;
- el plan/hash y las referencias Map de `extract_selection.json` se validan;
- la reserva continua ocurriendo antes de cada llamada;
- Search y Map superados siguen `BLOCKED_STAGE` antes de credencial/cliente;
- una seleccion corrupta sigue `BLOCKED_SELECTION` con codigo `2`.

Preflight real offline: hash valido, ocho paginas, ocho operaciones simuladas
en memoria, secretos `0`, Extract antes/despues `0`, credenciales/clientes/red
`0`. Fake execution: ocho `ATTEMPT_RESERVED`, ocho llamadas Extract simuladas,
ocho envelopes, global `23/25`, intentos `1`, retries `0`, UTF-8 PASS. Pruebas
focalizadas del runner multirregional `10/10` PASS.

### 38.3 Unico bloque futuro corregido

No fue ejecutado. Muestra toda la salida; `NEXT_STAGE` aparece solo con codigo
`0`, y cualquier fallo termina con
`EXTRACT_STAGE_FAILED_DO_NOT_RETRY_AUTOMATICALLY`:

```powershell
& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    $runDir = 'C:\Proyectos\IPTV-Playlist-Builder-Premium\research\output\best_iptv_2026\brand_first_market_universe_1b\search_map_extract_multiregion_pilot_01\run_20260718_041625'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No Extract operation was made.'
        $runnerExitCode = 3
    }
    else {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'

        $runnerOutput = & python -B .\scripts\run_brand_first_1b_multiregion_pilot.py --resume-run $runDir --stage extract --approval-token 'BRAND-FIRST-1B-MULTIREGION-PILOT-01' --execution-origin powershell 2>&1
        $runnerExitCode = $LASTEXITCODE
        $runnerOutput | ForEach-Object { Write-Output $_ }
    }

    Write-Output "RUN_DIR=$runDir"
    Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"
    if ($runnerExitCode -eq 0) {
        Write-Output 'NEXT_STAGE=OFFLINE_CONSOLIDATION_AND_PILOT_EVALUATION'
        Write-Output 'DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED'
    }
    else {
        Write-Output 'EXTRACT_STAGE_FAILED_DO_NOT_RETRY_AUTOMATICALLY'
    }
}
```

Dictamen:

`EXTRACT_PREFLIGHT_MINIMAL_FIX_COMPLETE_PENDING_EXECUTION`

## 39. Consolidacion y evaluacion offline final del piloto multirregional (2026-07-18)

Esta seccion es aditiva y supersede el estado pendiente de Extract de 38.3. El
usuario ejecuto el bloque corregido sobre el mismo `run_20260718_041625` y el
runner devolvio `RUNNER_EXIT_CODE=0` y
`NEXT_STAGE=OFFLINE_CONSOLIDATION_AND_PILOT_EVALUATION`. Esta consolidacion no
ejecuto Tavily, Search, Map, Extract, Crawl ni Research; no uso red, no leyo
credenciales y no autorizo nuevas llamadas.

### 39.1 Reality check y contabilidad final

- repositorio: `C:\Proyectos\IPTV-Playlist-Builder-Premium`;
- rama: `main`;
- `HEAD` y `origin/main` local:
  `6a8e129afc1a16c11e36d991f5bd708d9f9f7030`;
- divergencia: `0 0`;
- manifest: `ACQUISITION_COMPLETED_PENDING_OFFLINE_CONSOLIDATION`;
- checkpoint: `offline_consolidation`;
- Search: `10` reservadas y `10` completadas, `49` filas, `41` URLs y `29`
  dominios unicos;
- Map: `5` reservadas y `5` completadas, `119` URLs unicas, de las cuales
  `115` no estaban entre las URLs Search;
- Extract: `8` reservadas y `8` completadas, `8` envelopes, `8` paginas con
  contenido, `0` vacias y `0` fallidas;
- global: `23/25`; quedan `2` operaciones globales y `2` Extract sin usar;
- errores `0`, retries `0`, Crawl `0`, Research `0`.

Antes de consolidar, el run tenia 19 archivos y hash de arbol
`5a240ad0fe99d3faf62069ab578bc6290f656f585812599dbeee323cbbf95be1`.
Tras completar exclusivamente derivados, tiene 24 archivos, 888,313 bytes y
hash de arbol
`500aba729cc221982886689a95aa8a2b89dd09f76589fd5215683f072c559e86`.

Los once artefactos protegidos de Search/Map/Extract, checkpoint, ledger,
selecciones y manifest conservaron exactamente sus hashes de entrada. Su hash
agregado es
`6e363fe802634477a670cd08b4a83712bd2958ec490977dc59ac3b709a554c68`.
El arbol FIX4 autoritativo tambien permanece
`f21e2f16a7e67fc259328ff7d97520e02ab3bc3f6a33bb5223d3786f299f3b31`.

### 39.2 Marcas y comparacion con FIX4

La comparacion primaria usa el artefacto real
`run_20260717_051437/02_raw_brand_mentions.csv`: `1,035` filas y SHA-256
`c17f14925934861e91da53d44a15c7e98979a03a3cab1b65a5acd5d9f7839b8c`.
Los alias y canonicos FIX4 solo se usaron para explicar normalizaciones, nunca
para sustituir el universo de 1,035 nombres.

Resultado Extract consolidado:

- menciones brutas: `103`;
- entidades normalizadas unicas: `56`;
- candidatos de proveedor: `54`;
- coincidencias historicas exactas: `21`;
- coincidencias historicas normalizadas: `5`;
- variantes posibles que requieren revision: `8`;
- candidatos nuevos plausibles: `20`;
- falsos positivos/no objetivo: `2` entidades y `3` menciones (`ORA IPTV
  Player`, aplicacion; `Fubo TV`, OTT legal fuera del universo objetivo);
- candidatos repetidos en dos o mas independence groups: `15`;
- candidatos nuevos repetidos en dos grupos: `4`: `iScreenHD IPTV`,
  `OneTVBox IPTV`, `SofaIPTV` y `USA LIVE IPTV`.

Las ocho variantes pendientes son `Bunnystream`, `IPTV Harmony`, `IPTV
Trends`, `Mundo IPTV`, `Stremzi`, `TrendyScreen`, `TV Krooz` y `Worthystream`.
Se conservaron como
`POSSIBLE_VARIANT_REQUIRES_REVIEW`: agregar/quitar/reordenar `IPTV` o corregir
una etiqueta traducida no basta para forzar identidad.

### 39.3 Valor por etapa, independencia y cobertura

Search sirvio para discovery amplio: `4.1` URLs unicas por operacion, aunque
con ocho filas URL duplicadas y predominio de rankings/promocion. La revision
por URL unica quedo A/B/C/D/E = `0/5/23/7/6`; el conteo provisional por fila
fue `0/7/30/12/0`.

Map sirvio de forma selectiva: `23.8` URLs por operacion y `115` URLs nuevas
frente a Search, pero solo tres de cinco dominios devolvieron paginas; las dos
fuentes B devolvieron cero. Ocho de 119 paginas se consideraron utiles para
Extract.

Extract aporto el mayor valor semantico: `12.875` menciones brutas y `2.5`
candidatos nuevos plausibles por operacion. El contenido completo permitio
recuperar nombres, alias deformados por traduccion, falsos positivos y orden
de rankings que titulos y snippets no demostraban.

La muestra cubre Norteamerica, Europa, Latinoamerica y multirregion, en ingles
y espanol. No es representativa del mercado: las ocho paginas son nivel C y
pertenecen a solo tres grupos editoriales. El solapamiento interno y las
estructuras de tabla/ranking indican duplicacion SEO o afiliada probable. La
repeticion entre dominios es corroboracion de discovery, no prueba de
propiedad comun, identidad, oficialidad, legalidad, legitimidad, calidad ni
reputacion.

### 39.4 Dictamen y continuidad

Dictamen global:

`PILOT_SIRVIO_PARCIALMENTE`

El piloto si amplio el universo con `20` candidatos plausiblemente nuevos,
pero solo cuatro reaparecen en grupos editoriales distintos y todos requieren
revision de identidad antes de priorizarse. Una marca nueva no equivale a una
marca valida o recomendable.

Continuidad elegida:

`E. CERRAR 1B Y PASAR A PRIORIZACION DE MARCAS 1C.`

Crawl no se recomienda ahora. Si en el futuro se justificara un smoke test, el
candidato concreto seria `iptvserviceradar.com`, una operacion y maximo diez
paginas, para topologia de rankings por pais; el riesgo es consumir casi todo
en templates equivalentes. Research tampoco se recomienda ahora; una futura
operacion deberia responder unicamente si registros publicos de autor,
contacto y disclosure de afiliacion demuestran independencia editorial entre
los tres publishers. Research no debe usarse para enumerar marcas masivamente
porque reduce trazabilidad por fila y mezcla discovery con sintesis.

Esta decision no autoriza nuevas llamadas.

### 39.5 Artefactos y validacion

Se completaron atomicamente y en UTF-8 los nueve artefactos previstos y se
crearon `final_pilot_evaluation.json`, `extracted_page_quality.csv`,
`stage_value_comparison.csv`, `brand_source_matrix.csv` e
`historical_match_review.csv`. El script reproducible offline es
`scripts/consolidate_brand_first_1b_multiregion_pilot.py`.

Validacion: JSON, JSONL, CSV, Markdown, UTF-8, schemas, hashes del integrity
manifest, 103/103 cadenas de trazabilidad, 56/56 clasificaciones historicas,
ocho operaciones/envelopes/URLs, secretos `0`, `py_compile`, ejecucion offline
reproducible y `git diff --check`: PASS. Raw y FIX4 permanecen byte-identicos.

Dictamen tecnico:

`MULTIREGION_PILOT_OFFLINE_EVALUATION_COMPLETE`

## 40. Cierre autoritativo de BRAND-FIRST-MARKET-UNIVERSE-1B (2026-07-18)

Esta seccion es aditiva y prevalece sobre cualquier bloque historico que
describa 1B, el smoke test, la reconciliacion API, el piloto multirregional o
su consolidacion como pendientes. No borra esas etapas porque forman la
trazabilidad reproducible del hito completo.

### 40.1 Genealogia cerrada de 1B

El smoke test CLI, su correccion Unicode y la terminacion API Q3/Q4 quedan
preservados. Las tres ejecuciones API manuales accidentales fueron
reconciliadas: no fueron retries internos y contenian las mismas diez URLs y
scores. El run API autoritativo es `run_20260718_031814`; los runs
`run_20260718_031913` y `run_20260718_032124` son duplicados accidentales
preservados. Esta decision mantiene la contabilidad historica de seis llamadas
API observadas, cero retries internos y usa solo el primer run completo como
autoridad metodologica.

El piloto multirregional autoritativo es:

`research/output/best_iptv_2026/brand_first_market_universe_1b/search_map_extract_multiregion_pilot_01/run_20260718_041625`

Su contabilidad final es Search `10/10`, Map `5/5`, Extract `8/8`, global
`23/25`, errores `0` y retries `0`. La consolidacion contiene `103` menciones,
`56` entidades normalizadas, `54` candidatos de proveedor, `21` matches
historicos exactos, `5` matches normalizados, `8` variantes pendientes, `20`
candidatos nuevos y `2` entidades fuera del universo objetivo.

Los cuatro candidatos nuevos repetidos entre grupos editoriales son:

- `iScreenHD IPTV`;
- `OneTVBox IPTV`;
- `SofaIPTV`;
- `USA LIVE IPTV`.

Las ocho paginas Extract pertenecen a fuentes nivel C. La repeticion entre
publishers es corroboracion de discovery, no prueba identidad, oficialidad,
legalidad, legitimidad, reputacion ni calidad. Una marca nueva no equivale a
un proveedor valido o recomendable.

### 40.2 Superficie versionable y validacion de cierre

La trazabilidad reproducible de 1B esta compuesta por:

- runner y prueba del smoke test CLI;
- runner y prueba de API completion;
- runner y prueba del piloto multirregional;
- consolidador offline del piloto;
- este handoff aditivo.

Los outputs bajo `research/` permanecen ignorados y no deben forzarse en Git.
La evidencia raw y los runs historicos permanecen fuera del versionamiento y
byte-identicos.

Validacion final offline: `py_compile` `7/7`; unittest focalizado `46/46`;
importacion de cuatro scripts con subprocess `0` y sockets `0`; JSON `8`,
JSONL `4`, CSV `11` y Markdown `1`; UTF-8 `24/24` artefactos del run y `8/8`
archivos versionables; trazabilidad `103/103`; clasificacion `56/56`;
integrity `23/23`; raw protegido `11/11`; secretos reales `0`; residuos
temporales de pruebas 1B `0`; `git diff --check` PASS. El token
`tvly-secret-must-be-redacted` es un fixture ficticio de dos pruebas de
redaccion y no una credencial.

Los scripts no ejecutan Tavily al importarse. Crawl y Research conservan
`authorized=false` y `executable_stage=false`.

### 40.3 Dictamen y siguiente tarea unica

Dictamen global de 1B:

`PILOT_SIRVIO_PARCIALMENTE`

Decision de continuidad:

`E. CERRAR 1B Y PASAR A PRIORIZACION DE MARCAS 1C.`

Crawl y Research no quedan autorizados. No se inicia desarrollo de 1C en esta
seccion.

Proxima tarea unica:

`BRAND-SEED-PRIORITIZATION-1C`

`OFFLINE-PRIORITY-MODEL-AND-REVIEW-QUEUE-01`

Estado del hito:

`BRAND_FIRST_MARKET_UNIVERSE_1B_READY_FOR_FINAL_VERSIONING`
