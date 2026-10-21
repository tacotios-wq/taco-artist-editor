Fuente: manuales locales de edición y scripts de montaje (destilado) · Fecha: 2026-10-20

# Montaje trazable

## Entrada mínima

Cada corte declara ID, bloque, `master_in`, `master_out` y el texto esperado. El timecode siempre pertenece al máster; la EDL añade por separado el tiempo del montaje.

## Secuencia de trabajo

1. Leer el transcript completo antes de seleccionar frases.
2. Construir un mapa de momentos: cambio, conflicto, decisión, reacción, información y aire.
3. Ordenar una escaleta donde cada bloque cambie la pregunta o pague una anterior.
4. Resolver bordes por primera y última palabra, no a ojo por segundos enteros.
5. Montar con aire corto entre frases y mayor entre bloques.
6. Retranscribir el candidato y comparar la primera y última palabra de cada corte.

`bin/montar.py` escribe siempre candidato, EDL y verificación. Solo copia `ENTREGA_montaje.wav` cuando todos los bordes coinciden.

## Decisiones editoriales

- El transcript ayuda a buscar, pero no representa miradas, acciones ni silencios.
- Una puntuación puede ordenar opciones; nunca decide el corte final.
- Una reacción puede ser el pago de una frase anterior.
- La continuidad emocional manda sobre el orden cronológico cuando la verdad del material se conserva.
- Todo silencio retirado necesita una razón; la velocidad uniforme aplana el carácter.

