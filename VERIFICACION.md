Fuente: bin/verificar.py · Fecha: 2026-10-29

# Verificación

**PASA** · ejecución 2026-10-29T12:26:54-06:00

| Control | Resultado | Evidencia |
|---|---|---|
| `estructura_plugin` | PASA | 2 manifests JSON válidos y 5 skills completas |
| `allowlist` | PASA | 16 fuentes declaradas con forma, destino y motivo |
| `conocimiento` | PASA | 10 archivos con cabecera; 3 fichas |
| `archivos_publicos` | PASA | 52 archivos visibles; sin multimedia ni archivos mayores de 2 MB |
| `tests` | PASA | ----------------------------------------------------------------------; Ran 33 tests in 0.903s; OK |
| `sync_seco` | PASA | evitado para no crear recursión |
| `detector_fugas` | PASA | FUGAS DURAS: 0 |
| `detector_externo` | PASA | FUGAS DURAS (audiencia externa): 0 |
| `filtro_publico` | PASA | 0 términos encontrados |

## Comandos ejecutados

- `validar manifests y cinco skills`
- `validar sync/ALLOWLIST.yaml`
- `comprobar cabeceras y fichas`
- `revisar tamaño, extensiones y rutas`
- `python3 -m unittest discover -s tests`
- `sync seco omitido por llamada interna`
- `detector de fugas <repo>`
- `detector de audiencia externa <repo>`
- `filtro público`

## Resultado

La salida se generó desde los procesos reales. Las rutas de los detectores permanecen en la configuración local ignorada.
