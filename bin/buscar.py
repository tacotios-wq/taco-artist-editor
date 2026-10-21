#!/usr/bin/env python3
"""Resuelve frases de inicio y fin contra tiempos por palabra."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ta_core import cargar_json, escribir_json, normalizar, palabras_de, primera_clave, segundos


def _texto(palabra: dict[str, Any]) -> str:
    return str(primera_clave(palabra, ("texto", "w", "t"), ""))


def _inicio(palabra: dict[str, Any]) -> float:
    return float(primera_clave(palabra, ("inicio", "t", "ini"), 0.0))


def _fin(palabra: dict[str, Any]) -> float:
    return float(primera_clave(palabra, ("fin", "f"), _inicio(palabra)))


def encontrar(tokens: list[str], frase: str, desde: int = 0) -> tuple[int, int] | None:
    objetivo = [normalizar(x) for x in frase.split() if normalizar(x)]
    if not objetivo:
        return None
    for indice in range(desde, len(tokens) - len(objetivo) + 1):
        if tokens[indice: indice + len(objetivo)] == objetivo:
            return indice, indice + len(objetivo) - 1
    return None


def resolver(palabras: list[dict[str, Any]], selecciones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tokens = [normalizar(_texto(p)) for p in palabras]
    cortes = []
    for seleccion in selecciones:
        limite_inicio = segundos(seleccion.get("ventana_inicio", 0))
        limite_fin = segundos(seleccion.get("ventana_fin", float("inf")))
        indices = [i for i, p in enumerate(palabras) if _inicio(p) >= limite_inicio and _fin(p) <= limite_fin]
        base = indices[0] if indices else 0
        tope = indices[-1] + 1 if indices else len(palabras)
        a = encontrar(tokens[:tope], seleccion["desde"], base)
        b = encontrar(tokens[:tope], seleccion["hasta"], a[0] if a else base)
        if not a or not b or b[1] < a[0]:
            raise ValueError(f"No se encontró el borde de {seleccion.get('id', '?')}")
        tramo = palabras[a[0]: b[1] + 1]
        cortes.append(
            {
                "id": seleccion.get("id", f"c{len(cortes) + 1:03d}"),
                "bloque": seleccion.get("bloque", "sin-bloque"),
                "master_in": round(_inicio(tramo[0]), 3),
                "master_out": round(_fin(tramo[-1]), 3),
                "texto": " ".join(_texto(p) for p in tramo).strip(),
            }
        )
    return cortes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("palabras", type=Path)
    parser.add_argument("selecciones", type=Path)
    parser.add_argument("salida", type=Path)
    args = parser.parse_args()
    try:
        cortes = resolver(palabras_de(cargar_json(args.palabras)), cargar_json(args.selecciones))
        escribir_json(args.salida, cortes)
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"HECHO: {len(cortes)} cortes resueltos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

