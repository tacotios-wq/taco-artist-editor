import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from motor import agrupar_golpes, ass_desde_plan
from qa_subtitulos import validar_plan
from ta_core import cargar_json


class SubtitulosTest(unittest.TestCase):
    def setUp(self):
        self.preset = cargar_json(Path(__file__).resolve().parents[1] / "sync" / "preset_subtitulos.json")
        self.palabras = [
            {"texto": "Esta", "inicio": 0.0, "fin": 0.2},
            {"texto": "es", "inicio": 0.21, "fin": 0.32},
            {"texto": "la", "inicio": 0.33, "fin": 0.42},
            {"texto": "primera", "inicio": 0.43, "fin": 0.7},
            {"texto": "frase", "inicio": 0.71, "fin": 1.0},
            {"texto": "Cambia", "inicio": 1.6, "fin": 1.9},
            {"texto": "ahora", "inicio": 1.91, "fin": 2.2},
        ]

    def test_golpes_respetan_pausa_y_reveal(self):
        golpes = agrupar_golpes(self.palabras, self.preset)
        self.assertEqual(len(golpes), 2)
        self.assertEqual(golpes[0]["modo"], "hook")
        self.assertEqual(len(golpes[0]["eventos"]), len(golpes[0]["palabras"]))

    def test_qa_falla_cerrado_hasta_revision_visual(self):
        plan = {"golpes": agrupar_golpes(self.palabras, self.preset)}
        pendiente = validar_plan(plan, self.palabras, self.preset, False)
        aprobado = validar_plan(plan, self.palabras, self.preset, True)
        self.assertFalse(pendiente["pasa"])
        self.assertTrue(aprobado["pasa"])

    def test_ass_contiene_un_evento_por_palabra(self):
        plan = {"golpes": agrupar_golpes(self.palabras, self.preset)}
        ass = ass_desde_plan(plan, self.preset)
        self.assertEqual(ass.count("Dialogue:"), len(self.palabras))


if __name__ == "__main__":
    unittest.main()

