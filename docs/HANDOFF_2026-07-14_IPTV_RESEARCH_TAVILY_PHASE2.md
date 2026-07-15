# HANDOFF - IPTV Playlist Builder Premium

## 1. Metadatos

- Fecha: 2026-07-14
- Proyecto: IPTV Playlist Builder Premium
- Fase: Investigacion comercial IPTV / Due Diligence con Tavily
- Estado: Phase 2 en curso
- Ruta del proyecto: `C:\Proyectos\IPTV-Playlist-Builder-Premium`

## 2. Objetivo general

Se esta construyendo una base de inteligencia comercial y OSINT sobre proveedores IPTV/OTT para identificar marcas, dominios candidatos, empresa juridica, pais, domicilio, aplicaciones, paneles, revendedores, tecnologia observable, transparencia, licencias publicamente demostradas o no, antecedentes legales y senales de riesgo.

Este trabajo no evalua todavia la calidad real del streaming. Tampoco debe declarar legalidad o ilegalidad sin evidencia publica suficiente.

## 3. Alcance y limites

- Investigacion basada en fuentes publicas.
- Tavily se usa como motor de busqueda y extraccion.
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
12. Estado actual: auditoria de las 50 evidencias aceptadas y 5 ambiguas.

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

## 18. Script vigente para modificar

- `scripts\run_top50_tavily_due_diligence.py`

## 19. Decisiones tecnicas vigentes

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

## 21. Estado operativo final

FASE 2 EN CURSO.

Piloto V2 tecnico completado.
Auditoria real completada.
Dictamen: FAIL.
Lote 2 no autorizado.

NO ejecutar nuevas consultas Tavily.

Siguiente paso unico:

- redisenar la logica de aceptacion V3 sin usar Tavily.

## 22. Comandos utiles

Comandos de lectura y validacion, sin secretos:

```powershell
cd "C:\Proyectos\IPTV-Playlist-Builder-Premium"

python -m py_compile .\scripts\run_top50_tavily_due_diligence.py

python .\scripts\run_top50_tavily_due_diligence.py --pilot-brands "Krooz TV,Voco TV,DigitaLizard IPTV,Free Go TV,Sonix IPTV" --pause-seconds 1 --dry-run
```

## 23. Prompt de inicio para el nuevo hilo

Bloque listo para copiar y pegar:

```text
Continuamos el proyecto IPTV Playlist Builder Premium.

Lee primero:

docs/HANDOFF_2026-07-14_IPTV_RESEARCH_TAVILY_PHASE2.md

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

La siguiente tarea única es rediseñar la lógica de aceptación V3 en:

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
