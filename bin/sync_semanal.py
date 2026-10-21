#!/usr/bin/env python3
"""Sincronización local allowlist; el modo seco no escribe ni modifica git."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ta_core import ROOT, cargar_json, escribir_json, escribir_texto_atomico


ALLOWLIST = ROOT / "sync" / "ALLOWLIST.yaml"
STATE = ROOT / "sync" / "STATE.json"
COLA = ROOT / "referencias" / "cola.txt"


def validar_allowlist(datos: dict[str, Any]) -> list[dict[str, Any]]:
    if datos.get("politica") != "ALLOWLIST":
        raise ValueError("La política debe ser ALLOWLIST")
    fuentes = datos.get("fuentes")
    if not isinstance(fuentes, list) or not fuentes:
        raise ValueError("La allowlist no contiene fuentes")
    ids = set()
    requeridas = {"id", "origen", "destino", "forma", "motivo"}
    for fuente in fuentes:
        faltan = requeridas - set(fuente)
        if faltan:
            raise ValueError(f"Fuente incompleta: faltan {', '.join(sorted(faltan))}")
        if fuente["id"] in ids:
            raise ValueError(f"ID duplicado: {fuente['id']}")
        ids.add(fuente["id"])
        if fuente["forma"] not in {"CODIGO", "DESTILADO", "FUERA"}:
            raise ValueError(f"Forma inválida en {fuente['id']}")
        origen = str(fuente["origen"])
        if origen.startswith("/") or ".." in Path(origen).parts:
            raise ValueError(f"Origen no permitido en {fuente['id']}")
    return fuentes


def expandir_llaves(patron: str) -> list[str]:
    coincidencia = re.search(r"\{([^{}]+)\}", patron)
    if not coincidencia:
        return [patron]
    salidas = []
    for opcion in coincidencia.group(1).split(","):
        nuevo = patron[: coincidencia.start()] + opcion + patron[coincidencia.end():]
        salidas.extend(expandir_llaves(nuevo))
    return salidas


def rutas_fuente(origen: str) -> list[Path]:
    rutas: set[Path] = set()
    for patron in expandir_llaves(origen):
        expandido = os.path.expanduser(patron)
        for nombre in glob.glob(expandido):
            rutas.add(Path(nombre))
    return sorted(rutas, key=lambda p: str(p))


def _archivos(rutas: Iterable[Path]) -> Iterable[Path]:
    for ruta in rutas:
        if ruta.is_file():
            yield ruta
        elif ruta.is_dir():
            for archivo in sorted((p for p in ruta.rglob("*") if p.is_file()), key=lambda p: str(p)):
                yield archivo


def huella_fuente(fuente: dict[str, Any]) -> str:
    resumen = hashlib.sha256()
    rutas = rutas_fuente(str(fuente["origen"]))
    if not rutas:
        return "AUSENTE"
    for archivo in _archivos(rutas):
        try:
            estado = archivo.stat()
        except OSError:
            continue
        resumen.update(str(archivo.name).encode("utf-8", errors="replace"))
        resumen.update(str(estado.st_size).encode())
        resumen.update(str(estado.st_mtime_ns).encode())
    return resumen.hexdigest()


def leer_cola(path: Path = COLA) -> list[str]:
    if not path.exists():
        return []
    urls = []
    for linea in path.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if limpia and not limpia.startswith("#"):
            if not limpia.startswith(("https://", "http://")):
                raise ValueError(f"Entrada de cola inválida: {limpia}")
            urls.append(limpia)
    return urls


def estado_actual(fuentes: list[dict[str, Any]]) -> dict[str, str]:
    return {
        fuente["id"]: huella_fuente(fuente)
        for fuente in fuentes
        if fuente["forma"] != "FUERA" and fuente.get("actualizacion") != "LECTURA_EN_EJECUCION"
    }


def plan_seco(repo: Path = ROOT) -> dict[str, Any]:
    fuentes = validar_allowlist(cargar_json(repo / "sync" / "ALLOWLIST.yaml"))
    nuevo = estado_actual(fuentes)
    previo = cargar_json(repo / "sync" / "STATE.json").get("fuentes", {}) if (repo / "sync" / "STATE.json").exists() else {}
    cambiadas = sorted(clave for clave, valor in nuevo.items() if previo.get(clave) != valor)
    ausentes = sorted(clave for clave, valor in nuevo.items() if valor == "AUSENTE")
    referencias = leer_cola(repo / "referencias" / "cola.txt")
    return {
        "version": 1,
        "modo": "seco",
        "escrituras": False,
        "git_modificado": False,
        "fuentes_cambiadas": cambiadas,
        "fuentes_ausentes": ausentes,
        "referencias_pendientes": len(referencias),
        "hay_trabajo": bool(cambiadas or referencias),
    }


def regenerar_indice(repo: Path = ROOT) -> bool:
    fichas = sorted((repo / "conocimiento" / "referentes").glob("*.md"))
    filas = []
    fechas = []
    for ficha in fichas:
        texto = ficha.read_text(encoding="utf-8")
        titulo = next((l[2:].strip() for l in texto.splitlines() if l.startswith("# ")), ficha.stem)
        ejes = next((l.split(":", 1)[1].strip() for l in texto.splitlines() if l.startswith("Ejes:")), "sin clasificar")
        fechas += re.findall(r"Fecha:\s*(\d{4}-\d{2}-\d{2})", texto[:300])
        filas.append((titulo, ficha.name, ejes))
    fecha_fuente = max(fechas) if fechas else date.today().isoformat()
    lineas = [
        f"Fuente: fichas públicas de conocimiento/referentes · Fecha: {fecha_fuente}",
        "",
        "# Índice de referentes",
        "",
        "| Referente | Ejes |",
        "|---|---|",
    ]
    lineas += [f"| [{titulo}](referentes/{nombre}) | {ejes} |" for titulo, nombre, ejes in filas]
    lineas += ["", "Las transcripciones completas permanecen en `.cache/` y no se versionan.", ""]
    destino = repo / "conocimiento" / "INDICE.md"
    nuevo = "\n".join(lineas)
    anterior = destino.read_text(encoding="utf-8") if destino.exists() else ""
    if nuevo != anterior:
        escribir_texto_atomico(destino, nuevo)
        return True
    return False


def procesar_referencias(urls: list[str], repo: Path = ROOT) -> list[str]:
    if not urls:
        return []
    creadas: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ta-referencias-") as temporal:
        temp = Path(temporal)
        for url in urls:
            clave = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
            nombre = f"referencia-{clave}.md"
            destino_temp = temp / nombre
            subprocess.run(
                [sys.executable, str(repo / "bin" / "referente.py"), "--url-remota", url, "--url", url,
                 "--salida", str(destino_temp), "--cache", str(repo / ".cache" / "referencias")],
                cwd=repo,
                check=True,
            )
            creadas.append(nombre)
        for nombre in creadas:
            shutil.copy2(temp / nombre, repo / "conocimiento" / "referentes" / nombre)
    comentarios = [
        linea for linea in COLA.read_text(encoding="utf-8").splitlines()
        if not linea.strip() or linea.lstrip().startswith("#")
    ]
    escribir_texto_atomico(COLA, "\n".join(comentarios).rstrip() + "\n")
    return creadas


def actualizar_changelog(cambiadas: list[str], referencias: list[str], repo: Path = ROOT) -> bool:
    if not cambiadas and not referencias:
        return False
    path = repo / "CHANGELOG.md"
    texto = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n"
    hoy = date.today().isoformat()
    marcador = f"## {hoy} · sincronización"
    bloque = [marcador, ""]
    if cambiadas:
        bloque.append("- Fuentes detectadas con cambios: " + ", ".join(f"`{x}`" for x in cambiadas) + ".")
    if referencias:
        bloque.append(f"- Fichas públicas incorporadas desde la cola: {len(referencias)}.")
    bloque.append("")
    nuevo_bloque = "\n".join(bloque)
    if marcador in texto:
        inicio = texto.index(marcador)
        siguiente = texto.find("\n## ", inicio + len(marcador))
        fin = siguiente if siguiente >= 0 else len(texto)
        nuevo = texto[:inicio] + nuevo_bloque + texto[fin:].lstrip("\n")
    else:
        encabezado = "# Changelog\n\n"
        cuerpo = texto[len(encabezado):] if texto.startswith(encabezado) else texto
        nuevo = encabezado + nuevo_bloque + cuerpo
    if nuevo != texto:
        escribir_texto_atomico(path, nuevo)
        return True
    return False


def estado_git(repo: Path = ROOT) -> str:
    proceso = subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=True)
    return proceso.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seco", action="store_true")
    parser.add_argument("--rama", action="store_true")
    parser.add_argument("--pr", action="store_true")
    parser.add_argument("--config", type=Path, default=ROOT / "config.local.yaml")
    args = parser.parse_args()
    if args.pr and not args.rama:
        parser.error("--pr requiere --rama")
    try:
        plan = plan_seco(ROOT)
        if args.seco:
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
            return 0
        if args.rama and estado_git(ROOT):
            raise RuntimeError("El árbol debe estar limpio antes de crear una rama semanal")
        if not plan["hay_trabajo"]:
            print("SIN_CAMBIOS: no se escribe ni se crea rama")
            return 0
        fuentes = validar_allowlist(cargar_json(ALLOWLIST))
        urls = leer_cola(COLA)
        creadas = procesar_referencias(urls, ROOT)
        regenerar_indice(ROOT)
        actuales = estado_actual(fuentes)
        escribir_json(STATE, {"version": 1, "fuentes": actuales})
        actualizar_changelog(plan["fuentes_cambiadas"], creadas, ROOT)
        verificacion = subprocess.run(
            [sys.executable, str(ROOT / "bin" / "verificar.py"), "--no-sync", "--config", str(args.config)],
            cwd=ROOT,
            check=False,
        )
        if verificacion.returncode != 0:
            raise RuntimeError("La verificación falló; no se crea rama")
        cambios = estado_git(ROOT)
        if not cambios:
            print("SIN_CAMBIOS: verificación completa; no se crea rama")
            return 0
        if args.rama:
            rama = f"semanal/{date.today().isoformat()}"
            existe = subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{rama}"], cwd=ROOT, check=False
            ).returncode == 0
            if existe:
                raise RuntimeError(f"La rama {rama} ya existe; no se sobrescribe")
            subprocess.run(["git", "switch", "-c", rama], cwd=ROOT, check=True)
            subprocess.run(["git", "add", "--all"], cwd=ROOT, check=True)
            subprocess.run(["git", "commit", "-m", f"sync semanal {date.today().isoformat()}"], cwd=ROOT, check=True)
            if args.pr:
                subprocess.run(
                    ["gh", "pr", "create", "--fill", "--title", f"Sync semanal {date.today().isoformat()}"],
                    cwd=ROOT,
                    check=True,
                )
            print(f"RAMA_LOCAL: {rama}")
        else:
            print("CAMBIOS_PREPARADOS: revisa el árbol; no se creó rama")
        return 0
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

