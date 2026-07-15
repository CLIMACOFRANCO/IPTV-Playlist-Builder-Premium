$ErrorActionPreference = "Stop"

$SourceUrl = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
$Mapping = Join-Path $PSScriptRoot "Premium_WeibPlayer_v1_matching_report.csv"
$Output = Join-Path $PSScriptRoot "custom_weib_epg.xml.gz"
$Builder = Join-Path $PSScriptRoot "build_custom_xmltv.py"

python $Builder `
  --source-url $SourceUrl `
  --mapping $Mapping `
  --output $Output

Write-Host ""
Write-Host "Archivo generado:"
Write-Host $Output
