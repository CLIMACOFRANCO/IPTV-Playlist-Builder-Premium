# Cierre formal: BRAND-FIRST Market Universe 1A

## Estado oficial

**Fecha de cierre:** 2026-07-17  
**Dictamen documental:** `BRAND_FIRST_MARKET_UNIVERSE_1A_OFFLINE_BASELINE_FROZEN_WITH_KNOWN_LIMITATIONS`

La fase queda congelada como baseline offline diagnóstico. El run autoritativo es `research/output/best_iptv_2026/brand_first_market_universe_1a/run_20260717_051437` y su hash lógico es `B2D3B232EE3FC0C345D48816B230A6A30D0DA67CC2ED53A4175B474D3FF40FF7`.

## Objetivo y cambio estratégico

El objetivo original de 1A fue reconstruir, exclusivamente desde el corpus local y de forma reproducible, un universo de mercado BRAND-FIRST para separar menciones, marcas canónicas, proveedores históricos y una superficie potencialmente trazable. La decisión estratégica fue pasar a BRAND-FIRST: la unidad primaria es `CANONICAL_BRAND`; los 692 `PROVIDER` históricos se preservan como una capa histórica independiente y no como una validación externa.

## Genealogía y cronología

La genealogía final es: **1.035 menciones → 757 registros canónicos depurados → 692 PROVIDER históricos → Top 50 histórico exacto**.

- Run inicial: estableció la reconstrucción offline y los entregables base.
- FIX1: corrigió controles de independencia y réplicas cross-host conservadoras.
- FIX2: añadió interpretación semántica, calidad de publicación, independencia, colisiones, score diagnóstico y elegibilidad sin reescribir los 692 históricos.
- FIX3: separó estrictamente ranking diagnóstico de readiness y limitó la publicación a `TRACEABLE_FOR_FUTURE_PRIORITIZATION`.
- FIX4: ajustó la calibración de compactación canónica frente a substring accidental y conservó los contratos previos.
- FIX5: fue iniciado y detenido manualmente; sus cambios parciales se deshicieron mediante Deshacer de Codex. No se creó un run FIX5 ni se considera una implementación completada.

## Resultado final del run FIX4 restaurado

- 1.035 menciones.
- 757 registros canónicos depurados.
- 692 `PROVIDER` históricos.
- Top 50 histórico exacto.
- 175 `PLAUSIBLE_BRAND`.
- 0 `TRACEABLE_FOR_FUTURE_PRIORITIZATION`.
- 0 adjudication-ready.
- 0 publicadas.

El resultado cero significa únicamente: **“Cero marcas publicables bajo el corpus local y los criterios FIX4”.** No significa cero marcas reales en el mercado, inexistencia de proveedores IPTV, ilegalidad, baja calidad comercial, ranking definitivo, validación externa ni adjudicación humana.

## Qué logró y qué no logró 1A

1A logró una línea base offline reproducible, trazable y con integridad comprobable: preservó los insumos históricos, mantuvo el Top 50 histórico exacto, calculó la capa diagnóstica sobre 692 PROVIDER y evitó seleccionar una marca para investigación externa.

1A no logró evidencia web nueva, independiente y trazable; tampoco confirmó identidad oficial, calidad comercial, legalidad, ranking definitivo, adjudicación humana ni publicación de una marca. La ausencia de una superficie publicable no debe transformarse en una conclusión de mercado.

## Limitaciones conocidas aceptadas

Permanecen documentados, sin que autoricen automáticamente FIX5:

- el validador no es totalmente independiente para score, semántica y colisiones;
- ciertos blockers tienen comparación unilateral;
- subsiste riesgo residual en el override compacto;
- la auditoría detectó pruebas duplicadas;
- las fechas de publicación ausentes impiden medir recencia;
- la independencia editorial de fuentes singleton sigue sin resolverse.

Estas limitaciones se aceptan porque no hay un defecto material demostrado que cambie las decisiones o resultados del baseline restaurado.

## Justificación de congelación y regla de reapertura

Se cancela FIX5 y se prohíbe continuar el ciclo de fixes offline. Congelar 1A conserva un punto de referencia íntegro, evita perfeccionismo no material y separa con claridad el diagnóstico local de la adquisición futura de evidencia externa.

1A solo podrá reabrirse ante un defecto material demostrado que cambie decisiones o resultados. No justifican reabrirla: un refactor, mejoras cosméticas, más pruebas sin impacto material, perfeccionismo formal, cambios de nombres u optimizaciones no necesarias.

## Niveles de decisión

- **Validación automatizada:** comprueba contratos, hashes, conteos, referencias y reglas implementadas.
- **Auditoría asistida por IA:** revisa coherencia, riesgos y documentación; no sustituye evidencia externa ni decisión humana.
- **Adjudicación humana:** determina si una evidencia concreta satisface un criterio de decisión.
- **Aprobación humana:** autoriza versionado, apertura de la siguiente fase o cualquier publicación.

## Integridad, Git y propuesta de versionado

El manifest del run autoritativo declara 19 entregables; sus 18 hashes no circulares coinciden con los archivos actuales. Los 10 insumos históricos permanecen intactos. El hash lógico autoritativo coincide con el valor indicado arriba. El estado Git de partida corresponde a `main`, con `HEAD` y `origin/main` en `dbff5acf83dd35064249bde69c007178eb97bf33`, sin divergencia.

Los archivos propuestos para versionar, sujetos a aprobación humana posterior, son:

- `docs/BRAND_FIRST_1A_OFFLINE_BASELINE_CLOSURE.md` (este cierre).
- `docs/BRAND_FIRST_RESEARCH_METHOD.md` (método congelado existente).
- `scripts/build_brand_first_market_universe.py` (runner congelado existente).
- `tests/test_build_brand_first_market_universe.py` (pruebas congeladas existentes).

No se hizo `git add`, commit, push ni Pull Request en este cierre.

## Tavily y siguiente fase

No hubo Tavily durante 1A: el baseline utilizó únicamente el corpus local. Esta fase no leyó `TAVILY_API_KEY`, no cargó `.env`, no hizo red y no seleccionó una marca para investigación externa.

Tras un commit aprobado por una persona, queda autorizada metodológicamente la apertura de 1B. Su objetivo preliminar es adquirir evidencia web nueva, independiente y trazable. El flujo previsto será: **Search → Extract → Map → Crawl → Research**. 1B no podrá interpretar este baseline como un ranking definitivo.

## Riesgos abiertos y próxima tarea única

Persisten riesgos de evidencia local incompleta, identidad de marca no resuelta, independencia editorial insuficiente y ausencia de recencia verificable. Se mantienen explícitos para que no se conviertan en inferencias comerciales, legales o de calidad.

**Próxima tarea única:** solicitar aprobación humana para revisar y versionar exactamente los cuatro archivos propuestos; solo después, abrir 1B con adquisición de evidencia web nueva, independiente y trazable.

## Dictamen de cierre

`BRAND_FIRST_MARKET_UNIVERSE_1A_OFFLINE_BASELINE_FROZEN_WITH_KNOWN_LIMITATIONS`

El baseline FIX4 restaurado es apto como cierre documental y como referencia offline, con las limitaciones conocidas expresamente preservadas. No constituye ranking definitivo, validación externa, adjudicación humana ni aprobación humana.
