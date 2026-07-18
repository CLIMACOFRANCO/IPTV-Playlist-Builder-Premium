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
   `C:\Users\Franco Traders\.codex\.env`.
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

C:\Users\Franco Traders\.codex\.env

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
