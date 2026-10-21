---
name: ta-escaleta
description: Convierte una transcripción con tiempos en mapa de momentos, escaleta trazable y montaje de audio verificado. Úsala para episodios, avances o piezas cortas.
---

# Escaleta y montaje

## Lee primero

1. `conocimiento/montaje.md` y `conocimiento/teaser.md`.
2. La transcripción completa y `palabras.json` generados por `ta-transcribir`.
3. El canon indicado por `rutas.canon_privado` en `config.local.yaml`; si no existe, declara “modo genérico”.

## Corre

Escribe `cortes.json` con bloques, IDs, `master_in`, `master_out` y texto esperado. Resuelve los bordes con:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/buscar.py" palabras.json selecciones.json cortes.json
python3 "${CLAUDE_PLUGIN_ROOT}/bin/montar.py" MASTER cortes.json SALIDA --verificar
```

Ordena por valor narrativo, no solo por cronología. Cada bucle abierto debe declarar su pago o quedar marcado para retirar.

## Entrega

- Mapa de momentos con timecodes del máster y criterio editorial.
- Escaleta por bloques con aperturas y pagos.
- `edl.json` y audio `ENTREGA_montaje.wav` únicamente si la retranscripción confirma la primera y última palabra de cada corte.

## No hace

No decide el corte final por una puntuación automática, no promete un pago ausente y no publica audio, citas del máster ni decisiones del canon.

