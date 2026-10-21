# Taco Artist Editor

Plugin público de Claude Code para convertir material de diálogo en decisiones de edición trazables. Trabaja en español e inglés, prepara transcripciones por frase, escaletas y montajes de audio, subtítulos bloqueados por QA, notas de corte y fichas de referentes. El repositorio contiene el motor genérico; el canon del proyecto se carga en tiempo de ejecución y nunca se publica aquí.

## Requisitos

Claude Code, Python 3.11 o posterior, `ffmpeg`/`ffprobe` y `openai-whisper`. Para ingerir URLs también hace falta `yt-dlp`. Los tests no necesitan red ni esas herramientas externas.

## Instalación (5 pasos)

1. Clona el repositorio: `git clone https://github.com/tacotios/taco-artist-editor.git && cd taco-artist-editor`.
2. Añade el marketplace en Claude Code: `/plugin marketplace add ./`.
3. Instala el plugin: `/plugin install taco-artist-editor@taco-artist-editor`.
4. Crea la configuración local: `cp config.example.yaml config.local.yaml` y completa las rutas externas disponibles.
5. Comprueba la instalación: `python3 bin/verificar.py`.

Si `rutas.canon_privado` queda vacía, todas las skills funcionan en modo genérico y lo indican. La verificación pública falla cerrada cuando no están configurados los tres controles externos.

## Uso

### `ta-transcribir`

Pásale un máster de diálogo. Separa por pausas, detecta idioma en cada frase y entrega JSON con tiempos por palabra más una transcripción legible.

### `ta-escaleta`

Pásale la transcripción y el objetivo del corte. Devuelve mapa de momentos, escaleta con timecodes del máster y audio; el audio solo se marca como entrega tras retranscribir y comprobar sus bordes.

### `ta-subtitular`

Pásale el video y `palabras.json`. Genera un candidato, corre el QA y exige confirmación de revisión visual antes de crear `ENTREGA_*.mp4`.

### `ta-revisar-corte`

Pásale un EDL o una lista JSON de clips. Si hay canon privado configurado lo lee; devuelve notas por timecode, bucles sin pago, densidad y puntos que necesitan juicio editorial.

### `ta-referente`

Pásale una URL o una transcripción local. La transcripción completa queda ignorada en `.cache/`; solo entra una ficha con estructura, gancho, ritmo, bucles y citas breves.

## Actualización semanal

`python3 bin/sync_semanal.py --seco` muestra un plan estable sin escribir ni tocar git. `--rama` procesa la cola, verifica el repo y, solo si hay cambios, crea un commit local en `semanal/AAAA-MM-DD`. Nunca mezcla ni publica por sí solo.

## Pasos hacia fuera (preparados, no ejecutados)

Cada acción es deliberada y la realiza la persona responsable después de revisar el contenido:

1. Crear el remoto inicialmente no público: `gh repo create tacotios-wq/taco-artist-editor --private --source=. --remote=origin`.
2. Hacer el primer push: `git push -u origin main`.
3. Dar acceso de escritura a cada cuenta aprobada: `gh api -X PUT repos/tacotios-wq/taco-artist-editor/collaborators/<cuenta> -f permission=push`.
4. Instalar la tarea local de los domingos: `sed "s|__RUTA_REPO__|$PWD|g" sync/com.taco-artist-editor.semanal.plist > ~/Library/LaunchAgents/com.taco-artist-editor.semanal.plist && launchctl load ~/Library/LaunchAgents/com.taco-artist-editor.semanal.plist`.
5. Tras la revisión final, cambiar la visibilidad: `gh repo edit tacotios-wq/taco-artist-editor --visibility public`.

## Licencia

Todos los derechos reservados. No se concede una licencia abierta.

