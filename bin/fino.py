#!/usr/bin/env python3
"""Recorta un transcript por ventanas conservando idioma y tiempos por palabra."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ta_core import cargar_json, escribir_json, palabras_de, segundos


def refinar(palabras: list[dict[str, Any]], ventanas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    salida = []
    for ventana in ventanas:
        inicio = segundos(ventana["inicio"])
        fin = segundos(ventana["fin"])
        if fin <= inicio:
            raise ValueError(f"Ventana {ventana.get('id', '?')} sin duración positiva")
        elegidas = [
            p for p in palabras
            if float(p.get("fin", p.get("f", 0))) > inicio
            and float(p.get("inicio", p.get("t", 0))) < fin
        ]
        salida.append(
            {
                "id": ventana.get("id", f"v{len(salida) + 1:03d}"),
                "inicio": inicio,
                "fin": fin,
                "palabras": elegidas,
            }
        )
    return salida


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("palabras", type=Path)
    parser.add_argument("ventanas", type=Path)
    parser.add_argument("salida", type=Path)
    args = parser.parse_args()
    try:
        resultado = refinar(palabras_de(cargar_json(args.palabras)), cargar_json(args.ventanas))
        escribir_json(args.salida, resultado)
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"HECHO: {len(resultado)} ventanas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

