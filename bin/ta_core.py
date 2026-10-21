#!/usr/bin/env python3
"""Utilidades compartidas, sin dependencias externas."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


def cargar_json(path: str | Path) -> Any:
    """Carga JSON. Los YAML del repo usan el subconjunto JSON válido de YAML."""
    ruta = Path(path).expanduser()
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"No existe el archivo: {ruta}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON/YAML inválido en {ruta}: línea {exc.lineno}") from exc


def escribir_texto_atomico(path: str | Path, texto: str) -> None:
    ruta = Path(path)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=ruta.parent, delete=False) as tmp:
        tmp.write(texto)
        temporal = Path(tmp.name)
    os.replace(temporal, ruta)


def escribir_json(path: str | Path, valor: Any) -> None:
    escribir_texto_atomico(path, json.dumps(valor, ensure_ascii=False, indent=2) + "\n")


def normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.lower())
    sin_acentos = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", sin_acentos)


def segundos(valor: str | int | float) -> float:
    if isinstance(valor, (int, float)):
        return float(valor)
    partes = valor.strip().replace(",", ".").split(":")
    if len(partes) == 1:
        return float(partes[0])
    if len(partes) == 2:
        minutos, seg = partes
        return int(minutos) * 60 + float(seg)
    if len(partes) == 3:
        horas, minutos, seg = partes
        return int(horas) * 3600 + int(minutos) * 60 + float(seg)
    raise ValueError(f"Timecode inválido: {valor}")


def timecode(valor: float) -> str:
    valor = max(0.0, float(valor))
    horas = int(valor // 3600)
    minutos = int(valor % 3600 // 60)
    seg = valor % 60
    return f"{horas:02d}:{minutos:02d}:{seg:06.3f}"


def ejecutar(args: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def archivos_visibles(repo: Path = ROOT) -> list[Path]:
    proceso = ejecutar(
        ["git", "-C", str(repo), "ls-files", "-co", "--exclude-standard"],
        check=False,
    )
    if proceso.returncode != 0:
        raise RuntimeError(proceso.stderr.strip() or "git ls-files falló")
    return [repo / linea for linea in proceso.stdout.splitlines() if linea]


def palabras_de(valor: Any) -> list[dict[str, Any]]:
    if isinstance(valor, dict):
        valor = valor.get("palabras", [])
    if not isinstance(valor, list):
        raise ValueError("Se esperaba una lista de palabras")
    return valor


def primera_clave(dic: dict[str, Any], claves: Iterable[str], default: Any = None) -> Any:
    for clave in claves:
        if clave in dic:
            return dic[clave]
    return default

