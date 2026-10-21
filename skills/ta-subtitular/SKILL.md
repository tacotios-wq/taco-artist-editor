---
name: ta-subtitular
description: Renderiza subtítulos desde tiempos por palabra y bloquea la entrega hasta pasar QA mecánico y revisión visual. Úsala después de cerrar el texto del corte.
---

# Subtitular con QA

## Lee primero

1. `conocimiento/subtitulado.md` completo.
2. `palabras.json`, el video final y cualquier corrección numerada de una iteración anterior.
3. `sync/preset_subtitulos.json`; el preset es parte de la verificación y no se cambia durante un render.

## Corre

Primero genera candidato y reporte:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/motor.py" VIDEO DIRECTORIO --palabras palabras.json
```

Mira el video completo en movimiento y la hoja de eventos. Si texto, caras, interfaz, pausas y cortes están correctos, repite con `--revision-visual`; solo entonces puede aparecer `ENTREGA_*.mp4`.

## Entrega

- `subtitulos.ass`, `plan_subtitulos.json` y `candidato.mp4`.
- `QA_REPORTE.md` y `qa.json` con PASA o NO PASA.
- `ENTREGA_*.mp4` solo cuando no hay fallos bloqueantes y la revisión visual está confirmada.

## No hace

No entrega un candidato, no tapa caras deliberadamente, no llena pausas de voz y no sustituye el juicio en movimiento por una captura aislada.

