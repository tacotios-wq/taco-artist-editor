#!/usr/bin/env python3
"""Busca b-roll por ejes en un catálogo JSON; nunca copia ni abre los clips."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ta_core import cargar_json, normalizar


def buscar(catalogo: list[dict[str, Any]], consulta: str, limite: int = 10) -> list[dict[str, Any]]:
    terminos = {normalizar(t) for t in consulta.split() if normalizar(t)}
    candidatos = []
    for item in catalogo:
        texto = " ".join([str(item.get("descripcion", "")), *map(str, item.get("ejes", []))])
        tokens = {normalizar(t) for t in texto.split() if normalizar(t)}
        puntaje = len(terminos & tokens)
        if puntaje:
            candidatos.append((puntaje, str(item.get("id", "")), item))
    candidatos.sort(key=lambda x: (-x[0], x[1]))
    return [dict(item, coincidencias=puntaje) for puntaje, _, item in candidatos[:limite]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalogo", type=Path)
    parser.add_argument("consulta")
    parser.add_argument("--limite", type=int, default=10)
    args = parser.parse_args()
    try:
        resultado = buscar(cargar_json(args.catalogo), args.consulta, max(1, args.limite))
    except (ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

