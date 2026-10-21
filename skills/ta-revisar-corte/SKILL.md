---
name: ta-revisar-corte
description: Revisa un corte o EDL contra reglas de edición y, cuando está configurado, contra el canon privado. Úsala para obtener notas accionables por timecode.
---

# Revisar un corte

## Lee primero

1. `conocimiento/formato.md`, `conocimiento/montaje.md` y `conocimiento/sonido.md`.
2. El EDL o JSON de clips y las notas de intención del corte.
3. El archivo de `rutas.canon_privado` si está configurado. Si no lo está, declara “revisión genérica; canon no comprobado”.

## Corre

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/revisar_corte.py" CORTE_JSON REPORTE.md --config config.local.yaml
```

Usa el reporte mecánico como punto de partida. Ve el corte completo y añade por timecode qué rompe, qué sobra, dónde falta silencio y qué apertura no obtiene pago.

## Entrega

Notas ordenadas por timecode, con evidencia, impacto y acción propuesta. Separa fallos verificables de decisiones que necesitan aprobación humana.

## No hace

No inventa reglas del canon, no aprueba cambios de canon, no confunde densidad con calidad y no modifica el corte por su cuenta.

