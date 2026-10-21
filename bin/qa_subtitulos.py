#!/usr/bin/env python3
"""QA bloqueante del plan de subtítulos y confirmación de revisión visual."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ta_core import cargar_json, escribir_json, escribir_texto_atomico, normalizar, palabras_de


def validar_plan(
    plan: dict[str, Any],
    palabras: list[dict[str, Any]],
    preset: dict[str, Any],
    revision_visual: bool,
) -> dict[str, Any]:
    leyes = preset["chunking"]
    fallos: list[dict[str, Any]] = []
    avisos: list[dict[str, Any]] = []
    golpes = plan.get("golpes", [])

    def falla(ley: str, golpe: Any, detalle: str) -> None:
        fallos.append({"ley": ley, "golpe": golpe, "detalle": detalle})

    if not golpes:
        falla("estructura", None, "el plan no contiene golpes")
    elif golpes[0].get("modo") != "hook":
        falla("hook", golpes[0].get("id"), "el primer golpe no está marcado como hook")

    ocupados: list[tuple[float, float]] = []
    for golpe in golpes:
        gid = golpe.get("id")
        ws = golpe.get("palabras", [])
        maximo = leyes["palabras_hook_max"] if golpe.get("modo") == "hook" else leyes["palabras_max"]
        if not ws:
            falla("estructura", gid, "golpe sin palabras")
            continue
        if len(ws) > maximo:
            falla("chunking", gid, f"{len(ws)} palabras supera el máximo {maximo}")
        if len(golpe.get("lineas", [])) > leyes["lineas_max"]:
            falla("chunking", gid, "demasiadas líneas")
        for anterior, siguiente in zip(ws, ws[1:]):
            pausa = float(siguiente["inicio"]) - float(anterior["fin"])
            if pausa > leyes["pausa_umbral_s"]:
                falla("silencio", gid, f"pausa interna de {pausa:.3f}s")
        eventos = golpe.get("eventos", [])
        if len(eventos) != len(ws):
            falla("reveal", gid, "debe haber un estado por palabra")
        prefijo_anterior = ""
        for indice, evento in enumerate(eventos):
            inicio, fin = float(evento["inicio"]), float(evento["fin"])
            if fin <= inicio:
                falla("reveal", gid, f"estado {indice + 1} sin duración positiva")
            if indice < len(ws) and abs(inicio - float(ws[indice]["inicio"])) > 0.05:
                falla("reveal", gid, f"estado {indice + 1} desalineado de la voz")
            texto = evento.get("texto", "")
            if prefijo_anterior and not texto.startswith(prefijo_anterior):
                falla("reveal", gid, f"estado {indice + 1} no conserva el prefijo")
            prefijo_anterior = texto
            ocupados.append((inicio, fin))
        ultima = normalizar(str(ws[-1].get("texto", "")))
        if ultima in set(leyes["no_terminar_en"]):
            avisos.append({"ley": "chunking", "golpe": gid, "detalle": f"termina en conector: {ultima}"})

    ordenados = sorted(ocupados)
    for actual, siguiente in zip(ordenados, ordenados[1:]):
        if actual[1] > siguiente[0] + 0.001:
            falla("tiempo", None, "dos estados se solapan")
            break

    if palabras:
        inicio_total = float(palabras[0].get("inicio", 0.0))
        fin_total = float(palabras[-1].get("fin", inicio_total))
        voz_total = max(0.001, fin_total - inicio_total)
        visible = sum(max(0.0, fin - inicio) for inicio, fin in ordenados)
        densidad = visible / voz_total
        if densidad > float(preset["seguridad"]["densidad_texto_max"]):
            avisos.append({"ley": "densidad", "golpe": None, "detalle": f"densidad visible {densidad:.1%}"})
    else:
        falla("transcripcion", None, "no hay palabras fuente")

    if preset["seguridad"].get("requiere_revision_visual", True) and not revision_visual:
        falla(
            "revision_visual",
            None,
            "falta confirmar el visionado completo: caras, interfaz, cortes y legibilidad",
        )
    return {"pasa": not fallos, "fallos": fallos, "avisos": avisos, "revision_visual": revision_visual}


def escribir_reporte(salida: Path, resultado: dict[str, Any]) -> None:
    estado = "PASA" if resultado["pasa"] else "NO PASA"
    lineas = [
        "# QA de subtítulos",
        "",
        f"**{estado}** · {len(resultado['fallos'])} fallos bloqueantes · {len(resultado['avisos'])} avisos",
        "",
    ]
    if resultado["fallos"]:
        lineas += ["## Fallos bloqueantes", ""]
        lineas += [
            f"- {x['ley']} · golpe {x['golpe'] if x['golpe'] is not None else '-'}: {x['detalle']}"
            for x in resultado["fallos"]
        ]
        lineas.append("")
    if resultado["avisos"]:
        lineas += ["## Avisos", ""]
        lineas += [
            f"- {x['ley']} · golpe {x['golpe'] if x['golpe'] is not None else '-'}: {x['detalle']}"
            for x in resultado["avisos"]
        ]
        lineas.append("")
    lineas += [
        "## Límite declarado",
        "",
        "El QA mecánico valida texto y tiempo. La revisión visual confirmada cubre caras, interfaz y lectura en movimiento; no se infiere desde el transcript.",
    ]
    escribir_json(salida / "qa.json", resultado)
    escribir_texto_atomico(salida / "QA_REPORTE.md", "\n".join(lineas) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("palabras", type=Path)
    parser.add_argument("preset", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--revision-visual", action="store_true")
    args = parser.parse_args()
    try:
        resultado = validar_plan(
            cargar_json(args.plan), palabras_de(cargar_json(args.palabras)), cargar_json(args.preset), args.revision_visual
        )
        args.salida.mkdir(parents=True, exist_ok=True)
        escribir_reporte(args.salida, resultado)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"QA {'PASA' if resultado['pasa'] else 'NO PASA'}")
    return 0 if resultado["pasa"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

