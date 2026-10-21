# Inventario público

Fecha de corte: 2026-10-20. La allowlist ejecutable vive en `sync/ALLOWLIST.yaml`; esta tabla explica el destino editorial de cada entrada.

## Fuentes autorizadas

| Fuente | Forma | Destino | Motivo |
|---|---|---|---|
| `motor_subtitulos` | CÓDIGO | `bin/motor.py`, `bin/qa_subtitulos.py`, preset | Portar motor y puerta de QA sin rutas ni recursos privados. |
| `doctrina_subtitulos` | DESTILADO | `conocimiento/subtitulado.md` | Conservar ritmo, composición y verificación. |
| `montaje_automatico` | CÓDIGO | `bin/montar.py`, conocimiento | Reutilizar montaje genérico y EDL. |
| `matriz_montaje` | DESTILADO | `conocimiento/montaje.md` | Separar oficio general de doctrina ajena al formato. |
| `metodo_editor_master` | DESTILADO | `conocimiento/formato.md` | Conservar método y excluir estado de ciclos. |
| `manual_editor` | DESTILADO | `conocimiento/montaje.md` | Incorporar decisiones de edición repetibles. |
| `guias_formato_privado` | FUERA | configuración local | Leer el canon en ejecución sin copiarlo. |
| `sistema_sonoro_privado` | FUERA | configuración local | Mantener decisiones sonoras específicas en privado. |
| `biblia_formato_privado` | FUERA | configuración local | Evitar que estrategia y canon entren al motor público. |
| `pipeline_avances` | CÓDIGO | transcripción, búsqueda y montaje genéricos | Reescribir algoritmos con entradas JSON neutras. |
| `leyes_avances` | DESTILADO | `conocimiento/teaser.md` | Conservar leyes de curiosidad sin ejemplos de producción. |
| `referentes_publicos` | DESTILADO | fichas e índice; originales en `.cache/` | Publicar análisis propio y citas breves. |
| `broll_generico` | CÓDIGO | `bin/broll.py` | Buscar por ejes sin copiar clips. |
| `skills_edicion` | DESTILADO | cinco skills públicas | Adaptar oficio sin memoria ni rutas personales. |

## FUERA

- Másteres, transcripciones completas, escaletas, EDL, clips y encuestas de cualquier producción.
- Audio, video, imágenes de trabajo, fuentes tipográficas y cachés.
- Canon, estructura, música y decisiones específicas del proyecto; se leen solo desde configuración local.
- Actas, sesiones internas, comentarios sobre desempeño y conversaciones con terceros.
- Contratos, acuerdos, cifras, credenciales, tokens, archivos de entorno y claves.
- Memoria personal, registros médicos, documentación legal y proyectos no relacionados.
- Transcripciones completas de referentes; solo permanecen en `.cache/` por derechos de autor.

## Pendientes y riesgos vivos

- La detección automática de caras no entra porque exigiría una dependencia no disponible. El motor falla cerrado hasta que una persona confirma el visionado completo.
- Los cambios de código o doctrina privada se detectan por huella y preparan una revisión; no se copian automáticamente al repo público.
- La ingesta por URL necesita `yt-dlp` y subtítulos disponibles. Si faltan, se transcribe el audio localmente antes de crear la ficha.
- `ffmpeg`, `ffprobe` y `openai-whisper` son requisitos de ejecución; los tests los simulan y no usan red.
- Sin `rutas.canon_privado`, la revisión funciona en modo genérico y no afirma haber comprobado el canon.

