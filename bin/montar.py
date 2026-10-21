#!/usr/bin/env python3
"""Monta cortes de audio desde JSON y bloquea la entrega hasta retranscribirlos."""

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

from ta_core import cargar_json, escribir_json, normalizar, palabras_de


def validar_cortes(cortes: list[dict[str, Any]]) -> None:
    ids = set()
    for corte in cortes:
        identificador = str(corte.get("id", ""))
        if not identificador or identificador in ids:
            raise ValueError("Cada corte necesita un id único")
        ids.add(identificador)
        inicio, fin = float(corte["master_in"]), float(corte["master_out"])
        if inicio < 0 or fin <= inicio:
            raise ValueError(f"Corte {identificador} sin rango positivo")
        if not str(corte.get("texto", "")).strip():
            raise ValueError(f"Corte {identificador} sin texto esperado")


def construir_plan(
    cortes: list[dict[str, Any]], aire_frase: float = 0.30, aire_bloque: float = 0.70, cola: float = 1.0
) -> tuple[list[tuple[Any, ...]], list[dict[str, Any]], float]:
    validar_cortes(cortes)
    piezas: list[tuple[Any, ...]] = []
    edl: list[dict[str, Any]] = []
    tiempo = 0.0
    bloque_anterior = None
    for numero, corte in enumerate(cortes, 1):
        bloque = corte.get("bloque", "sin-bloque")
        if bloque_anterior is not None:
            aire = aire_bloque if bloque != bloque_anterior else aire_frase
            piezas.append(("silencio", aire))
            tiempo += aire
        inicio, fin = float(corte["master_in"]), float(corte["master_out"])
        piezas.append(("clip", inicio, fin))
        edl.append(
            {
                "n": numero,
                "id": corte["id"],
                "bloque": bloque,
                "montaje_in": round(tiempo, 3),
                "montaje_out": round(tiempo + fin - inicio, 3),
                "master_in": inicio,
                "master_out": fin,
                "texto": corte["texto"],
            }
        )
        tiempo += fin - inicio
        bloque_anterior = bloque
    piezas.append(("silencio", cola))
    return piezas, edl, round(tiempo + cola, 3)


def _bordes(texto: str) -> tuple[str, str]:
    tokens = [normalizar(x) for x in re.findall(r"[\wÀ-ÿ']+", texto) if normalizar(x)]
    return (tokens[0], tokens[-1]) if tokens else ("", "")


def verificar_bordes(edl: list[dict[str, Any]], palabras: list[dict[str, Any]]) -> dict[str, Any]:
    resultados = []
    for corte in edl:
        dentro = [
            p for p in palabras
            if float(p.get("fin", p.get("f", 0))) > corte["montaje_in"]
            and float(p.get("inicio", p.get("t", 0))) < corte["montaje_out"]
        ]
        esperado = _bordes(corte["texto"])
        observado = _bordes(" ".join(str(p.get("texto", p.get("w", ""))) for p in dentro))
        pasa = bool(dentro) and esperado == observado
        resultados.append(
            {
                "id": corte["id"],
                "esperado": {"primera": esperado[0], "ultima": esperado[1]},
                "observado": {"primera": observado[0], "ultima": observado[1]},
                "pasa": pasa,
            }
        )
    return {"pasa": all(r["pasa"] for r in resultados), "cortes": resultados}


def renderizar(master: Path, piezas: list[tuple[Any, ...]], salida: Path, ffmpeg: str) -> None:
    cadenas = []
    etiquetas = []
    for indice, pieza in enumerate(piezas):
        etiqueta = f"p{indice}"
        if pieza[0] == "clip":
            _, inicio, fin = pieza
            duracion = fin - inicio
            fundido = min(0.02, duracion / 4)
            cadenas.append(
                f"[0:a]atrim=start={inicio}:end={fin},asetpts=PTS-STARTPTS,"
                f"afade=t=in:d={fundido},afade=t=out:st={max(0, duracion - fundido):.3f}:d={fundido}[{etiqueta}]"
            )
        else:
            cadenas.append(f"anullsrc=r=48000:cl=mono,atrim=duration={pieza[1]}[{etiqueta}]")
        etiquetas.append(f"[{etiqueta}]")
    cadenas.append(
        "".join(etiquetas)
        + f"concat=n={len(etiquetas)}:v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]"
    )
    subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-i", str(master), "-filter_complex", ";".join(cadenas),
         "-map", "[out]", "-ac", "1", "-ar", "48000", str(salida)],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path)
    parser.add_argument("cortes", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--verificar", action="store_true")
    parser.add_argument("--transcripcion-verificacion", type=Path)
    parser.add_argument("--solo-plan", action="store_true")
    args = parser.parse_args()

    try:
        cortes = cargar_json(args.cortes)
        piezas, edl, duracion = construir_plan(cortes)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    args.salida.mkdir(parents=True, exist_ok=True)
    escribir_json(args.salida / "edl.json", edl)
    escribir_json(args.salida / "plan_montaje.json", {"duracion": duracion, "piezas": piezas})
    if args.solo_plan:
        print(f"PLAN: {len(edl)} cortes, {duracion:.2f}s")
        return 0
    if not args.master.is_file():
        parser.error(f"No existe el máster: {args.master}")
    if shutil.which(args.ffmpeg) is None:
        parser.error(f"No se encontró la herramienta: {args.ffmpeg}")
    candidato = args.salida / "candidato_montaje.wav"
    try:
        renderizar(args.master, piezas, candidato, args.ffmpeg)
        transcript_path = args.transcripcion_verificacion
        if args.verificar and transcript_path is None:
            carpeta = args.salida / "retranscripcion"
            subprocess.run(
                [sys.executable, str(Path(__file__).with_name("transcribir.py")), str(candidato), str(carpeta)],
                check=True,
            )
            transcript_path = carpeta / "palabras.json"
        if transcript_path:
            verificacion = verificar_bordes(edl, palabras_de(cargar_json(transcript_path)))
        else:
            verificacion = {"pasa": False, "motivo": "PENDIENTE_RETRANSCRIPCION", "cortes": []}
        escribir_json(args.salida / "verificacion_montaje.json", verificacion)
        if verificacion["pasa"]:
            shutil.copy2(candidato, args.salida / "ENTREGA_montaje.wav")
            print(f"PASA: {len(edl)} cortes, {duracion:.2f}s")
            return 0
        print("NO PASA: el candidato no es entrega; revisa verificacion_montaje.json")
        return 3 if transcript_path else 0
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

