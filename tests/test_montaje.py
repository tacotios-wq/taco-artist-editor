import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from buscar import resolver
from montar import construir_plan, verificar_bordes


class MontajeTest(unittest.TestCase):
    def setUp(self):
        self.palabras = [
            {"texto": "Hoy", "inicio": 1.0, "fin": 1.2},
            {"texto": "cocinamos", "inicio": 1.21, "fin": 1.7},
            {"texto": "juntos", "inicio": 1.71, "fin": 2.0},
            {"texto": "Sale", "inicio": 3.0, "fin": 3.2},
            {"texto": "bien", "inicio": 3.21, "fin": 3.5},
        ]

    def test_resuelve_bordes_por_palabra(self):
        cortes = resolver(
            self.palabras,
            [{"id": "c1", "bloque": "inicio", "desde": "hoy", "hasta": "juntos"}],
        )
        self.assertEqual(cortes[0]["master_in"], 1.0)
        self.assertEqual(cortes[0]["master_out"], 2.0)

    def test_plan_separa_bloques(self):
        cortes = [
            {"id": "a", "bloque": "uno", "master_in": 1.0, "master_out": 2.0, "texto": "Hoy cocinamos"},
            {"id": "b", "bloque": "dos", "master_in": 3.0, "master_out": 3.5, "texto": "Sale bien"},
        ]
        piezas, edl, total = construir_plan(cortes)
        self.assertEqual(piezas[1], ("silencio", 0.7))
        self.assertEqual(edl[1]["montaje_in"], 1.7)
        self.assertAlmostEqual(total, 3.2)

    def test_verificacion_exige_primera_y_ultima(self):
        edl = [{"id": "a", "montaje_in": 0.0, "montaje_out": 1.0, "texto": "Hoy cocinamos"}]
        bien = [
            {"texto": "Hoy", "inicio": 0.0, "fin": 0.2},
            {"texto": "cocinamos", "inicio": 0.3, "fin": 0.9},
        ]
        mal = [
            {"texto": "Ahora", "inicio": 0.0, "fin": 0.2},
            {"texto": "cocinamos", "inicio": 0.3, "fin": 0.9},
        ]
        self.assertTrue(verificar_bordes(edl, bien)["pasa"])
        self.assertFalse(verificar_bordes(edl, mal)["pasa"])


if __name__ == "__main__":
    unittest.main()

