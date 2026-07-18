# Handoff — IPTV Bulk Ranking Harvest 01

Fecha: 2026-07-18
Tarea: `BRAND-FIRST-MARKET-UNIVERSE / BULK-RANKING-HARVEST-01 / DYNAMIC-SEARCH-INTEGRAL-RUNNER-01`

## Base autoritativa

- Repositorio: `C:\Proyectos\IPTV-Playlist-Builder-Premium`
- Rama: `main`
- HEAD inicial: `5d6c0b0a747358787e9ce07548d586d478a534d4`
- `origin/main` local inicial: `5d6c0b0a747358787e9ce07548d586d478a534d4`
- Divergencia inicial: `0/0`
- Working tree e index iniciales: limpios

## Archivos creados

- `scripts/run_bulk_ranking_harvest.py`
- `tests/test_run_bulk_ranking_harvest.py`
- `docs/BULK_RANKING_HARVEST_METHOD.md`
- `docs/HANDOFF_2026-07-18_IPTV_BULK_RANKING_HARVEST_01.md`

No se modificaron los runners históricos de BRAND-FIRST 1B.

## Diseño implementado

El nuevo runner es autocontenido y usa el SDK oficial `tavily-python`. Una única
ejecución autorizada recorre automáticamente:

`SEARCH -> DYNAMIC_SEARCH_FILTER -> MAP -> DOMAIN_PRODUCTIVITY_FILTER -> CRAWL -> EXTRACT_FALLBACK -> DYNAMIC_BRAND_FILTER -> CONSOLIDATE -> COMPLETE`

Incluye:

- 24 consultas congeladas, multirregión y multilingües;
- filtro determinístico de páginas de ranking con clasificación A–E;
- selección automática de hasta 10 dominios Map y cuatro dominios Crawl;
- Extract de respaldo de hasta 60 URLs en tres lotes de 20;
- clasificación de marcas, cola REVIEW y exclusiones de hardware/apps;
- deduplicación conservadora, ranking completo, Top 50 y Top 20;
- límite físico de 41 solicitudes, con un retry máximo y computado solo para
  429, 5xx o timeout;
- reserva antes de llamada, ledger, checkpoint, resume e integridad;
- raw completo en JSONL y salida normal compacta;
- escrituras atómicas, UTF-8, supporting row IDs y hashes.

## Validación offline

Se prepararon pruebas focalizadas con cliente Tavily falso para inventario,
parámetros SDK, filtro dinámico, selección automática, límites físicos y de
contenido, persistencia raw, aislamiento de consola, ranking, exclusiones,
REVIEW, retries, autenticación, presupuesto, checkpoint, resume, run completo,
secretos, UTF-8, atomicidad, schemas, hashes y bloque PowerShell.

Resultados de cierre offline:

- `py_compile`: PASS;
- `unittest` focalizado: 16 pruebas, 16 PASS;
- fake execution completa: 24 Search + 10 Map + 4 Crawl + 3 Extract, PASS;
- fake resume sin repetir operaciones completadas: PASS;
- `--dry-run`: PASS, 24 consultas, 27 outputs y máximo 41 requests;
- `--preflight`: PASS, plan hash
  `db3b88e7114cb057e24516c75d4a007a1ce838bd2adc5d34f368533acedf01d4`;
- parser PowerShell: PASS;
- `git diff --check`: PASS.

La ejecución Tavily real permanece pendiente. Durante esta preparación no se
leyó la clave, no se creó cliente real, no se usó red y no se consumieron
créditos.

## Ejecución futura única

Ejecutar solo después de revisión humana. El bloque comprueba presencia de la
variable sin imprimirla, ejecuta una vez y mantiene PowerShell abierto.

```powershell
& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No Tavily operation was made.'
        $runnerExitCode = 3
        $runnerOutput = @()
    }
    else {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'
        $runnerOutput = & python -B .\scripts\run_bulk_ranking_harvest.py --execute --approval-token 'BULK-RANKING-HARVEST-01' --execution-origin powershell 2>&1
        $runnerExitCode = $LASTEXITCODE
    }

    $runLine = $runnerOutput | Where-Object { $_ -like 'RUN_DIR=*' } | Select-Object -Last 1
    $runnerOutput | Where-Object { $_ -notlike 'RUN_DIR=*' } | ForEach-Object { Write-Output $_ }
    if ($runLine) { Write-Output $runLine }
    else { Write-Output 'RUN_DIR=NOT_CREATED_OR_NOT_REPORTED' }
    Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"
    Write-Output 'DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED'
    if ($runnerExitCode -eq 0) { Write-Output 'FINAL_STATE=COMPLETE_PENDING_HUMAN_REVIEW' }
    else { Write-Output 'FINAL_STATE=FAILED_OR_BLOCKED_DO_NOT_RETRY_AUTOMATICALLY' }
}
```

## Restricción de publicación

No hacer `git add`, commit ni push antes de que una persona revise el diff y las
validaciones. Después de la ejecución real, la única etapa prevista es revisión
humana de los artefactos `COMPLETE`; no debe repetirse automáticamente el run si
ya se imprimió un `RUN_DIR`.

## Actualización autoritativa — ejecución real y limpieza offline

Esta sección supersede el estado de preparación y el bloque PowerShell futuro
anteriores. Tavily ya fue ejecutado una vez y **no debe volver a ejecutarse**.

- Run autoritativo:
  `research/output/best_iptv_2026/brand_first_market_universe/bulk_ranking_harvest_01/run_20260718_180950`
- Estado: `COMPLETE`.
- Solicitudes físicas: 37.
- Search: 24; Map: 10; Crawl: 2; Extract: 1.
- Resultados Search: 240.
- Páginas útiles procesadas: 68.
- Candidatos únicos iniciales: 960.
- Errores Tavily: 0.

La revisión humana detectó sobreextracción material: frases promocionales,
encabezados, términos genéricos, players y hardware habían entrado en el ranking
inicial. Se ejecutó una sola pasada offline de higiene sobre los candidatos y su
contexto, sin modificar Search, Map, Crawl ni Extract.

Resultados finales:

- servicios IPTV plausibles: 106;
- REVIEW: 230;
- exclusiones totales: 589;
- variantes fusionadas de forma conservadora: 35;
- frases promocionales excluidas: 77;
- players/apps excluidos: 9;
- hardware excluido: 5;
- canales/plataformas excluidos: 22;
- términos genéricos excluidos: 55;
- otros falsos positivos excluidos: 421;
- reducción frente al universo inicial: 88,96 %;
- Top 50: 50 filas;
- Top 20: 20 filas, control de calidad `PASS`;
- reparaciones de mojibake: 0; los archivos ya contenían UTF-8 correcto;
- raw Search/Map/Crawl/Extract: byte-idéntico según SHA-256.

Top 50 final:

VocoTV; Krooz TV; IPTV Harmony; Xtreme HD IPTV; VIPSATV; Eaglecast TV;
OrigineTV; RealmIPTV; FreeGoTV; Kemo IPTV; Nexus IPTV; TereaTV; Yeah IPTV;
Flash 4K IPTV; Apollo Group TV; Double Click TV; OTTOcean; XCodes IPTV;
SofaIPTV; Zenora IPTV; MoaTV; VIRALIPTV; ReflexSat IPTV; ARISIPTV; Nikiptv;
Nexo Play IPTV; Play Brasil IPTV; Play Max IPTV; Play Plus IPTV; Play Pro IPTV;
Zap Plus IPTV; IPTV USAX; Velino TV; Flashline IPTV; Velvado IPTV;
Magnolia IPTV; StreamingNordic IPTV; VEROXIPTV; SerieIPTV; PerfectIPTV;
GreatestIPTV; KenoaTV; StrimoIPTV; Abble IPTV; Academus IPTV; AHE Brasil IPTV;
Batiste IPTV; Cine Libero IPTV; Generation IPTV; Home Refill IPTV.

Top 20 final:

1. VocoTV
2. Krooz TV
3. IPTV Harmony
4. Xtreme HD IPTV
5. VIPSATV
6. Eaglecast TV
7. OrigineTV
8. RealmIPTV
9. FreeGoTV
10. Kemo IPTV
11. Nexus IPTV
12. TereaTV
13. Yeah IPTV
14. Flash 4K IPTV
15. Apollo Group TV
16. Double Click TV
17. OTTOcean
18. XCodes IPTV
19. SofaIPTV
20. Zenora IPTV

Limitaciones:

- aparecer en rankings no confirma calidad;
- no confirma legalidad;
- no confirma oficialidad;
- no confirma funcionamiento real.

Los 230 casos REVIEW permanecen separados y no bloquean el lote.

Próxima tarea única:

`IPTV-SERVICE-REAL-WORLD-TESTING-01`

`TOP20-AVAILABILITY-TRIAL-AND-EPG-SCREEN-01`

Todavía no se ejecutaron pruebas reales ni se adquirieron suscripciones.
Continúa prohibido hacer commit o push antes de revisión humana.
