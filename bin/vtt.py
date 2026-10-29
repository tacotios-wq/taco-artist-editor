#!/usr/bin/env python3
"""Escribe y lee WebVTT con marcas de tiempo por palabra.

Portado de packages/openfilm/studio/ui/src/lib/{subtitles,subtitle-cues}.ts
y packages/openfilm/studio/server/transcripts.mjs, commit de5a98b. Licencia MIT.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable


TIMESTAMP = re.compile(r"(?:(\d{2,}):)?([0-5]\d):([0-5]\d)\.(\d{3})$")
TAG_OR_TEXT = re.compile(r"<([^>]*)>|([^<]+)")
CLOSE_PUNCTUATION = re.compile(r"^[,.;:!?%)}\]\u00bb\u201d\u2019，。、；：！？》〉）」』…]")


def milliseconds(stamp: str) -> int:
    match = TIMESTAMP.fullmatch(stamp.strip())
    if not match:
        raise ValueError(f"marca WebVTT inválida: {stamp}")
    hours, minutes, seconds, millis = match.groups()
    return ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)


def timestamp(value: int | float) -> str:
    millis = max(0, round(float(value)))
    hours, rest = divmod(millis, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _pick(word: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in word:
            return word[name]
    return None


def normalize_words(value: Any) -> list[dict[str, Any]]:
    raw = value.get("palabras", value.get("words")) if isinstance(value, dict) else value
    if not isinstance(raw, list):
        raise ValueError("se esperaba una lista o un objeto con palabras")
    words = []
    previous = -1.0
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"palabra {index} no es un objeto")
        text = str(_pick(item, ("texto", "w", "token", "text")) or "").strip()
        start = _pick(item, ("inicio", "t", "start", "startSec"))
        end = _pick(item, ("fin", "f", "end", "endSec"))
        if not text:
            raise ValueError(f"palabra {index} sin texto")
        if start is None or end is None:
            raise ValueError(f"palabra {index} sin tiempo de inicio o fin")
        start, end = float(start), float(end)
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            raise ValueError(f"palabra {index} tiene tiempo inválido")
        if start < previous:
            raise ValueError("las palabras deben estar en orden temporal")
        words.append({"texto": text, "inicio": start, "fin": end})
        previous = start
    return words


def _append_token(text: str, token: str) -> tuple[str, int]:
    separator = "" if not text or CLOSE_PUNCTUATION.match(token) else " "
    index = len(text) + len(separator)
    return text + separator + token, index


def words_to_cues(
    value: Any,
    *,
    max_chars: int = 42,
    max_duration: float = 6.0,
    max_gap: float = 0.7,
) -> list[dict[str, Any]]:
    """Agrupa palabras sin perder el inicio de ninguna."""

    if max_chars < 1 or max_duration <= 0 or max_gap < 0:
        raise ValueError("los límites de agrupación deben ser positivos")
    words = normalize_words(value)
    cues: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if not current:
            return
        text = ""
        marks = []
        for word in current:
            text, index = _append_token(text, word["texto"])
            marks.append({"index": index, "startMs": round(word["inicio"] * 1000)})
        cues.append(
            {
                "text": text,
                "startMs": round(current[0]["inicio"] * 1000),
                "endMs": round(current[-1]["fin"] * 1000),
                "marks": marks,
            }
        )
        current.clear()

    for word in words:
        candidate = current + [word]
        text = ""
        for one in candidate:
            text, _ = _append_token(text, one["texto"])
        gap = word["inicio"] - current[-1]["fin"] if current else 0
        duration = word["fin"] - current[0]["inicio"] if current else word["fin"] - word["inicio"]
        if current and (gap > max_gap or duration > max_duration or len(text) > max_chars):
            flush()
        current.append(word)
    flush()
    return cues


def vtt_dumps(cues: Iterable[dict[str, Any]], *, speaker: str | None = None) -> str:
    blocks = []
    for index, cue in enumerate(cues, 1):
        text = str(cue.get("text", "")).strip()
        start = int(cue["startMs"])
        end = int(cue["endMs"])
        if not text or start < 0 or end <= start:
            raise ValueError(f"cue {index} inválido")
        marks = sorted(
            (
                {"index": int(mark["index"]), "startMs": int(mark["startMs"])}
                for mark in cue.get("marks", [])
                if 0 < int(mark["index"]) < len(text)
            ),
            key=lambda mark: mark["index"],
        )
        payload = ""
        cursor = 0
        for mark in marks:
            payload += html.escape(text[cursor : mark["index"]], quote=False)
            payload += f"<{timestamp(mark['startMs'])}>"
            cursor = mark["index"]
        payload += html.escape(text[cursor:], quote=False)
        voice = f"<v {html.escape(speaker, quote=False)}>" if speaker else ""
        blocks.append(f"{timestamp(start)} --> {timestamp(end)}\n{voice}{payload}")
    return "WEBVTT\n\n" + "\n\n".join(blocks) + ("\n" if blocks else "")


def _remap_marks(raw: str, clean: str, marks: list[dict[str, int]]) -> list[dict[str, int]]:
    positions = [0] * (len(raw) + 1)
    out = ""
    previous_space = True
    for index, char in enumerate(raw):
        positions[index] = len(out)
        is_space = char.isspace()
        if is_space and previous_space:
            continue
        out += " " if is_space else char
        previous_space = is_space
    positions[len(raw)] = len(out)
    leading = len(out) - len(out.lstrip())
    result = []
    for mark in marks:
        position = max(0, min(len(clean), positions[min(mark["index"], len(raw))] - leading))
        if position < len(clean) and (not result or position > result[-1]["index"]):
            result.append({"index": position, "startMs": mark["startMs"]})
    return result


def vtt_loads(body: str) -> dict[str, Any]:
    """Lee cues, marcas por palabra y la primera voz WebVTT."""

    normalized = body.lstrip("\ufeff").replace("\r", "")
    if not normalized.startswith("WEBVTT"):
        raise ValueError("falta la cabecera WEBVTT")
    cues = []
    speaker = None
    for block in re.split(r"\n{2,}", normalized):
        rows = block.splitlines()
        timing_index = next((i for i, row in enumerate(rows) if "-->" in row), -1)
        if timing_index < 0 or (rows and re.match(r"^(NOTE|STYLE|REGION)\b", rows[0])):
            continue
        left, right = rows[timing_index].split("-->", 1)
        start = milliseconds(left.strip())
        end = milliseconds(right.strip().split()[0])
        raw = ""
        pending: int | None = None
        found_marks: list[dict[str, int]] = []
        for match in TAG_OR_TEXT.finditer(" ".join(rows[timing_index + 1 :])):
            tag, chunk = match.groups()
            if tag is not None:
                try:
                    pending = milliseconds(tag)
                except ValueError:
                    if tag.startswith("v ") or tag.startswith("v."):
                        name = html.unescape(re.sub(r"^v(?:\.\S*)?\s+", "", tag).strip())
                        speaker = speaker or name or None
                continue
            piece = html.unescape(chunk or "")
            if pending is not None and piece.strip():
                found_marks.append({"index": len(raw) + len(piece) - len(piece.lstrip()), "startMs": pending})
                pending = None
            raw += piece
        text = re.sub(r"\s+", " ", raw).strip()
        if not text:
            continue
        marks = _remap_marks(raw, text, found_marks)
        if marks and marks[0]["index"] > 0:
            marks.insert(0, {"index": 0, "startMs": start})
        elif marks:
            marks[0]["startMs"] = start
        cues.append({"text": text, "startMs": start, "endMs": max(end, start + 1), **({"marks": marks} if marks else {})})
    return {"cues": cues, **({"speaker": speaker} if speaker else {})}


def cues_to_words(cues: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    words = []
    for cue in cues:
        text = str(cue["text"])
        marks = list(cue.get("marks") or [{"index": 0, "startMs": int(cue["startMs"])}])
        if not marks or marks[0]["index"] != 0:
            marks.insert(0, {"index": 0, "startMs": int(cue["startMs"])})
        for index, mark in enumerate(marks):
            next_index = int(marks[index + 1]["index"]) if index + 1 < len(marks) else len(text)
            token = text[int(mark["index"]) : next_index].strip()
            if not token:
                continue
            estimated = index + 1 < len(marks)
            end_ms = int(marks[index + 1]["startMs"]) if estimated else int(cue["endMs"])
            words.append(
                {
                    "texto": token,
                    "inicio": int(mark["startMs"]) / 1000,
                    "fin": end_ms / 1000,
                    "fin_estimado": estimated,
                }
            )
    return words


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    write = subparsers.add_parser("escribir", aliases=["write"], help="palabras.json a WebVTT")
    write.add_argument("entrada", type=Path)
    write.add_argument("salida", type=Path)
    write.add_argument("--hablante")
    write.add_argument("--max-caracteres", type=int, default=42)
    read = subparsers.add_parser("leer", aliases=["read"], help="WebVTT a palabras.json")
    read.add_argument("entrada", type=Path)
    read.add_argument("salida", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in {"escribir", "write"}:
            value = json.loads(args.entrada.read_text(encoding="utf-8"))
            cues = words_to_cues(value, max_chars=args.max_caracteres)
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            args.salida.write_text(vtt_dumps(cues, speaker=args.hablante), encoding="utf-8")
            print(f"VTT: {len(cues)} cues")
        else:
            parsed = vtt_loads(args.entrada.read_text(encoding="utf-8"))
            words = cues_to_words(parsed["cues"])
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            args.salida.write_text(json.dumps({"palabras": words}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"PALABRAS: {len(words)}")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
