import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from ta_core import segundos, timecode
from transcribir import elegir_idioma, plan_frases, puntos_silencio


class TranscripcionTest(unittest.TestCase):
    def test_parsea_silencios_y_plan_limita_duracion(self):
        log = "silence_start: 4.0\nsilence_end: 5.0\nsilence_start: 29.0\nsilence_end: 31.0\n"
        cortes = puntos_silencio(log)
        self.assertEqual(cortes, [4.5, 30.0])
        plan = plan_frases(40.0, cortes, minimo=0.6, maximo=10.0)
        self.assertEqual(plan[0][0], 0.0)
        self.assertEqual(plan[-1][1], 40.0)
        self.assertTrue(all(fin - inicio <= 10.01 for inicio, fin in plan))

    def test_idioma_se_decide_por_frase(self):
        self.assertEqual(elegir_idioma({"es": 0.7, "en": 0.2}), ("es", 0.7))
        self.assertEqual(elegir_idioma({"es": 0.1, "en": 0.8}), ("en", 0.8))

    def test_timecodes(self):
        self.assertAlmostEqual(segundos("01:02:03.5"), 3723.5)
        self.assertEqual(timecode(3723.5), "01:02:03.500")


if __name__ == "__main__":
    unittest.main()

