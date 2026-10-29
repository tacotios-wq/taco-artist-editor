#!/usr/bin/env python3
"""Exporta el EDL de ``montar.py`` a FCP7 XML, FCPXML y borrador CapCut.

Portado de packages/openfilm/studio/server/nle.mjs,
packages/openfilm/studio/server/fcpxml.mjs,
packages/openfilm/studio/server/jianying.mjs y
packages/openfilm/studio/server/markers.mjs.
OpenFilm commit de5a98b. Licencia MIT.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


@dataclass(frozen=True)
class Rate:
    """Cadencia exacta que entienden los editores."""

    timebase: int
    numerator: int
    denominator: int
    ntsc: bool

    @property
    def fps(self) -> float:
        return self.numerator / self.denominator


@dataclass(frozen=True)
class SourceTimecode:
    """Dirección SMPTE de un medio y su cadencia nativa."""

    value: str
    rate: Rate
    frame: int

    @property
    def displayformat(self) -> str:
        return "DF" if ";" in self.value else "NDF"


@dataclass(frozen=True)
class Clip:
    id: str
    block: str
    text: str
    media: Path
    timeline_in: float
    timeline_out: float
    source_in: float
    source_out: float
    source_timecode: SourceTimecode | None
    source_rate: Rate | None


@dataclass(frozen=True)
class Timeline:
    title: str
    rate: Rate
    width: int
    height: int
    clips: tuple[Clip, ...]
    duration_frames: int
    warnings: tuple[str, ...]


NTSC_RATES = {
    24: Fraction(24_000, 1001),
    30: Fraction(30_000, 1001),
    60: Fraction(60_000, 1001),
}
INTEGER_RATES = {24, 25, 30, 50, 60}


def nle_rate(value: float) -> Rate:
    """Convierte 23.976, 29.97 y 59.94 en razones 1000/1001 exactas."""

    fps = float(value)
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps debe ser un número positivo")
    for base, exact in NTSC_RATES.items():
        if abs(fps - float(exact)) < 0.002:
            return Rate(base, exact.numerator, exact.denominator, True)
    rounded = round(fps)
    if rounded in INTEGER_RATES and abs(fps - rounded) < 0.002:
        return Rate(rounded, rounded, 1, False)
    raise ValueError("fps no soportado; usa 23.976, 24, 25, 29.97, 30, 50, 59.94 o 60")


def _round_fraction(value: Fraction) -> int:
    if value < 0:
        raise ValueError("los tiempos no pueden ser negativos")
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def seconds_to_frames(seconds: float, rate: Rate) -> int:
    """Redondea cada borde por separado, igual que OpenFilm."""

    if not math.isfinite(float(seconds)):
        raise ValueError("tiempo no finito")
    return _round_fraction(Fraction(str(seconds)) * rate.numerator / rate.denominator)


def frame_span(start: float, end: float, rate: Rate) -> tuple[int, int]:
    return seconds_to_frames(start, rate), seconds_to_frames(end, rate)


def frames_to_timecode(frames: int, rate: Rate) -> str:
    """Dirección SMPTE sin drop-frame, usada para la secuencia relativa."""

    if frames < 0:
        raise ValueError("frames no puede ser negativo")
    hours, rest = divmod(frames, rate.timebase * 3600)
    minutes, rest = divmod(rest, rate.timebase * 60)
    seconds, frame = divmod(rest, rate.timebase)
    return f"{hours % 24:02d}:{minutes:02d}:{seconds:02d}:{frame:02d}"


def source_timecode(raw: str | None, fps: float | None) -> str | None:
    """Valida etiquetas SMPTE NDF/DF con las mismas fronteras que OpenFilm."""

    match = re.fullmatch(r"(\d{2}):([0-5]\d):([0-5]\d)([:;.])(\d{2,3})", raw or "")
    if not match or fps is None:
        return None
    try:
        rate = nle_rate(float(fps))
    except (TypeError, ValueError):
        return None
    hours, minutes, seconds, separator, frames = match.groups()
    frame = int(frames)
    if int(hours) >= 24 or frame >= rate.timebase:
        return None
    drop = separator != ":"
    skipped = rate.timebase // 15
    if drop and (
        not rate.ntsc
        or rate.timebase not in {30, 60}
        or (int(minutes) % 10 != 0 and int(seconds) == 0 and frame < skipped)
    ):
        return None
    return f"{hours}:{minutes}:{seconds}{';' if drop else ':'}{frames}"


def _source_timecode_details(raw: str | None, fps: float | None) -> SourceTimecode | None:
    value = source_timecode(raw, fps)
    if value is None or fps is None:
        return None
    rate = nle_rate(float(fps))
    hours, minutes, seconds, frames = (int(part) for part in re.split(r"[:;]", value))
    nominal = ((hours * 60 + minutes) * 60 + seconds) * rate.timebase + frames
    if ";" in value:
        dropped_per_minute = rate.timebase // 15
        total_minutes = hours * 60 + minutes
        nominal -= dropped_per_minute * (total_minutes - total_minutes // 10)
    return SourceTimecode(value=value, rate=rate, frame=nominal)


def _declared_timecode(value: Any, fps: float, context: str) -> SourceTimecode | None:
    if value is None:
        return None
    if isinstance(value, dict):
        raw = value.get("value", value.get("timecode"))
        declared_fps = value.get("fps", value.get("rate", fps))
    else:
        raw = value
        declared_fps = fps
    found = _source_timecode_details(str(raw) if raw is not None else None, float(declared_fps))
    if found is None:
        raise ValueError(f"{context} declara un timecode de origen inválido")
    return found


def _fraction_rate(raw: Any) -> float | None:
    try:
        value = Fraction(str(raw))
    except (ValueError, ZeroDivisionError):
        return None
    result = float(value)
    return result if math.isfinite(result) and 0 < result <= 240 else None


def _tag(tags: Any, name: str) -> str | None:
    if not isinstance(tags, dict):
        return None
    return next((str(value) for key, value in tags.items() if str(key).casefold() == name.casefold()), None)


def probe_source_metadata(path: Path) -> tuple[SourceTimecode | None, Rate | None, str | None]:
    """Lee cadencia y timecode nativos sin hacer obligatorio ``ffprobe``."""

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format_tags=timecode:stream=codec_type,avg_frame_rate,r_frame_rate:stream_tags=timecode",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, None, f"{path}: ffprobe no pudo leer los metadatos ({exc}); se usa 00:00:00:00 y la cadencia de secuencia"
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else f"código {result.returncode}"
        return None, None, f"{path}: ffprobe falló ({detail}); se usa 00:00:00:00 y la cadencia de secuencia"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, None, f"{path}: ffprobe devolvió JSON inválido; se usa 00:00:00:00 y la cadencia de secuencia"
    streams = data.get("streams", []) if isinstance(data, dict) else []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    tagged_stream = next((stream for stream in streams if _tag(stream.get("tags"), "timecode")), None)
    fps = _fraction_rate((video or {}).get("avg_frame_rate"))
    fps = fps or _fraction_rate((video or {}).get("r_frame_rate"))
    try:
        rate = nle_rate(fps) if fps is not None else None
    except ValueError:
        rate = None
    raw = _tag((video or {}).get("tags"), "timecode")
    raw = raw or _tag(data.get("format", {}).get("tags"), "timecode")
    raw = raw or _tag((tagged_stream or {}).get("tags"), "timecode")
    if raw is None:
        warning = None if rate is not None or fps is None else f"{path}: ffprobe devolvió una cadencia no soportada; se usa la de secuencia"
        return None, rate, warning
    found = _source_timecode_details(raw, fps)
    if found is None:
        return None, rate, f"{path}: ffprobe devolvió un timecode o cadencia inválidos; se usa 00:00:00:00"
    return found, rate, None


def probe_source_timecode(path: Path) -> tuple[SourceTimecode | None, str | None]:
    """Compatibilidad para consumidores que solo necesitan el timecode."""

    found, _, warning = probe_source_metadata(path)
    return found, warning


def _number(mapping: dict[str, Any], names: Iterable[str], *, required: bool = True) -> float | None:
    for name in names:
        if name in mapping:
            value = float(mapping[name])
            if not math.isfinite(value):
                raise ValueError(f"{name} debe ser finito")
            return value
    if required:
        raise ValueError(f"falta {next(iter(names))}")
    return None


def _absolute_media(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).absolute()


def load_timeline(
    value: Any,
    *,
    base: Path = Path.cwd(),
    master: str | Path | None = None,
    fps: float | None = None,
    title: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> Timeline:
    """Adapta una lista ``edl.json`` o un objeto con ``edl``/``clips``."""

    metadata = value if isinstance(value, dict) else {}
    raw_clips = value if isinstance(value, list) else metadata.get("edl", metadata.get("clips"))
    if not isinstance(raw_clips, list):
        raise ValueError("el plan debe ser una lista EDL o contener edl/clips")
    chosen_fps = fps if fps is not None else float(metadata.get("fps", 25))
    rate = nle_rate(chosen_fps)
    default_media = master or metadata.get("master") or metadata.get("media") or metadata.get("source")
    default_timecode = metadata.get("source_timecode", metadata.get("timecode"))
    default_source_fps = metadata.get("source_fps", metadata.get("timecode_fps"))
    media_timecodes = metadata.get("media_timecodes", metadata.get("timecodes", {}))
    if not isinstance(media_timecodes, dict):
        raise ValueError("media_timecodes debe ser un objeto")
    clips: list[Clip] = []
    declared_by_media: dict[Path, SourceTimecode] = {}
    rates_by_media: dict[Path, Rate] = {}
    last_start = -1.0
    for index, raw in enumerate(raw_clips, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"clip {index} no es un objeto")
        clip_id = str(raw.get("id", raw.get("n", index))).strip()
        if not clip_id:
            raise ValueError(f"clip {index} sin id")
        timeline_in = float(_number(raw, ("montaje_in", "timeline_in", "at")))
        timeline_out = float(_number(raw, ("montaje_out", "timeline_out", "end")))
        source_in = float(_number(raw, ("master_in", "source_in", "from")))
        source_out = float(_number(raw, ("master_out", "source_out", "to")))
        if min(timeline_in, source_in) < 0 or timeline_out <= timeline_in or source_out <= source_in:
            raise ValueError(f"clip {clip_id} tiene un rango inválido")
        if timeline_in < last_start:
            raise ValueError("los clips deben conservar el orden temporal del plan")
        if clips and timeline_in < clips[-1].timeline_out:
            raise ValueError(f"clip {clip_id} solapa al anterior")
        media = raw.get("media") or raw.get("master") or raw.get("source") or default_media
        if not isinstance(media, (str, Path)) or not str(media).strip():
            raise ValueError(f"clip {clip_id} no declara media y no se indicó --master")
        media_path = _absolute_media(str(media), base)
        declaration = raw.get("source_timecode", raw.get("timecode"))
        if declaration is None:
            declaration = media_timecodes.get(str(media), media_timecodes.get(str(media_path), default_timecode))
        source_fps = raw.get("source_fps", raw.get("timecode_fps"))
        timecode_fps = declaration.get("fps", declaration.get("rate")) if isinstance(declaration, dict) else None
        try:
            source_rate = nle_rate(float(source_fps)) if source_fps is not None else None
            timecode_rate = nle_rate(float(timecode_fps)) if timecode_fps is not None else None
            default_rate = nle_rate(float(default_source_fps)) if default_source_fps is not None else None
        except (TypeError, ValueError):
            raise ValueError(f"clip {clip_id} declara una cadencia de origen inválida") from None
        if source_rate is not None and timecode_rate is not None and source_rate != timecode_rate:
            raise ValueError(f"clip {clip_id} declara cadencias de origen incompatibles")
        declared_rate = source_rate or timecode_rate or default_rate
        if declared_rate is None and declaration is not None:
            declared_rate = rate
        declared = _declared_timecode(declaration, declared_rate.fps if declared_rate else chosen_fps, f"clip {clip_id}")
        if declared is not None and declared_rate is not None and declared.rate != declared_rate:
            raise ValueError(f"clip {clip_id} declara cadencias de origen incompatibles")
        previous_timecode = declared_by_media.get(media_path)
        if declared is not None and previous_timecode is not None and declared != previous_timecode:
            raise ValueError(f"el medio {media_path} declara timecodes incompatibles")
        previous_rate = rates_by_media.get(media_path)
        if declared_rate is not None and previous_rate is not None and declared_rate != previous_rate:
            raise ValueError(f"el medio {media_path} declara cadencias incompatibles")
        if declared is not None:
            declared_by_media[media_path] = declared
        if declared_rate is not None:
            rates_by_media[media_path] = declared_rate
        clips.append(
            Clip(
                id=clip_id,
                block=str(raw.get("bloque", raw.get("block", "sin-bloque"))).strip() or "sin-bloque",
                text=str(raw.get("texto", raw.get("text", ""))).strip(),
                media=media_path,
                timeline_in=timeline_in,
                timeline_out=timeline_out,
                source_in=source_in,
                source_out=source_out,
                source_timecode=declared,
                source_rate=declared_rate,
            )
        )
        last_start = timeline_in
    warnings: list[str] = []
    resolved_timecodes = dict(declared_by_media)
    resolved_rates = dict(rates_by_media)
    for media_path in dict.fromkeys(clip.media for clip in clips):
        if media_path in resolved_timecodes and media_path in resolved_rates:
            continue
        if not media_path.is_file():
            continue
        found, found_rate, warning = probe_source_metadata(media_path)
        if media_path not in resolved_rates and found_rate is not None:
            resolved_rates[media_path] = found_rate
        if found is not None and media_path not in resolved_timecodes and found.rate == resolved_rates.get(media_path, found.rate):
            resolved_timecodes[media_path] = found
        elif found is not None and found.rate != resolved_rates.get(media_path):
            warnings.append(f"{media_path}: el timecode de ffprobe usa otra cadencia y se ignora")
        if warning is not None:
            warnings.append(warning)
    clips = [
        replace(
            clip,
            source_timecode=resolved_timecodes.get(clip.media),
            source_rate=resolved_rates.get(clip.media, rate),
        )
        for clip in clips
    ]
    duration = max((seconds_to_frames(c.timeline_out, rate) for c in clips), default=1)
    final_width = int(width if width is not None else metadata.get("width", metadata.get("ancho", 1920)))
    final_height = int(height if height is not None else metadata.get("height", metadata.get("alto", 1080)))
    if final_width <= 0 or final_height <= 0:
        raise ValueError("ancho y alto deben ser positivos")
    return Timeline(
        title=(title or str(metadata.get("title", metadata.get("titulo", "Taco Artist")))).strip() or "Taco Artist",
        rate=rate,
        width=final_width,
        height=final_height,
        clips=tuple(clips),
        duration_frames=max(1, duration),
        warnings=tuple(warnings),
    )


def markers(timeline: Timeline) -> list[dict[str, Any]]:
    """Un marcador en el primer clip de cada bloque, en orden de aparición."""

    seen: set[str] = set()
    result = []
    for clip in timeline.clips:
        if clip.block in seen:
            continue
        seen.add(clip.block)
        result.append({"name": clip.block, "frame": seconds_to_frames(clip.timeline_in, timeline.rate), "clip": clip.id})
    return result


def file_url(path: Path) -> str:
    """URL xmeml compatible con Premiere y Resolve, incluidos espacios y Unicode."""

    posix = path.absolute().as_posix()
    return "file://localhost" + quote(posix, safe="/:")


def _add(parent: ET.Element, tag: str, text: Any | None = None, **attrs: str) -> ET.Element:
    node = ET.SubElement(parent, tag, attrs)
    if text is not None:
        node.text = str(text)
    return node


def _xmeml_rate(parent: ET.Element, rate: Rate) -> None:
    node = _add(parent, "rate")
    _add(node, "timebase", rate.timebase)
    _add(node, "ntsc", "TRUE" if rate.ntsc else "FALSE")


def _xmeml_timecode(parent: ET.Element, rate: Rate, source: SourceTimecode | None = None) -> None:
    node = _add(parent, "timecode")
    _xmeml_rate(node, source.rate if source else rate)
    _add(node, "string", source.value if source else frames_to_timecode(0, rate))
    _add(node, "frame", source.frame if source else 0)
    _add(node, "displayformat", source.displayformat if source else "NDF")


def _media_index(timeline: Timeline) -> tuple[list[Path], dict[Path, int], dict[Path, int], dict[Path, Rate]]:
    paths = list(dict.fromkeys(c.media for c in timeline.clips))
    ids = {path: index for index, path in enumerate(paths, 1)}
    rates = {
        path: next((c.source_rate for c in timeline.clips if c.media == path and c.source_rate is not None), timeline.rate)
        for path in paths
    }
    durations = {
        path: max(
            (seconds_to_frames(c.source_out, rates[path]) for c in timeline.clips if c.media == path),
            default=1,
        )
        for path in paths
    }
    return paths, ids, durations, rates


def fcp7_xml(timeline: Timeline) -> str:
    """Documento xmeml v4 importable en Premiere y DaVinci Resolve."""

    root = ET.Element("xmeml", {"version": "4"})
    sequence = _add(root, "sequence", id="sequence-1")
    _add(sequence, "name", timeline.title)
    _add(sequence, "duration", timeline.duration_frames)
    _xmeml_rate(sequence, timeline.rate)
    _xmeml_timecode(sequence, timeline.rate)
    media = _add(sequence, "media")
    video = _add(media, "video")
    fmt = _add(video, "format")
    props = _add(fmt, "samplecharacteristics")
    _xmeml_rate(props, timeline.rate)
    _add(props, "width", timeline.width)
    _add(props, "height", timeline.height)
    _add(props, "pixelaspectratio", "square")
    _add(props, "fielddominance", "none")
    video_track = _add(video, "track")
    audio = _add(media, "audio")
    _add(audio, "numOutputChannels", 2)
    audio_track = _add(audio, "track", premiereTrackType="Stereo")
    paths, ids, durations, source_rates = _media_index(timeline)
    written: set[Path] = set()

    def clipitem(track: ET.Element, clip: Clip, kind: str, index: int) -> None:
        start, end = frame_span(clip.timeline_in, clip.timeline_out, timeline.rate)
        source_rate = source_rates[clip.media]
        source_in, source_out = frame_span(clip.source_in, clip.source_out, source_rate)
        item = _add(track, "clipitem", id=f"{kind}-clip-{index}")
        _add(item, "name", clip.id)
        _add(item, "enabled", "TRUE")
        _add(item, "duration", durations[clip.media])
        _xmeml_rate(item, source_rate)
        _add(item, "start", start)
        _add(item, "end", end)
        _add(item, "in", source_in)
        _add(item, "out", source_out)
        file = _add(item, "file", id=f"file-{ids[clip.media]}")
        if clip.media not in written:
            written.add(clip.media)
            _add(file, "name", clip.media.name)
            _add(file, "pathurl", file_url(clip.media))
            _xmeml_rate(file, source_rate)
            _add(file, "duration", durations[clip.media])
            _xmeml_timecode(file, source_rate, clip.source_timecode)
            file_media = _add(file, "media")
            file_video = _add(file_media, "video")
            sample = _add(file_video, "samplecharacteristics")
            _xmeml_rate(sample, source_rate)
            _add(sample, "width", timeline.width)
            _add(sample, "height", timeline.height)
            file_audio = _add(file_media, "audio")
            sample_audio = _add(file_audio, "samplecharacteristics")
            _add(sample_audio, "depth", 16)
            _add(sample_audio, "samplerate", 48000)
            _add(file_audio, "channelcount", 2)
        if kind == "audio":
            source_track = _add(item, "sourcetrack")
            _add(source_track, "mediatype", "audio")
            _add(source_track, "trackindex", 1)

    for index, clip in enumerate(timeline.clips, 1):
        clipitem(video_track, clip, "video", index)
    for index, clip in enumerate(timeline.clips, 1):
        clipitem(audio_track, clip, "audio", index)
    for marker in markers(timeline):
        node = _add(sequence, "marker")
        _add(node, "name", marker["name"])
        _add(node, "comment", f"Bloque {marker['name']}")
        _add(node, "in", marker["frame"])
        _add(node, "out", -1)
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n{body}\n'


def _fcpx_time(frames: int, rate: Rate) -> str:
    return f"{frames * rate.denominator}/{rate.numerator}s"


def fcpxml(timeline: Timeline) -> str:
    """Documento FCPXML 1.10 con huecos y marcadores conservados."""

    root = ET.Element("fcpxml", {"version": "1.10"})
    resources = _add(root, "resources")
    _add(
        resources,
        "format",
        id="sequence-format",
        frameDuration=_fcpx_time(1, timeline.rate),
        width=str(timeline.width),
        height=str(timeline.height),
        colorSpace="1-1-1 (Rec. 709)",
    )
    paths, ids, durations, source_rates = _media_index(timeline)
    source_timecodes = {clip.media: clip.source_timecode for clip in timeline.clips if clip.source_timecode is not None}
    for path in paths:
        file_id = ids[path]
        source_rate = source_rates[path]
        source_tc = source_timecodes.get(path)
        _add(
            resources,
            "format",
            id=f"format-file-{file_id}",
            frameDuration=_fcpx_time(1, source_rate),
            width=str(timeline.width),
            height=str(timeline.height),
            colorSpace="1-1-1 (Rec. 709)",
        )
        asset = _add(
            resources,
            "asset",
            id=f"file-{file_id}",
            name=path.name,
            start=_fcpx_time(source_tc.frame, source_tc.rate) if source_tc else "0s",
            duration=_fcpx_time(durations[path], source_rate),
            hasVideo="1",
            hasAudio="1",
            format=f"format-file-{file_id}",
            audioSources="1",
            audioChannels="2",
            audioRate="48000",
        )
        _add(asset, "media-rep", kind="original-media", src=file_url(path))
    library = _add(root, "library")
    event = _add(library, "event", name=timeline.title)
    project = _add(event, "project", name=timeline.title)
    sequence = _add(
        project,
        "sequence",
        format="sequence-format",
        duration=_fcpx_time(timeline.duration_frames, timeline.rate),
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k",
    )
    spine = _add(sequence, "spine")
    first_marker = {m["clip"]: m for m in markers(timeline)}
    cursor = 0
    for clip in timeline.clips:
        start, end = frame_span(clip.timeline_in, clip.timeline_out, timeline.rate)
        source_rate = source_rates[clip.media]
        source_in, source_out = frame_span(clip.source_in, clip.source_out, source_rate)
        source_tc = source_timecodes.get(clip.media)
        absolute_source_in = (source_tc.frame if source_tc else 0) + source_in
        if start > cursor:
            _add(
                spine,
                "gap",
                name="Aire",
                offset=_fcpx_time(cursor, timeline.rate),
                start="0s",
                duration=_fcpx_time(start - cursor, timeline.rate),
            )
        item = _add(
            spine,
            "asset-clip",
            ref=f"file-{ids[clip.media]}",
            name=clip.id,
            offset=_fcpx_time(start, timeline.rate),
            start=_fcpx_time(absolute_source_in, source_rate),
            duration=_fcpx_time(source_out - source_in, source_rate),
            format=f"format-file-{ids[clip.media]}",
            tcFormat=(source_tc.displayformat if source_tc else "NDF"),
            audioRole="dialogue",
        )
        if clip.id in first_marker:
            _add(
                item,
                "marker",
                start=_fcpx_time(absolute_source_in, source_rate),
                duration=_fcpx_time(1, source_rate),
                value=first_marker[clip.id]["name"],
            )
        cursor = end
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n{body}\n'


def _stable_id(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "taco-artist:" + ":".join(parts))).upper()


def _microseconds(frames: int, rate: Rate) -> int:
    return _round_fraction(Fraction(frames * rate.denominator * 1_000_000, rate.numerator))


def capcut_draft(timeline: Timeline, folder: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Borrador mínimo de CapCut/Jianying, versión declaradamente cambiante."""

    paths, ids, durations, source_rates = _media_index(timeline)
    materials = []
    library = []
    material_ids: dict[Path, str] = {}
    for path in paths:
        material_id = _stable_id(timeline.title, str(path))
        material_ids[path] = material_id
        duration = _microseconds(durations[path], source_rates[path])
        materials.append(
            {
                "id": material_id,
                "local_material_id": material_id,
                "path": str(path),
                "name": path.name,
                "type": "video",
                "duration": duration,
                "width": timeline.width,
                "height": timeline.height,
                "material_name": path.name,
            }
        )
        library.append(
            {
                "id": material_id,
                "file_Path": str(path),
                "metetype": "video",
                "duration": duration,
                "width": timeline.width,
                "height": timeline.height,
            }
        )
    speeds = []
    segments = []
    for index, clip in enumerate(timeline.clips, 1):
        start, end = frame_span(clip.timeline_in, clip.timeline_out, timeline.rate)
        source_rate = source_rates[clip.media]
        source_in, source_out = frame_span(clip.source_in, clip.source_out, source_rate)
        speed_id = _stable_id(timeline.title, "speed", str(index))
        speeds.append({"id": speed_id, "type": "speed", "speed": 1.0, "curve_speed": None})
        segments.append(
            {
                "id": _stable_id(timeline.title, "segment", str(index)),
                "material_id": material_ids[clip.media],
                "target_timerange": {"start": _microseconds(start, timeline.rate), "duration": _microseconds(end - start, timeline.rate)},
                "source_timerange": {"start": _microseconds(source_in, source_rate), "duration": _microseconds(source_out - source_in, source_rate)},
                "extra_material_refs": [speed_id],
                "visible": True,
                "volume": 1.0,
                "render_index": 0,
                "clip": {"alpha": 1.0, "scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}, "rotation": 0.0},
            }
        )
    duration_us = _microseconds(timeline.duration_frames, timeline.rate)
    draft_id = _stable_id(timeline.title, "draft")
    platform = {"app_id": 3704, "app_source": "cc", "app_version": "13.0.0", "device_id": "", "hard_disk_id": "", "os": "mac"}
    info = {
        "id": draft_id,
        "name": timeline.title,
        "duration": duration_us,
        "fps": round(timeline.rate.fps, 6),
        "canvas_config": {"width": timeline.width, "height": timeline.height, "ratio": "original"},
        "color_space": 0,
        "config": {"maintrack_adsorb": False, "material_save_mode": 0, "video_mute": False},
        "materials": {"videos": materials, "audios": [], "audio_fades": [], "speeds": speeds, "texts": []},
        "tracks": [{"id": _stable_id(timeline.title, "track"), "type": "video", "name": "V1", "segments": segments, "attribute": 0, "flag": 0}],
        "time_marks": [
            {"id": _stable_id(timeline.title, "marker", m["name"]), "name": m["name"], "time": _microseconds(m["frame"], timeline.rate), "color": "blue"}
            for m in markers(timeline)
        ],
        "platform": platform,
        "last_modified_platform": platform,
        "version": 360000,
        "new_version": "110.0.0",
    }
    meta = {
        "draft_id": draft_id,
        "draft_name": timeline.title,
        "draft_fold_path": str(folder),
        "draft_root_path": str(folder.parent),
        "tm_duration": duration_us,
        "draft_materials": [{"type": 0, "value": library}],
        "draft_materials_copied_info": [],
        "draft_new_version": "",
    }
    return info, meta


def export_all(timeline: Timeline, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    capcut = output / "capcut"
    capcut.mkdir(parents=True, exist_ok=True)
    paths = [output / "premiere-resolve.xml", output / "final-cut.fcpxml", capcut / "draft_content.json", capcut / "draft_meta_info.json"]
    paths[0].write_text(fcp7_xml(timeline), encoding="utf-8")
    paths[1].write_text(fcpxml(timeline), encoding="utf-8")
    content, meta = capcut_draft(timeline, capcut)
    paths[2].write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths[3].write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="edl.json o plan JSON con edl/clips")
    parser.add_argument("salida", type=Path, help="carpeta de exportación")
    parser.add_argument("--master", type=Path, help="medio común cuando el plan no lo declara")
    parser.add_argument("--fps", type=float)
    parser.add_argument("--titulo")
    parser.add_argument("--ancho", type=int)
    parser.add_argument("--alto", type=int)
    args = parser.parse_args(argv)
    try:
        value = json.loads(args.plan.read_text(encoding="utf-8"))
        timeline = load_timeline(
            value,
            base=args.plan.parent,
            master=args.master,
            fps=args.fps,
            title=args.titulo,
            width=args.ancho,
            height=args.alto,
        )
        paths = export_all(timeline, args.salida)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for warning in timeline.warnings:
        print(f"AVISO: {warning}", file=sys.stderr)
    print(f"EXPORTADOS: {len(timeline.clips)} clips, {len(markers(timeline))} marcadores")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
