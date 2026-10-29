"""Casos portados de subtitles y subtitle-cues de OpenFilm.

Origen: packages/openfilm/studio/ui/src/lib/{subtitles,subtitle-cues}.test.ts
y packages/openfilm/studio/server/transcripts.test.mjs, commit de5a98b, licencia MIT.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from vtt import cues_to_words, milliseconds, timestamp, vtt_dumps, vtt_loads, words_to_cues


PALABRAS_EJEMPLO = {
    "palabras": [
        {"texto": "Hola", "inicio": 0.1, "fin": 0.35},
        {"texto": "mundo.", "inicio": 0.5, "fin": 0.9},
        {"texto": "Otra", "inicio": 1.8, "fin": 2.05},
        {"texto": "línea", "inicio": 2.1, "fin": 2.4},
        {"texto": "aquí.", "inicio": 2.45, "fin": 2.8},
    ]
}


class VttTest(unittest.TestCase):
    def test_timestamp_acepta_horas_y_rechaza_formato_invalido(self):
        self.assertEqual(timestamp(3_723_004), "01:02:03.004")
        self.assertEqual(milliseconds("01:02:03.004"), 3_723_004)
        self.assertEqual(milliseconds("02:03.004"), 123_004)
        with self.assertRaises(ValueError):
            milliseconds("1:2:3")

    def test_palabras_se_agrupan_por_pausa_y_conservan_marcas(self):
        cues = words_to_cues(PALABRAS_EJEMPLO)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["text"], "Hola mundo.")
        self.assertEqual(cues[0]["marks"], [{"index": 0, "startMs": 100}, {"index": 5, "startMs": 500}])
        self.assertEqual(cues[1]["startMs"], 1800)

    def test_ida_y_vuelta_vtt_con_tiempo_por_palabra_y_voz(self):
        cues = words_to_cues(PALABRAS_EJEMPLO)
        body = vtt_dumps(cues, speaker="Ann & Bo")
        self.assertTrue(body.startswith("WEBVTT\n\n"))
        self.assertIn("Hola <00:00:00.500>mundo.", body)
        self.assertIn("<v Ann &amp; Bo>", body)
        parsed = vtt_loads(body)
        self.assertEqual(parsed["speaker"], "Ann & Bo")
        self.assertEqual(parsed["cues"], cues)
        words = cues_to_words(parsed["cues"])
        self.assertEqual([word["texto"] for word in words], [word["texto"] for word in PALABRAS_EJEMPLO["palabras"]])
        self.assertEqual([word["inicio"] for word in words], [word["inicio"] for word in PALABRAS_EJEMPLO["palabras"]])
        self.assertEqual([word["fin_estimado"] for word in words], [True, False, True, True, False])
        self.assertEqual(words[0]["fin"], words[1]["inicio"])
        self.assertEqual(words[2]["fin"], words[3]["inicio"])
        self.assertEqual(words[3]["fin"], words[4]["inicio"])
        self.assertEqual(words[1]["fin"], PALABRAS_EJEMPLO["palabras"][1]["fin"])
        self.assertEqual(words[-1]["fin"], PALABRAS_EJEMPLO["palabras"][-1]["fin"])
        self.assertFalse(words[-1]["fin_estimado"])

    def test_lector_admite_identificador_estilos_y_lineas_multiples(self):
        body = """WEBVTT

cue-1
00:00:00.100 --> 00:00:01.000 align:start
<v Ann><b>Hola</b> <00:00:00.500>allí
segunda línea
"""
        parsed = vtt_loads(body)
        self.assertEqual(parsed["speaker"], "Ann")
        self.assertEqual(parsed["cues"][0]["text"], "Hola allí segunda línea")
        self.assertEqual(parsed["cues"][0]["marks"], [{"index": 0, "startMs": 100}, {"index": 5, "startMs": 500}])

    def test_palabra_sin_tiempo_falla_con_indice(self):
        with self.assertRaisesRegex(ValueError, "palabra 1 sin tiempo"):
            words_to_cues({"palabras": [{"texto": "Hola"}]})

    def test_cli_escribe_y_lee_webvtt(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "palabras.json"
            vtt = folder / "subtitulos.vtt"
            restored = folder / "restauradas.json"
            source.write_text(json.dumps(PALABRAS_EJEMPLO, ensure_ascii=False), encoding="utf-8")
            write = subprocess.run(
                [sys.executable, str(root / "bin" / "vtt.py"), "escribir", str(source), str(vtt)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(write.returncode, 0, write.stderr)
            read = subprocess.run(
                [sys.executable, str(root / "bin" / "vtt.py"), "leer", str(vtt), str(restored)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(read.returncode, 0, read.stderr)
            words = json.loads(restored.read_text(encoding="utf-8"))["palabras"]
            self.assertEqual([word["texto"] for word in words], [word["texto"] for word in PALABRAS_EJEMPLO["palabras"]])
            self.assertEqual([word["fin_estimado"] for word in words], [True, False, True, True, False])


if __name__ == "__main__":
    unittest.main()
