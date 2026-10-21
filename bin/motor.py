#!/usr/bin/env python3
"""Motor genérico de subtítulos ASS con reveal por palabra y QA bloqueante."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_subtitulos import escribir_reporte, validar_plan
from ta_core import ROOT, cargar_json, escribir_json, escribir_texto_atomico, normalizar, palabras_de


PRESET_DEFECTO = ROOT / "sync" / "preset_subtitulos.json"


def _adaptar_palabra(palabra: dict[str, Any]) -> dict[str, Any]:
    texto = palabra.get("texto", palabra.get("w", ""))
    inicio = palabra.get("inicio", palabra.get("t", palabra.get("ini", 0.0)))
    fin = palabra.get("fin", palabra.get("f", inicio))
    return {"texto": str(texto).strip(), "inicio": float(inicio), "fin": float(fin)}


def agrupar_golpes(palabras: list[dict[str, Any]], preset: dict[str, Any]) -> list[dict[str, Any]]:
    leyes = preset["chunking"]
    ws = [_adaptar_palabra(p) for p in palabras if str(p.get("texto", p.get("w", ""))).strip()]
    grupos: list[list[dict[str, Any]]] = []
    actual: list[dict[str, Any]] = []
    pendientes: list[dict[str, Any]] = []

    def cerrar() -> None:
        nonlocal actual, pendientes
        if not actual:
            return
        pendientes = []
        conectores = set(leyes["no_terminar_en"])
        while len(actual) > 1 and normalizar(actual[-1]["texto"]) in conectores:
            pendientes.insert(0, actual.pop())
        grupos.append(actual)
        actual = pendientes
        pendientes = []

    for palabra in ws:
        if actual and palabra["inicio"] - actual[-1]["fin"] > leyes["pausa_umbral_s"]:
            cerrar()
        actual.append(palabra)
        maximo = leyes["palabras_hook_max"] if not grupos else leyes["palabras_max"]
        if len(actual) >= maximo:
            cerrar()
    cerrar()

    golpes = []
    for indice, grupo in enumerate(grupos):
        mitad = (len(grupo) + 1) // 2
        lineas = [" ".join(w["texto"] for w in grupo[:mitad])]
        if mitad < len(grupo):
            lineas.append(" ".join(w["texto"] for w in grupo[mitad:]))
        siguiente_inicio = grupos[indice + 1][0]["inicio"] if indice + 1 < len(grupos) else float("inf")
        fin_golpe = min(grupo[-1]["fin"] + leyes["hold_s"], siguiente_inicio)
        eventos = []
        for pos, palabra in enumerate(grupo):
            fin = grupo[pos + 1]["inicio"] if pos + 1 < len(grupo) else fin_golpe
            eventos.append(
                {
                    "inicio": round(palabra["inicio"], 3),
                    "fin": round(max(palabra["inicio"] + 0.01, fin), 3),
                    "texto": " ".join(w["texto"] for w in grupo[: pos + 1]),
                }
            )
        golpes.append(
            {
                "id": indice,
                "modo": "hook" if indice == 0 else "estandar",
                "inicio": grupo[0]["inicio"],
                "fin": round(fin_golpe, 3),
                "palabras": grupo,
                "lineas": lineas,
                "eventos": eventos,
            }
        )
    return golpes


def tiempo_ass(segundos: float) -> str:
    centesimas = max(0, round(segundos * 100))
    horas, resto = divmod(centesimas, 360000)
    minutos, resto = divmod(resto, 6000)
    seg, cent = divmod(resto, 100)
    return f"{horas}:{minutos:02d}:{seg:02d}.{cent:02d}"


def escapar_ass(texto: str) -> str:
    return texto.replace("{", "(").replace("}", ")").replace("\n", " ")


def ass_desde_plan(plan: dict[str, Any], preset: dict[str, Any]) -> str:
    frame, estilo = preset["frame"], preset["estilo"]
    cabecera = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {frame['ancho']}
PlayResY: {frame['alto']}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,{estilo['fuente']},{estilo['tamano']},{estilo['color_ass']},{estilo['color_ass']},{estilo['contorno_color_ass']},&H00000000,-1,0,0,0,100,100,-2,0,1,{estilo['contorno']},{estilo['sombra']},{estilo['alineacion']},{estilo['margen_izquierdo']},{estilo['margen_derecho']},{estilo['margen_vertical']},1
Style: Hook,{estilo['fuente']},{estilo['tamano_hook']},{estilo['color_ass']},{estilo['color_ass']},{estilo['contorno_color_ass']},&H00000000,-1,0,0,0,100,100,-2,0,1,{estilo['contorno']},{estilo['sombra']},{estilo['alineacion']},{estilo['margen_izquierdo']},{estilo['margen_derecho']},{estilo['margen_vertical']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = [cabecera]
    for golpe in plan["golpes"]:
        estilo_nombre = "Hook" if golpe["modo"] == "hook" else "Base"
        for evento in golpe["eventos"]:
            palabras = evento["texto"].split()
            if len(palabras) > 3:
                corte = (len(palabras) + 1) // 2
                texto = " ".join(palabras[:corte]) + r"\N" + " ".join(palabras[corte:])
            else:
                texto = evento["texto"]
            lineas.append(
                f"Dialogue: 0,{tiempo_ass(evento['inicio'])},{tiempo_ass(evento['fin'])},{estilo_nombre},,0,0,0,,{escapar_ass(texto)}\n"
            )
    return "".join(lineas)


def renderizar(video: Path, salida: Path, ffmpeg: str) -> Path:
    candidato = salida / "candidato.mp4"
    subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-i", str(video.resolve()), "-vf", "ass=subtitulos.ass",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", candidato.name],
        cwd=salida,
        check=True,
    )
    return candidato


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--palabras", type=Path, required=True)
    parser.add_argument("--preset", type=Path, default=PRESET_DEFECTO)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--revision-visual", action="store_true")
    parser.add_argument("--solo-plan", action="store_true")
    args = parser.parse_args()

    try:
        palabras = palabras_de(cargar_json(args.palabras))
        preset = cargar_json(args.preset)
        plan = {"version": 1, "golpes": agrupar_golpes(palabras, preset)}
    except (ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    args.salida.mkdir(parents=True, exist_ok=True)
    plan_path = args.salida / "plan_subtitulos.json"
    escribir_json(plan_path, plan)
    escribir_texto_atomico(args.salida / "subtitulos.ass", ass_desde_plan(plan, preset))
    if args.solo_plan:
        print(f"PLAN: {len(plan['golpes'])} golpes")
        return 0
    if not args.video.is_file():
        parser.error(f"No existe el video: {args.video}")
    if shutil.which(args.ffmpeg) is None:
        parser.error(f"No se encontró la herramienta: {args.ffmpeg}")
    try:
        candidato = renderizar(args.video, args.salida, args.ffmpeg)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: ffmpeg terminó con código {exc.returncode}", file=sys.stderr)
        return 2
    resultado = validar_plan(plan, palabras, preset, args.revision_visual)
    escribir_reporte(args.salida, resultado)
    if resultado["pasa"]:
        entrega = args.salida / f"ENTREGA_{args.video.stem}.mp4"
        shutil.copy2(candidato, entrega)
        print(f"QA PASA: {entrega.name}")
        return 0
    print("QA NO PASA: candidato conservado; no hay entrega")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
