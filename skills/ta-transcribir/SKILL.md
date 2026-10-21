---
name: ta-transcribir
description: Transcribe un máster de diálogo español-inglés por frase, conservando el idioma y los tiempos por palabra. Úsala al recibir audio o video antes de construir una escaleta.
---

# Transcribir diálogo bilingüe

## Lee primero

1. `config.local.yaml`, si existe, para elegir el modelo y las herramientas.
2. `conocimiento/subtitulado.md`, en especial la separación por pausas y la regla de no fijar un idioma para todo el archivo.

## Corre

Ejecuta:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/transcribir.py" MASTER SALIDA
```

Si faltan `ffmpeg`, `ffprobe` u `openai-whisper`, detente con el error concreto. No cambies a traducción ni fijes un idioma global. Revisa las palabras de confianza baja escuchando el máster.

## Entrega

- `segmentos.json`: frases con inicio, fin, idioma y confianza.
- `palabras.json`: tiempos por palabra para cortes y subtítulos.
- `TRANSCRIPCION.md`: texto bilingüe con timecodes.
- Una lista explícita de palabras dudosas.

## No hace

No traduce, no resume, no inventa hablantes y no copia el máster ni la transcripción completa al repositorio del plugin. El material de trabajo permanece fuera o en `.cache/`.

