Fuente: OpenFilm commit de5a98b y sus pruebas MIT (destilado) · Fecha: 2026-10-29

# OpenFilm aplicado al editor

## Inventario módulo a módulo

| Módulo de OpenFilm | Forma | Destino | Decisión y motivo |
|---|---|---|---|
| `studio/server/nle.mjs` | CODIGO | `bin/nle_export.py` | Se portan cadencias exactas, cadencia nativa por medio, frames por borde, timecode de origen desde el plan o `ffprobe`, XMEML v4 y rutas de medios. |
| `studio/server/fcpxml.mjs` | CODIGO | `bin/nle_export.py` | Se porta FCPXML 1.10 con storyline, huecos, formato nativo de cada fuente, coordenada absoluta del asset y formato DF o NDF en sus clips. |
| `studio/server/jianying.mjs` | CODIGO | `bin/nle_export.py` | Se porta el borrador mínimo de CapCut con materiales, segmentos y microsegundos. |
| `studio/server/markers.mjs` | CODIGO | `bin/nle_export.py` | Se adapta a un marcador en la primera aparición de cada bloque del EDL. |
| `studio/ui/src/lib/subtitles.ts` | CODIGO | `bin/vtt.py` | Se conserva el modelo de cues que usa el editor, sin portar React ni la API. |
| `studio/ui/src/lib/subtitle-cues.ts` | CODIGO | `bin/vtt.py` | Se conservan inicios por palabra y tiempos de cue. El final intermedio se estima con el inicio siguiente y se marca con `fin_estimado`. |
| `studio/server/transcripts.mjs` | CODIGO | `bin/vtt.py` | Se porta la serialización y lectura WebVTT con etiquetas de inicio internas; solo la última palabra conserva el final real del cue. |
| `nle-timecode.test.mjs` | CODIGO | `tests/test_nle_export.py` | Se portan NTSC, timecode NDF/DF y límites de minuto drop-frame. |
| `fcpxml.test.mjs` | CODIGO | `tests/test_nle_export.py` | Se portan XML bien formado, tiempos racionales, huecos, orden y rutas codificadas. |
| `jianying.test.mjs` | CODIGO | `tests/test_nle_export.py` | Se portan orden de segmentos, microsegundos, biblioteca y metadatos de borrador. |
| `markers.test.mjs` | CODIGO | `tests/test_nle_export.py` | Se porta orden y unicidad, adaptados de marcador libre a bloque editorial. |
| Pruebas de subtítulos | CODIGO | `tests/test_vtt.py` | Se portan tiempos internos, voz, etiquetas, multilínea e ida y vuelta. |
| Diez skills oficiales | DESTILADO | esta ficha | Se extraen criterios aplicables a teasers y reels de entrevista. |
| UI, servidor HTTP y proveedores | FUERA | ninguno | No hacen falta para abrir el primer corte en un NLE. |
| Render, transcodificación y descarga | FUERA | ninguno | El editor enlaza el máster existente y no usa red, `npx` ni servicios. |
| `look.mjs` y comprobación de frames | FUERA | pendiente | Requiere Chromium y render; no forma parte del exportador stdlib. |

## Cobertura y puntuación de aprovechamiento

La puntuación es **76 de 100**. El método asigna puntos antes de evaluar: cadencias y timecode 15, FCP7 15, FCPXML 15, CapCut 15, marcadores 10, WebVTT 15, adaptación de palabras 5 y verificación temporal independiente 10. La implementación obtiene 14 + 13 + 13 + 10 + 8 + 13 + 5 + 0. No se concede 15/15 a una capacidad que aún dependa de importación real o pierda información que el formato no representa. CapCut recibe la penalización mayor por su esquema privado cambiante. La verificación temporal independiente sigue ausente.

| Capacidad | Puntos | Evidencia local |
|---|---:|---|
| Cadencias y timecode | 14/15 | Casos 23.976 en secuencia 29.97 y 25 en secuencia 30 comprueban por separado frames de origen, posición de montaje y timecode no nulo. El plan tiene prioridad; `ffprobe` conserva la cadencia aunque no haya etiqueta de timecode y su fallo es tolerante. |
| FCP7 para Premiere y Resolve | 13/15 | XMEML v4 con cadencia nativa en fichero, duración e in/out, cadencia de secuencia en start/end, vídeo, audio, timecode y marcadores; falta importación real. |
| Final Cut | 13/15 | FCPXML 1.10 con formato y tiempos racionales nativos por asset, start del clip en la coordenada absoluta del asset, offset de secuencia y huecos; falta importación real. |
| CapCut | 10/15 | Contenido, metadatos, biblioteca y segmentos; faltan importación real y estabilidad del esquema. |
| Marcadores | 8/10 | Uno por bloque en los tres destinos; falta inspección dentro de las aplicaciones. |
| WebVTT | 13/15 | Conserva inicios y el final real de cada cue. Los finales intermedios se estiman y se declaran con `fin_estimado: true`. |
| Adaptación de `palabras.json` | 5/5 | Claves españolas y aliases de los formatos de origen. |
| Método temporal independiente | 0/10 | Ausente, se detalla abajo. |

## Criterios de las diez skills para teasers y reels de entrevista

Estos criterios se aplican al material de entrevista. No se portan las skills completas, porque el objetivo es conservar decisiones editoriales verificables, no el sistema de generación de OpenFilm.

| Skill | Criterio útil para entrevista |
|---|---|
| `long-to-short` | Abrir con la línea real más fuerte, conservar condición y contexto, cerrar en la idea y cortar en pausas. |
| `presenter-pip` | Hacer coincidir cada apoyo visual con las palabras y no tapar cara, subtítulos ni controles de móvil. |
| `motion-graphics` | Mostrar cifras, nombres y afirmaciones exactamente como fueron dados, con un elemento legible por vez. |
| `collage` | Usar cada recorte por su significado, declarar su procedencia y no alterar caras. |
| `keynote` | Sostener cada afirmación con una prueba real en pantalla y mantener una afirmación por momento. |
| `screen-demo` | Enseñar producto real, retirar esperas sin fingir rendimiento y ocultar datos privados en cada frame. |
| `whiteboard` | Dibujar cada concepto al ser nombrado, mantener términos correctos y dejar el contenido editable. |
| `lyric-video` | Hacer llegar cada palabra dentro de dos frames y medir el ajuste con un método independiente. Para entrevista se adopta como estándar de subtítulos, no como estética. |
| `replicate` | Comparar los mismos instantes, separar referencia de materiales usados y declarar qué se conserva o cambia. |
| `vintage-film` | No cambiar personas ni hechos, obtener nombres y fechas de fuentes reales y mantener a quien importa dentro del encuadre. |

## Verificación tipo look

Según el README de OpenFilm, `look` dibuja cada frame de su hoja dos veces y usa dos órdenes mezclados. `packages/openfilm/src/look.mjs` compara las dos imágenes del mismo instante y nombra los instantes que cambian. También informa errores de página, fuentes que no cargan, archivos de sonido ausentes y texto cortado por el frame o por su caja. No compara contra una referencia externa.

Para este editor, una adaptación futura podría renderizar frames alrededor de cada corte y comprobar determinismo, encuadre, continuidad y presencia del marcador. Esa comprobación no se ha portado: los entregables actuales se validan por estructura, orden y tiempos, no por imagen renderizada.

OpenFilm tampoco aporta en las piezas portadas una verificación de tiempos independiente del transcript. Sus marcas de palabra siguen siendo la fuente de tiempo. Por tanto, la verificación independiente está **ausente**. Para cerrarla habría que medir contra audio o frames con una segunda herramienta y publicar error máximo y error medio.

## Uso operativo

Exportar el `edl.json` escrito por `montar.py`:

```sh
python3 bin/nle_export.py salida_montaje/edl.json salida_nle --master material/entrevista.mov --fps 29.97
```

La carpeta contiene `premiere-resolve.xml`, `final-cut.fcpxml`, `capcut/draft_content.json` y `capcut/draft_meta_info.json`. El plan de ejemplo autocontenido está en `tests/test_nle_export.py` y su caso CLI ejecuta los cuatro archivos sin medios reales.

El plan puede declarar `source_timecode` y `source_fps` en cada clip, o un objeto `media_timecodes` cuyas claves son las rutas de los medios y cuyos valores tienen `value` y `fps`. La declaración del plan tiene prioridad. Si no existe, el exportador consulta con `ffprobe` la cadencia y el timecode de los medios presentes. Si `ffprobe` falta o falla, usa la cadencia de secuencia, exporta `00:00:00:00`, escribe un aviso y continúa.

Crear WebVTT desde `palabras.json` y recuperarlo:

```sh
python3 bin/vtt.py escribir palabras.json subtitulos.vtt
python3 bin/vtt.py leer subtitulos.vtt palabras_restauradas.json
```

## Pendientes y límites

- Abrir los XML en Premiere, DaVinci Resolve y Final Cut sobre material real.
- Copiar el borrador a una instalación concreta de CapCut y adaptar su versión si cambia el esquema privado.
- Verificar marcadores y enlaces de medios dentro de cada aplicación.
- Añadir la comprobación temporal independiente descrita en la sección anterior.
- WebVTT no guarda por separado el final de cada palabra intermedia. La lectura no lo inventa como dato real: usa el inicio siguiente y marca `fin_estimado: true`; la última palabra del cue conserva su fin real con `fin_estimado: false`.
