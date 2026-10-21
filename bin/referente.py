#!/usr/bin/env python3
"""Convierte una transcripción local o URL pública en una ficha breve de corte."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ta_core import escribir_texto_atomico, segundos, timecode


MARCA = re.compile(r"^\[(\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d+)?\]\s*(.*)$")
MARCA_VTT = re.compile(r"^(\d{2}:)?\d{2}:\d{2}[.,]\d{3}\s+-->\s+")


def parsear_transcripcion(texto: str) -> list[dict[str, Any]]:
    entradas: list[dict[str, Any]] = []
    lineas = texto.splitlines()
    indice = 0
    while indice < len(lineas):
        linea = lineas[indice].strip()
        marca = MARCA.match(linea)
        if marca:
            tc = linea[1: linea.index("]")]
            contenido = linea[linea.index("]") + 1:].strip()
            if contenido:
                entradas.append({"inicio": segundos(tc), "texto": re.sub(r"<[^>]+>", "", contenido)})
            indice += 1
            continue
        if MARCA_VTT.match(linea):
            inicio = linea.split("-->", 1)[0].strip()
            contenido: list[str] = []
            indice += 1
            while indice < len(lineas) and lineas[indice].strip():
                parte = re.sub(r"<[^>]+>", "", lineas[indice].strip())
                if parte and parte not in contenido:
                    contenido.append(parte)
                indice += 1
            if contenido:
                entradas.append({"inicio": segundos(inicio), "texto": " ".join(contenido)})
            continue
        indice += 1
    unicas: list[dict[str, Any]] = []
    for entrada in entradas:
        if not unicas or entrada != unicas[-1]:
            unicas.append(entrada)
    return unicas


def cita_corta(texto: str, max_palabras: int = 14) -> str:
    palabras = texto.replace("\n", " ").split()
    return " ".join(palabras[:max_palabras]).strip(" -")


def ficha_desde_entradas(
    entradas: list[dict[str, Any]], *, url: str, titulo: str, formato: str, fecha: str | None = None
) -> str:
    if not entradas:
        raise ValueError("La transcripción no contiene marcas de tiempo reconocibles")
    fecha = fecha or date.today().isoformat()
    duracion = max(float(e["inicio"]) for e in entradas)
    bloques = []
    cursor = 0
    while cursor <= int(duracion // 300) * 300:
        grupo = [e for e in entradas if cursor <= float(e["inicio"]) < cursor + 300]
        if grupo:
            palabras = sum(len(e["texto"].split()) for e in grupo)
            muestra = cita_corta(grupo[0]["texto"], 10)
            bloques.append((cursor, min(cursor + 300, int(duracion) + 1), palabras, muestra))
        cursor += 300
    hook = next((e for e in entradas if float(e["inicio"]) <= 30), entradas[0])
    preguntas = [e for e in entradas if "?" in e["texto"]][:3]
    intervalos = [b["inicio"] - a["inicio"] for a, b in zip(entradas, entradas[1:]) if b["inicio"] > a["inicio"]]
    mediana = statistics.median(intervalos) if intervalos else 0.0
    lineas = [
        f"Fuente: {url} · Fecha: {fecha}",
        "",
        f"# {titulo}",
        "",
        f"Formato: {formato}",
        "",
        "Ejes: gancho, entrevista, ritmo, cierre",
        "",
        "## Estructura observada",
        "",
        "| Tramo | Densidad aproximada | Inicio del bloque |",
        "|---|---:|---|",
    ]
    lineas += [
        f"| {timecode(a)[:8]}–{timecode(b)[:8]} | {n} palabras | “{muestra}” |" for a, b, n, muestra in bloques
    ]
    lineas += [
        "",
        "## Gancho",
        "",
        f"Abre con una afirmación o intercambio antes de explicar el contexto: “{cita_corta(hook['texto'])}” ({timecode(hook['inicio'])[:8]}).",
        "",
        "## Bucles y pagos",
        "",
    ]
    if preguntas:
        lineas += [
            f"- Pregunta en {timecode(p['inicio'])[:8]}: “{cita_corta(p['texto'])}”. Revisar el bloque posterior para localizar el pago."
            for p in preguntas
        ]
    else:
        lineas.append("- La puntuación del transcript no permite detectar preguntas con confianza; revisar a oído.")
    lineas += [
        "",
        "## Ritmo y silencios",
        "",
        f"Las entradas del transcript aparecen cada {mediana:.1f}s de mediana. Es una medida de muestreo, no de cortes visuales.",
        "",
        "## Qué adaptar",
        "",
        "- Entrar en conflicto o carácter antes de explicar antecedentes.",
        "- Pagar una curiosidad pequeña antes de abrir la siguiente.",
        "- Dejar respirar las reacciones que cambian el sentido de la respuesta.",
        "",
        "## Qué no copiar",
        "",
        "- La identidad verbal, los chistes o la puesta en escena propios del formato.",
        "- La cadencia inferida solo desde subtítulos; debe comprobarse viendo el original.",
    ]
    return "\n".join(lineas) + "\n"


def _url_permitida(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}


def descargar_transcripcion(url: str, cache: Path, yt_dlp: str) -> tuple[Path, str]:
    if not _url_permitida(url):
        raise ValueError("Solo se aceptan URLs públicas de YouTube")
    if shutil.which(yt_dlp) is None:
        raise RuntimeError(f"No se encontró la herramienta: {yt_dlp}")
    cache.mkdir(parents=True, exist_ok=True)
    clave = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    metadatos = subprocess.run(
        [yt_dlp, "--dump-single-json", "--skip-download", url], text=True, capture_output=True, check=True
    )
    info = json.loads(metadatos.stdout)
    plantilla = str(cache / f"{clave}.%(ext)s")
    subprocess.run(
        [yt_dlp, "--write-subs", "--write-auto-subs", "--sub-langs", "es,en,es-.*,en-.*",
         "--sub-format", "vtt", "--skip-download", "-o", plantilla, url],
        check=True,
    )
    candidatos = sorted(cache.glob(f"{clave}*.vtt"))
    if not candidatos:
        raise RuntimeError("La URL no ofrece subtítulos; descarga audio y usa ta-transcribir localmente")
    return candidatos[0], str(info.get("title", "Referencia pública"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    origen = parser.add_mutually_exclusive_group(required=True)
    origen.add_argument("--transcripcion", type=Path)
    origen.add_argument("--url-remota")
    parser.add_argument("--url", required=True)
    parser.add_argument("--titulo", default="Referencia pública")
    parser.add_argument("--formato", default="entrevista")
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path(".cache/referencias"))
    parser.add_argument("--yt-dlp", default="yt-dlp")
    args = parser.parse_args()
    try:
        titulo = args.titulo
        if args.url_remota:
            if args.url_remota != args.url:
                raise ValueError("--url-remota y --url deben señalar el mismo original")
            transcripcion, titulo_remoto = descargar_transcripcion(args.url, args.cache, args.yt_dlp)
            titulo = titulo_remoto if args.titulo == "Referencia pública" else args.titulo
        else:
            transcripcion = args.transcripcion
            if not transcripcion or not transcripcion.is_file():
                raise ValueError("No existe la transcripción local")
        entradas = parsear_transcripcion(transcripcion.read_text(encoding="utf-8", errors="replace"))
        ficha = ficha_desde_entradas(entradas, url=args.url, titulo=titulo, formato=args.formato)
        escribir_texto_atomico(args.salida, ficha)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"HECHO: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

