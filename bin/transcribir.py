#!/usr/bin/env python3
"""Transcripción es/en por frase con detección de idioma y tiempos por palabra."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ta_core import escribir_json, escribir_texto_atomico, timecode


MUESTRA_HZ = 16000


def puntos_silencio(stderr: str) -> list[float]:
    inicios = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", stderr)]
    finales = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", stderr)]
    return [(a + b) / 2 for a, b in zip(inicios, finales) if b >= a]


def plan_frases(total: float, cortes: list[float], minimo: float = 0.6, maximo: float = 18.0) -> list[tuple[float, float]]:
    """Crea frases por pausas; parte tramos largos y une residuos demasiado cortos."""
    if total <= 0:
        return []
    limites = [0.0] + sorted({round(c, 3) for c in cortes if 0 < c < total}) + [total]
    crudos: list[tuple[float, float]] = []
    for inicio, fin in zip(limites, limites[1:]):
        cursor = inicio
        while fin - cursor > maximo:
            crudos.append((cursor, cursor + maximo))
            cursor += maximo
        if fin > cursor:
            crudos.append((cursor, fin))
    unidos: list[list[float]] = []
    for inicio, fin in crudos:
        if unidos and fin - inicio < minimo:
            unidos[-1][1] = fin
        else:
            unidos.append([inicio, fin])
    if len(unidos) > 1 and unidos[0][1] - unidos[0][0] < minimo:
        unidos[1][0] = unidos[0][0]
        unidos.pop(0)
    return [(round(a, 3), round(b, 3)) for a, b in unidos]


def duracion(path: Path, ffprobe: str) -> float:
    proceso = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        text=True,
        capture_output=True,
        check=True,
    )
    return float(proceso.stdout.strip())


def detectar_silencios(path: Path, ffmpeg: str) -> list[float]:
    proceso = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path), "-af", "silencedetect=noise=-35dB:d=0.38", "-f", "null", "-"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proceso.returncode != 0:
        raise RuntimeError(proceso.stderr.strip() or "ffmpeg no pudo leer el máster")
    return puntos_silencio(proceso.stderr)


def elegir_idioma(probabilidades: dict[str, float]) -> tuple[str, float]:
    idioma = "es" if probabilidades.get("es", 0.0) >= probabilidades.get("en", 0.0) else "en"
    return idioma, float(probabilidades.get(idioma, 0.0))


def transcribir(master: Path, modelo_nombre: str, ffmpeg: str, ffprobe: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import whisper  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Falta openai-whisper; instala el paquete para transcribir") from exc

    total = duracion(master, ffprobe)
    rangos = plan_frases(total, detectar_silencios(master, ffmpeg))
    audio = whisper.load_audio(str(master))
    modelo = whisper.load_model(modelo_nombre)
    segmentos: list[dict[str, Any]] = []
    palabras: list[dict[str, Any]] = []
    for indice, (inicio, fin) in enumerate(rangos, 1):
        muestra = audio[int(inicio * MUESTRA_HZ): int(fin * MUESTRA_HZ)]
        if len(muestra) < int(0.1 * MUESTRA_HZ):
            continue
        mel = whisper.log_mel_spectrogram(
            whisper.pad_or_trim(muestra), n_mels=modelo.dims.n_mels
        ).to(modelo.device)
        _, probabilidades = modelo.detect_language(mel)
        idioma, confianza_idioma = elegir_idioma(probabilidades)
        resultado = modelo.transcribe(
            muestra,
            language=idioma,
            task="transcribe",
            fp16=False,
            word_timestamps=True,
            condition_on_previous_text=False,
            temperature=0.0,
        )
        textos: list[str] = []
        confianza_segmento: list[float] = []
        for segmento in resultado.get("segments", []):
            texto = segmento.get("text", "").strip()
            if texto:
                textos.append(texto)
            confianza_segmento.append(1.0 - float(segmento.get("no_speech_prob", 0.0)))
            for palabra in segmento.get("words", []):
                token = palabra.get("word", "").strip()
                if not token:
                    continue
                palabras.append(
                    {
                        "texto": token,
                        "inicio": round(inicio + float(palabra["start"]), 3),
                        "fin": round(inicio + float(palabra["end"]), 3),
                        "idioma": idioma,
                        "confianza": round(float(palabra.get("probability", 1.0)), 4),
                    }
                )
        if textos:
            segmentos.append(
                {
                    "id": f"f{indice:04d}",
                    "inicio": inicio,
                    "fin": fin,
                    "idioma": idioma,
                    "confianza_idioma": round(confianza_idioma, 4),
                    "confianza_voz": round(sum(confianza_segmento) / max(1, len(confianza_segmento)), 4),
                    "texto": " ".join(textos),
                }
            )
        print(f"[{indice}/{len(rangos)}] {timecode(inicio)} {idioma}", flush=True)
    return segmentos, palabras


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--modelo", default="large-v3-turbo")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()

    if not args.master.is_file():
        parser.error(f"No existe el máster: {args.master}")
    for herramienta in (args.ffmpeg, args.ffprobe):
        if shutil.which(herramienta) is None:
            parser.error(f"No se encontró la herramienta: {herramienta}")
    args.salida.mkdir(parents=True, exist_ok=True)
    try:
        segmentos, palabras = transcribir(args.master, args.modelo, args.ffmpeg, args.ffprobe)
    except (RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    escribir_json(args.salida / "segmentos.json", segmentos)
    escribir_json(args.salida / "palabras.json", palabras)
    lineas = [f"# Transcripción · {args.master.name}", ""]
    lineas += [f"[{timecode(s['inicio'])}] ({s['idioma']}) {s['texto']}" for s in segmentos]
    dudosas = [p for p in palabras if p.get("confianza", 1.0) < 0.5]
    lineas += ["", "## Palabras de confianza baja", ""]
    lineas += [f"- {timecode(p['inicio'])} · `{p['texto']}` · {p['confianza']:.2f}" for p in dudosas]
    if not dudosas:
        lineas.append("- Ninguna por debajo de 0.50.")
    escribir_texto_atomico(args.salida / "TRANSCRIPCION.md", "\n".join(lineas) + "\n")
    print(f"HECHO: {len(segmentos)} frases, {len(palabras)} palabras, {len(dudosas)} dudosas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

