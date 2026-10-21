---
name: ta-referente
description: Convierte una entrevista o episodio público en una ficha de corte reutilizable sin guardar la transcripción completa. Úsala con una URL o archivo local.
---

# Analizar un referente

## Lee primero

1. `conocimiento/INDICE.md` para evitar duplicados y elegir ejes.
2. `conocimiento/teaser.md` y `conocimiento/formato.md` para separar observación de imitación.
3. La URL o transcripción local completa desde `.cache/`, nunca desde una carpeta versionada.

## Corre

Con una transcripción local:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/referente.py" --transcripcion ARCHIVO --url URL --titulo TITULO --formato FORMATO --salida FICHA.md
```

Con URL, el script usa `yt-dlp`; si faltan subtítulos, obtiene audio en `.cache/` y llama al transcriptor local.

## Entrega

Una ficha que abre con fuente y fecha e incluye estructura por minutos, gancho inicial, bucles y pagos, ritmo, silencios, qué adaptar y qué no. Cada cita tiene menos de 15 palabras y enlaza el original. Regenera `conocimiento/INDICE.md` después.

## No hace

No versiona audio, video ni transcripciones completas; no presenta hipótesis como resultados de retención y no copia la identidad visual o verbal del referente.

