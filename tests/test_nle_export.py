"""Casos portados de nle-timecode, fcpxml, jianying y markers de OpenFilm.

Origen: packages/openfilm/studio/server/*.test.mjs, commit de5a98b, licencia MIT.
"""

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from nle_export import (
    capcut_draft,
    fcp7_xml,
    fcpxml,
    frame_span,
    load_timeline,
    markers,
    nle_rate,
    seconds_to_frames,
    source_timecode,
)


# Plan de ejemplo ejecutable dentro de tests. Reproduce el edl.json de montar.py.
PLAN_EJEMPLO = {
    "titulo": "Entrevista: taco & arte",
    "fps": 29.97,
    "width": 1080,
    "height": 1920,
    "master": "/tmp/Medios/Entrevista á 01.mov",
    "edl": [
        {
            "n": 1,
            "id": "gancho-1",
            "bloque": "gancho",
            "montaje_in": 0.0,
            "montaje_out": 1.001,
            "master_in": 4.0,
            "master_out": 5.001,
            "texto": "Esto cambió todo.",
        },
        {
            "n": 2,
            "id": "gancho-2",
            "bloque": "gancho",
            "montaje_in": 1.301,
            "montaje_out": 2.301,
            "master_in": 8.0,
            "master_out": 9.0,
            "texto": "Y nadie lo esperaba.",
        },
        {
            "n": 3,
            "id": "cierre-1",
            "bloque": "cierre",
            "montaje_in": 3.001,
            "montaje_out": 4.502,
            "master_in": 12.0,
            "master_out": 13.501,
            "texto": "Por eso seguimos cocinando.",
        },
    ],
}


class NleExportTest(unittest.TestCase):
    def setUp(self):
        self.timeline = load_timeline(PLAN_EJEMPLO)

    def test_frames_ntsc_2997_y_23976_redondean_cada_borde(self):
        rate_2997 = nle_rate(29.97)
        rate_23976 = nle_rate(23.976)
        self.assertEqual((rate_2997.numerator, rate_2997.denominator), (30000, 1001))
        self.assertEqual((rate_23976.numerator, rate_23976.denominator), (24000, 1001))
        self.assertEqual(seconds_to_frames(10, rate_2997), 300)
        self.assertEqual(seconds_to_frames(10, rate_23976), 240)
        self.assertEqual(frame_span(0, 1.001, rate_2997), (0, 30))
        self.assertEqual(frame_span(1.001, 2.002, rate_2997)[0], 30)

    def test_timecode_valida_ndf_df_y_frontera_de_minuto(self):
        self.assertEqual(source_timecode("01:00:00:00", 25), "01:00:00:00")
        self.assertEqual(source_timecode("01:00:00.00", 29.97), "01:00:00;00")
        self.assertEqual(source_timecode("00:01:00;02", 29.97), "00:01:00;02")
        self.assertIsNone(source_timecode("00:01:00;00", 29.97))
        self.assertIsNone(source_timecode("01:00:00;00", 25))
        self.assertIsNone(source_timecode("24:00:00:00", 25))

    def test_numero_y_orden_de_clips_igual_al_plan(self):
        self.assertEqual([clip.id for clip in self.timeline.clips], [item["id"] for item in PLAN_EJEMPLO["edl"]])
        self.assertEqual(len(self.timeline.clips), 3)
        self.assertEqual(self.timeline.duration_frames, seconds_to_frames(4.502, self.timeline.rate))

    def test_fcp7_es_xml_bien_formado_con_ruta_local_y_marcadores(self):
        body = fcp7_xml(self.timeline)
        root = ET.fromstring(body)
        video_items = root.findall("./sequence/media/video/track/clipitem")
        audio_items = root.findall("./sequence/media/audio/track/clipitem")
        self.assertEqual([item.findtext("name") for item in video_items], ["gancho-1", "gancho-2", "cierre-1"])
        self.assertEqual(len(audio_items), 3)
        self.assertIn("file://localhost/tmp/Medios/Entrevista%20%C3%A1%2001.mov", body)
        self.assertEqual([item.findtext("name") for item in root.findall("./sequence/marker")], ["gancho", "cierre"])

    def test_fcpxml_es_bien_formado_con_ntsc_huecos_y_marcadores(self):
        body = fcpxml(self.timeline)
        root = ET.fromstring(body)
        self.assertEqual(root.tag, "fcpxml")
        self.assertEqual(root.find("./resources/format").attrib["frameDuration"], "1001/30000s")
        clips = root.findall("./library/event/project/sequence/spine/asset-clip")
        self.assertEqual([item.attrib["name"] for item in clips], ["gancho-1", "gancho-2", "cierre-1"])
        self.assertEqual(len(root.findall(".//gap")), 2)
        self.assertEqual([item.attrib["value"] for item in root.findall(".//marker")], ["gancho", "cierre"])
        self.assertIn("file://localhost/tmp/Medios/Entrevista%20%C3%A1%2001.mov", body)

    def test_xmeml_y_fcpxml_consumen_timecode_ndf_y_drop_frame_del_plan(self):
        camera_a = "/tmp/Medios/Cámara A.mov"
        camera_b = "/tmp/Medios/Cámara B.mov"
        plan = {
            "fps": 29.97,
            "media_timecodes": {
                camera_a: {"value": "01:00:00:00", "fps": 25},
                camera_b: {"value": "01:00:00;00", "fps": 29.97},
            },
            "edl": [
                {
                    "id": "a",
                    "bloque": "uno",
                    "media": camera_a,
                    "montaje_in": 0,
                    "montaje_out": 1,
                    "master_in": 0,
                    "master_out": 1,
                },
                {
                    "id": "b",
                    "bloque": "dos",
                    "media": camera_b,
                    "montaje_in": 1,
                    "montaje_out": 2,
                    "master_in": 0,
                    "master_out": 1,
                },
            ],
        }
        timeline = load_timeline(plan)

        xmeml = ET.fromstring(fcp7_xml(timeline))
        files = {node.findtext("name"): node for node in xmeml.findall(".//file") if node.find("timecode") is not None}
        tc_a = files["Cámara A.mov"].find("timecode")
        tc_b = files["Cámara B.mov"].find("timecode")
        self.assertEqual(
            (tc_a.findtext("string"), tc_a.findtext("frame"), tc_a.findtext("displayformat")),
            ("01:00:00:00", "90000", "NDF"),
        )
        self.assertEqual(
            (tc_b.findtext("string"), tc_b.findtext("frame"), tc_b.findtext("displayformat")),
            ("01:00:00;00", "107892", "DF"),
        )
        self.assertEqual(tc_b.findtext("rate/timebase"), "30")
        self.assertEqual(tc_b.findtext("rate/ntsc"), "TRUE")

        final_cut = ET.fromstring(fcpxml(timeline))
        assets = {node.attrib["name"]: node for node in final_cut.findall("./resources/asset")}
        self.assertEqual(assets["Cámara A.mov"].attrib["start"], "90000/25s")
        self.assertEqual(assets["Cámara B.mov"].attrib["start"], "107999892/30000s")
        clips = {node.attrib["name"]: node for node in final_cut.findall(".//asset-clip")}
        self.assertEqual(clips["a"].attrib["tcFormat"], "NDF")
        self.assertEqual(clips["b"].attrib["tcFormat"], "DF")

    def test_cadencias_mixtas_conservan_frames_timecode_y_posicion(self):
        cases = [
            {
                "name": "23976_en_2997",
                "sequence_fps": 29.97,
                "source_fps": 23.976,
                "timeline": (1.001, 2.002),
                "source": (4.004, 5.005),
                "sequence_frames": (30, 60),
                "source_frames": (96, 120),
                "timebase": "24",
                "ntsc": "TRUE",
                "frame_duration": "1001/24000s",
                "timecode_frame": "86400",
                "asset_start": "86486400/24000s",
                "clip_start": "86582496/24000s",
                "clip_duration": "24024/24000s",
                "offset": "30030/30000s",
            },
            {
                "name": "25_en_30",
                "sequence_fps": 30,
                "source_fps": 25,
                "timeline": (2, 3),
                "source": (4, 5),
                "sequence_frames": (60, 90),
                "source_frames": (100, 125),
                "timebase": "25",
                "ntsc": "FALSE",
                "frame_duration": "1/25s",
                "timecode_frame": "90000",
                "asset_start": "90000/25s",
                "clip_start": "90100/25s",
                "clip_duration": "25/25s",
                "offset": "60/30s",
            },
        ]
        for case in cases:
            with self.subTest(case["name"]):
                timeline_in, timeline_out = case["timeline"]
                source_in, source_out = case["source"]
                plan = {
                    "fps": case["sequence_fps"],
                    "edl": [
                        {
                            "id": case["name"],
                            "media": f"/tmp/{case['name']}.mov",
                            "source_fps": case["source_fps"],
                            "source_timecode": "01:00:00:00",
                            "montaje_in": timeline_in,
                            "montaje_out": timeline_out,
                            "master_in": source_in,
                            "master_out": source_out,
                        }
                    ],
                }
                timeline = load_timeline(plan)

                xmeml = ET.fromstring(fcp7_xml(timeline))
                item = xmeml.find("./sequence/media/video/track/clipitem")
                self.assertIsNotNone(item)
                self.assertEqual(
                    tuple(int(item.findtext(name)) for name in ("start", "end")),
                    case["sequence_frames"],
                )
                self.assertEqual(
                    tuple(int(item.findtext(name)) for name in ("in", "out")),
                    case["source_frames"],
                )
                self.assertEqual(item.findtext("rate/timebase"), case["timebase"])
                self.assertEqual(item.findtext("rate/ntsc"), case["ntsc"])
                file = item.find("file")
                self.assertEqual(file.findtext("rate/timebase"), case["timebase"])
                self.assertEqual(file.findtext("media/video/samplecharacteristics/rate/timebase"), case["timebase"])
                self.assertEqual(file.findtext("timecode/string"), "01:00:00:00")
                self.assertEqual(file.findtext("timecode/frame"), case["timecode_frame"])
                self.assertEqual(file.findtext("duration"), str(case["source_frames"][1]))

                final_cut = ET.fromstring(fcpxml(timeline))
                source_format = final_cut.find("./resources/format[@id='format-file-1']")
                asset = final_cut.find("./resources/asset")
                clip = final_cut.find(".//asset-clip")
                self.assertEqual(source_format.attrib["frameDuration"], case["frame_duration"])
                self.assertEqual(asset.attrib["start"], case["asset_start"])
                self.assertEqual(clip.attrib["offset"], case["offset"])
                self.assertEqual(clip.attrib["start"], case["clip_start"])
                self.assertEqual(clip.attrib["duration"], case["clip_duration"])
                self.assertEqual(clip.attrib["format"], "format-file-1")

    def test_cadencia_igual_conserva_los_tiempos_relativos_existentes(self):
        timeline = load_timeline(
            {
                "fps": 25,
                "master": "/tmp/camera-25.mov",
                "source_fps": 25,
                "edl": [
                    {
                        "id": "igual",
                        "montaje_in": 2,
                        "montaje_out": 3,
                        "master_in": 4,
                        "master_out": 5,
                    }
                ],
            }
        )
        xmeml = ET.fromstring(fcp7_xml(timeline)).find("./sequence/media/video/track/clipitem")
        self.assertEqual(
            tuple(xmeml.findtext(name) for name in ("start", "end", "in", "out")),
            ("50", "75", "100", "125"),
        )
        clip = ET.fromstring(fcpxml(timeline)).find(".//asset-clip")
        self.assertEqual(
            tuple(clip.attrib[name] for name in ("offset", "start", "duration")),
            ("50/25s", "100/25s", "25/25s"),
        )

    def test_ffprobe_automatico_es_tolerante_y_avisa_si_falla(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "camera.mov"
            media.touch()
            plan = {
                "fps": 29.97,
                "master": str(media),
                "edl": [
                    {
                        "id": "a",
                        "montaje_in": 0,
                        "montaje_out": 1,
                        "master_in": 0,
                        "master_out": 1,
                    }
                ],
            }
            probe = mock.Mock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "format": {"tags": {}},
                        "streams": [
                            {
                                "codec_type": "video",
                                "avg_frame_rate": "30000/1001",
                                "r_frame_rate": "30000/1001",
                                "tags": {"timecode": "01:00:00;00"},
                            }
                        ],
                    }
                ),
                stderr="",
            )
            with mock.patch("nle_export.subprocess.run", return_value=probe):
                timeline = load_timeline(plan)
            self.assertFalse(timeline.warnings)
            self.assertIn("<string>01:00:00;00</string>", fcp7_xml(timeline))
            self.assertIn('start="107999892/30000s"', fcpxml(timeline))

            probe_without_timecode = mock.Mock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "format": {"tags": {}},
                        "streams": [
                            {
                                "codec_type": "video",
                                "avg_frame_rate": "25/1",
                                "r_frame_rate": "25/1",
                                "tags": {},
                            }
                        ],
                    }
                ),
                stderr="",
            )
            with mock.patch("nle_export.subprocess.run", return_value=probe_without_timecode):
                native_rate = load_timeline(plan)
            self.assertEqual(native_rate.clips[0].source_rate, nle_rate(25))
            self.assertEqual(ET.fromstring(fcp7_xml(native_rate)).findtext(".//clipitem/out"), "25")
            self.assertIn('frameDuration="1/25s"', fcpxml(native_rate))

            with mock.patch("nle_export.subprocess.run", side_effect=FileNotFoundError("ffprobe")):
                fallback = load_timeline(plan)
            self.assertEqual(len(fallback.warnings), 1)
            self.assertIn("se usa 00:00:00:00", fallback.warnings[0])
            self.assertIn("<string>00:00:00:00</string>", fcp7_xml(fallback))

    def test_capcut_conserva_microsegundos_orden_rutas_y_marcadores(self):
        info, meta = capcut_draft(self.timeline, Path("/tmp/Drafts/Entrevista"))
        self.assertEqual(info["canvas_config"], {"width": 1080, "height": 1920, "ratio": "original"})
        segments = info["tracks"][0]["segments"]
        self.assertEqual(len(segments), 3)
        self.assertEqual([segment["target_timerange"]["start"] for segment in segments], [0, 1_301_300, 3_003_000])
        self.assertEqual([marker["name"] for marker in info["time_marks"]], ["gancho", "cierre"])
        self.assertEqual(meta["draft_id"], info["id"])
        self.assertEqual(info["materials"]["videos"][0]["path"], "/tmp/Medios/Entrevista á 01.mov")

    def test_plan_vacio_es_valido_y_plan_fuera_de_orden_falla(self):
        empty = load_timeline({"fps": 25, "master": "/tmp/master.mov", "edl": []})
        self.assertEqual(empty.clips, ())
        ET.fromstring(fcp7_xml(empty))
        ET.fromstring(fcpxml(empty))
        bad = dict(PLAN_EJEMPLO)
        bad["edl"] = list(reversed(PLAN_EJEMPLO["edl"]))
        with self.assertRaisesRegex(ValueError, "orden temporal"):
            load_timeline(bad)

    def test_cli_exporta_los_tres_formatos_solo_con_stdlib(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            plan = folder / "plan_ejemplo.json"
            output = folder / "export"
            plan.write_text(json.dumps(PLAN_EJEMPLO, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(root / "bin" / "nle_export.py"), str(plan), str(output)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = [
                output / "premiere-resolve.xml",
                output / "final-cut.fcpxml",
                output / "capcut" / "draft_content.json",
                output / "capcut" / "draft_meta_info.json",
            ]
            self.assertTrue(all(path.is_file() for path in expected))
            ET.parse(expected[0])
            ET.parse(expected[1])
            self.assertEqual(len(json.loads(expected[2].read_text(encoding="utf-8"))["tracks"][0]["segments"]), 3)


if __name__ == "__main__":
    unittest.main()
