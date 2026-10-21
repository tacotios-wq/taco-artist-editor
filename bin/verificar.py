#!/usr/bin/env python3
"""Verifica el repositorio público y escribe VERIFICACION.md con evidencia real."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_semanal import validar_allowlist
from ta_core import ROOT, archivos_visibles, cargar_json, escribir_texto_atomico


SKILLS = {"ta-transcribir", "ta-escaleta", "ta-subtitular", "ta-revisar-corte", "ta-referente"}
TEXTO = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".plist", ".csv", ".html"}
MULTIMEDIA = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".mp4", ".mov", ".mkv", ".webm", ".avi", ".jpg", ".jpeg", ".png", ".gif", ".webp"}
RUTA_PERSONAL = "/" + "Users" + r"/[^/\s]+"


@dataclass
class Resultado:
    nombre: str
    comando: str
    pasa: bool
    resumen: str


def _visible_relativo() -> list[Path]:
    return [p.relative_to(ROOT) for p in archivos_visibles(ROOT)]


def _frontmatter(texto: str) -> dict[str, str]:
    if not texto.startswith("---\n"):
        return {}
    cierre = texto.find("\n---\n", 4)
    if cierre < 0:
        return {}
    datos = {}
    for linea in texto[4:cierre].splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            datos[clave.strip()] = valor.strip().strip('"\'')
    return datos


def comprobar_estructura() -> Resultado:
    errores = []
    try:
        plugin = cargar_json(ROOT / ".claude-plugin" / "plugin.json")
        market = cargar_json(ROOT / ".claude-plugin" / "marketplace.json")
        if plugin.get("name") != "taco-artist-editor" or not plugin.get("version"):
            errores.append("manifest de plugin incompleto")
        plugins = market.get("plugins", [])
        if market.get("name") != "taco-artist-editor" or len(plugins) != 1 or plugins[0].get("source") != "./":
            errores.append("manifest de marketplace incompleto")
    except ValueError as exc:
        errores.append(str(exc))
    carpetas = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()} if (ROOT / "skills").is_dir() else set()
    if carpetas != SKILLS:
        errores.append(f"skills esperadas {len(SKILLS)}, encontradas {len(carpetas)}")
    for nombre in sorted(SKILLS):
        ruta = ROOT / "skills" / nombre / "SKILL.md"
        if not ruta.is_file():
            errores.append(f"falta {nombre}/SKILL.md")
            continue
        texto = ruta.read_text(encoding="utf-8")
        fm = _frontmatter(texto)
        if fm.get("name") != nombre or not fm.get("description"):
            errores.append(f"frontmatter inválido en {nombre}")
        for seccion in ("## Lee primero", "## Corre", "## Entrega", "## No hace"):
            if seccion not in texto:
                errores.append(f"{nombre} no declara {seccion[3:]}")
    return Resultado("estructura_plugin", "$ validar manifests y cinco skills", not errores, "; ".join(errores) or "2 manifests JSON válidos y 5 skills completas")


def comprobar_allowlist() -> Resultado:
    try:
        fuentes = validar_allowlist(cargar_json(ROOT / "sync" / "ALLOWLIST.yaml"))
        return Resultado("allowlist", "$ validar sync/ALLOWLIST.yaml", True, f"{len(fuentes)} fuentes declaradas con forma, destino y motivo")
    except (ValueError, OSError) as exc:
        return Resultado("allowlist", "$ validar sync/ALLOWLIST.yaml", False, str(exc))


def comprobar_conocimiento() -> Resultado:
    errores = []
    archivos = sorted((ROOT / "conocimiento").rglob("*.md"))
    patron = re.compile(r"^Fuente: .+ · Fecha: \d{4}-\d{2}-\d{2}$")
    if not archivos:
        errores.append("no hay archivos de conocimiento")
    for archivo in archivos:
        primera = archivo.read_text(encoding="utf-8").splitlines()[0] if archivo.stat().st_size else ""
        if not patron.match(primera):
            errores.append(f"cabecera inválida en {archivo.relative_to(ROOT)}")
    fichas = list((ROOT / "conocimiento" / "referentes").glob("*.md"))
    if len(fichas) < 3:
        errores.append("se requieren al menos tres fichas de referentes")
    return Resultado("conocimiento", "$ comprobar cabeceras y fichas", not errores, "; ".join(errores) or f"{len(archivos)} archivos con cabecera; {len(fichas)} fichas")


def comprobar_archivos_publicos() -> Resultado:
    errores = []
    visibles = _visible_relativo()
    for relativa in visibles:
        ruta = ROOT / relativa
        if ruta.suffix.lower() in MULTIMEDIA:
            errores.append(f"multimedia: {relativa}")
        if ruta.is_file() and ruta.stat().st_size > 2 * 1024 * 1024:
            errores.append(f"supera 2 MB: {relativa}")
        if ruta.is_file() and ruta.suffix.lower() in TEXTO:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            if re.search(RUTA_PERSONAL, texto):
                errores.append(f"ruta personal absoluta: {relativa}")
    return Resultado("archivos_publicos", "$ revisar tamaño, extensiones y rutas", not errores, "; ".join(errores) or f"{len(visibles)} archivos visibles; sin multimedia ni archivos mayores de 2 MB")


def ejecutar_control(nombre: str, comando: str, args: list[str], resumen: Callable[[str], str] | None = None) -> Resultado:
    proceso = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    salida = (proceso.stdout + "\n" + proceso.stderr).strip()
    detalle = resumen(salida) if resumen else ("; ".join(salida.splitlines()[-3:]) or f"exit {proceso.returncode}")
    detalle = re.sub(RUTA_PERSONAL, "~", detalle)
    return Resultado(nombre, comando, proceso.returncode == 0, detalle)


def comprobar_tests() -> Resultado:
    return ejecutar_control(
        "tests",
        "$ python3 -m unittest discover -s tests",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        lambda s: "; ".join([l.strip() for l in s.splitlines() if l.strip()][-3:]),
    )


def comprobar_sync() -> Resultado:
    antes = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    a = subprocess.run([sys.executable, "bin/sync_semanal.py", "--seco"], cwd=ROOT, text=True, capture_output=True, check=False)
    b = subprocess.run([sys.executable, "bin/sync_semanal.py", "--seco"], cwd=ROOT, text=True, capture_output=True, check=False)
    despues = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    pasa = a.returncode == 0 and b.returncode == 0 and a.stdout == b.stdout and antes == despues
    if pasa:
        plan = json.loads(a.stdout)
        detalle = f"dos salidas idénticas; escrituras={plan['escrituras']}; git_modificado={plan['git_modificado']}"
    else:
        detalle = "el modo seco cambió el árbol, falló o produjo salidas distintas"
    return Resultado("sync_seco", "$ python3 bin/sync_semanal.py --seco (dos veces)", pasa, detalle)


def _resumen_fugas(salida: str) -> str:
    lineas = [l.strip() for l in salida.splitlines() if "FUGAS DURAS" in l]
    return "; ".join(lineas) if lineas else "detector ejecutado sin resumen reconocible"


def controles_externos(config: dict) -> list[Resultado]:
    rutas = config.get("rutas", {})
    resultados = []
    for clave, nombre, etiqueta in (
        ("detector_fugas", "detector_fugas", "$ detector de fugas <repo>"),
        ("detector_externo", "detector_externo", "$ detector de audiencia externa <repo>"),
    ):
        valor = str(rutas.get(clave, "")).strip()
        if not valor or not Path(valor).expanduser().is_file():
            resultados.append(Resultado(nombre, etiqueta, False, "ruta externa ausente; verificación cerrada"))
            continue
        resultados.append(
            ejecutar_control(nombre, etiqueta, [sys.executable, str(Path(valor).expanduser()), str(ROOT)], _resumen_fugas)
        )
    return resultados


def comprobar_filtro(config: dict) -> Resultado:
    valor = str(config.get("rutas", {}).get("filtro_publico", "")).strip()
    if not valor or not Path(valor).expanduser().is_file():
        return Resultado("filtro_publico", "$ filtro público", False, "ruta externa ausente; verificación cerrada")
    terminos = [l.strip() for l in Path(valor).expanduser().read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]
    hallazgos = []
    for relativa in _visible_relativo():
        ruta = ROOT / relativa
        if not ruta.is_file() or ruta.suffix.lower() not in TEXTO:
            continue
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        for termino in terminos:
            if re.search(rf"(?<!\w){re.escape(termino)}(?!\w)", texto, re.IGNORECASE):
                hallazgos.append(str(relativa))
                break
    unicos = sorted(set(hallazgos))
    return Resultado(
        "filtro_publico",
        "$ filtro público",
        not unicos,
        "0 términos encontrados" if not unicos else f"términos encontrados en {len(unicos)} archivos: {', '.join(unicos)}",
    )


def escribir_reporte(resultados: Iterable[Resultado]) -> None:
    resultados = list(resultados)
    pasa = all(r.pasa for r in resultados)
    ahora = datetime.now().astimezone()
    lineas = [
        f"Fuente: bin/verificar.py · Fecha: {ahora.date().isoformat()}",
        "",
        "# Verificación",
        "",
        f"**{'PASA' if pasa else 'NO PASA'}** · ejecución {ahora.isoformat(timespec='seconds')}",
        "",
        "| Control | Resultado | Evidencia |",
        "|---|---|---|",
    ]
    for resultado in resultados:
        evidencia = resultado.resumen.replace("|", "\\|").replace("\n", " ")
        lineas.append(f"| `{resultado.nombre}` | {'PASA' if resultado.pasa else 'NO PASA'} | {evidencia} |")
    lineas += ["", "## Comandos ejecutados", ""]
    lineas += [f"- `{r.comando.removeprefix('$ ')}`" for r in resultados]
    lineas += [
        "",
        "## Resultado",
        "",
        "La salida se generó desde los procesos reales. Las rutas de los detectores permanecen en la configuración local ignorada.",
    ]
    escribir_texto_atomico(ROOT / "VERIFICACION.md", "\n".join(lineas) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.local.yaml")
    parser.add_argument("--no-sync", action="store_true", help="evita recursión cuando lo llama el sincronizador")
    args = parser.parse_args()
    try:
        config = cargar_json(args.config) if args.config.exists() else {"rutas": {}}
        base = [
            comprobar_estructura(),
            comprobar_allowlist(),
            comprobar_conocimiento(),
            comprobar_archivos_publicos(),
            comprobar_tests(),
        ]
        if not args.no_sync:
            base.append(comprobar_sync())
        else:
            base.append(Resultado("sync_seco", "$ sync seco omitido por llamada interna", True, "evitado para no crear recursión"))
        escribir_reporte(base)
        externos = controles_externos(config)
        filtro = comprobar_filtro(config)
        completos = base + externos + [filtro]
        escribir_reporte(completos)
        finales = base + controles_externos(config) + [comprobar_filtro(config)]
        escribir_reporte(finales)
        pasa = all(r.pasa for r in finales)
        print(f"VERIFICACION {'PASA' if pasa else 'NO PASA'}: {sum(r.pasa for r in finales)}/{len(finales)} controles")
        return 0 if pasa else 1
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        escribir_reporte([Resultado("verificador", "$ python3 bin/verificar.py", False, str(exc))])
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
