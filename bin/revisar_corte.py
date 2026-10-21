#!/usr/bin/env python3
"""Genera una primera revisión mecánica por timecode de un corte descrito en JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ta_core import cargar_json, escribir_texto_atomico, segundos, timecode


def analizar_corte(datos: Any, canon_disponible: bool) -> dict[str, Any]:
    clips = datos.get("clips", []) if isinstance(datos, dict) else datos
    if not isinstance(clips, list):
        raise ValueError("El corte debe ser una lista o un objeto con clips")
    notas: list[dict[str, Any]] = []
    aperturas: dict[str, float] = {}
    pagos: set[str] = set()
    fin_anterior = 0.0
    textos_vistos: dict[str, float] = {}
    for indice, clip in enumerate(clips, 1):
        inicio = segundos(clip.get("in", clip.get("inicio", 0)))
        fin = segundos(clip.get("out", clip.get("fin", inicio)))
        tc = timecode(inicio)
        if fin <= inicio:
            notas.append({"tc": tc, "tipo": "ERROR", "detalle": f"clip {indice} sin duración positiva"})
            continue
        if inicio < fin_anterior:
            notas.append({"tc": tc, "tipo": "ERROR", "detalle": "solape o retroceso en la línea de tiempo"})
        if inicio - fin_anterior > 1.5 and indice > 1:
            notas.append(
                {"tc": timecode(fin_anterior), "tipo": "REVISAR", "detalle": f"silencio de {inicio - fin_anterior:.2f}s; confirmar que tiene intención"}
            )
        if fin - inicio < 0.35:
            notas.append({"tc": tc, "tipo": "REVISAR", "detalle": "corte menor a 0.35s; comprobar respiración y comprensión"})
        texto = " ".join(str(clip.get("texto", "")).lower().split())
        if texto and texto in textos_vistos:
            notas.append({"tc": tc, "tipo": "SOBRA", "detalle": f"repite contenido ya oído en {timecode(textos_vistos[texto])}"})
        if texto:
            textos_vistos[texto] = inicio
        if clip.get("abre_bucle"):
            aperturas[str(clip["abre_bucle"])] = inicio
        if clip.get("paga_bucle"):
            pagos.add(str(clip["paga_bucle"]))
        fin_anterior = max(fin_anterior, fin)
    for identificador, inicio in aperturas.items():
        if identificador not in pagos:
            notas.append({"tc": timecode(inicio), "tipo": "ROMPE", "detalle": f"bucle `{identificador}` no obtiene pago"})
    if not canon_disponible:
        notas.append(
            {
                "tc": "00:00:00.000",
                "tipo": "LIMITE",
                "detalle": "modo genérico: el canon privado no fue comprobado",
            }
        )
    notas.sort(key=lambda n: n["tc"])
    return {"canon_comprobado": canon_disponible, "clips": len(clips), "notas": notas}


def reporte_markdown(resultado: dict[str, Any]) -> str:
    modo = "canon local disponible" if resultado["canon_comprobado"] else "modo genérico"
    lineas = ["# Revisión de corte", "", f"{resultado['clips']} clips · {modo}", "", "## Notas", ""]
    if resultado["notas"]:
        lineas += [f"- `{nota['tc']}` · **{nota['tipo']}** · {nota['detalle']}" for nota in resultado["notas"]]
    else:
        lineas.append("- Sin incidencias mecánicas. Falta el visionado editorial completo.")
    lineas += [
        "",
        "## Siguiente lectura",
        "",
        "Ver el corte completo y añadir evidencia visual o sonora a cada nota. Este reporte no aprueba el canon ni sustituye el juicio editorial.",
    ]
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corte", type=Path)
    parser.add_argument("reporte", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config.local.yaml"))
    args = parser.parse_args()
    try:
        config = cargar_json(args.config) if args.config.exists() else {"rutas": {}}
        canon = str(config.get("rutas", {}).get("canon_privado", "")).strip()
        canon_disponible = bool(canon and Path(canon).expanduser().is_file())
        if canon_disponible:
            Path(canon).expanduser().read_text(encoding="utf-8")
        resultado = analizar_corte(cargar_json(args.corte), canon_disponible)
        escribir_texto_atomico(args.reporte, reporte_markdown(resultado))
        args.reporte.with_suffix(".json").write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (ValueError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"HECHO: {len(resultado['notas'])} notas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

