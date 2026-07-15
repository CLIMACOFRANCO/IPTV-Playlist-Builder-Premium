# Generador XMLTV personalizado para Weib Player TV

Este paquete genera `custom_weib_epg.xml.gz`, cuya programación procede de
EPGShare, pero cuyos nombres de canal coinciden con los nombres exactos del
proveedor Xtream Codes.

## Archivos

- `build_custom_xmltv.py`: generador.
- `build_custom_xmltv.ps1`: ejecución directa desde PowerShell.
- `Premium_WeibPlayer_v1_matching_report.csv`: mapa de canales ya calculado.

## Ejecución en Windows

1. Coloque los tres archivos en la misma carpeta.
2. Abra PowerShell en esa carpeta.
3. Ejecute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_custom_xmltv.ps1
```

El proceso descarga el XMLTV global de EPGShare y genera:

```text
custom_weib_epg.xml.gz
```

## Publicación

Weib Player necesita una URL HTTP/HTTPS. El archivo generado debe publicarse en
un alojamiento accesible por Internet, como un servidor web, un bucket de
almacenamiento o un repositorio con entrega de archivos estáticos.

## Importante

La versión v1 usa únicamente coincidencias automáticas de confianza alta.
Actualmente contiene mapeos para 1.850 entradas de la playlist. Las demás se
mantienen fuera para evitar programación incorrecta.
