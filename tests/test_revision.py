import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from revisar_corte import analizar_corte


class RevisionTest(unittest.TestCase):
    def test_detecta_bucle_sin_pago_y_modo_generico(self):
        datos = {
            "clips": [
                {"in": 0, "out": 1, "texto": "Empieza", "abre_bucle": "respuesta"},
                {"in": 2.8, "out": 3.0, "texto": "Termina"},
            ]
        }
        resultado = analizar_corte(datos, False)
        detalles = " ".join(n["detalle"] for n in resultado["notas"])
        self.assertIn("no obtiene pago", detalles)
        self.assertIn("modo genérico", detalles)
        self.assertIn("silencio", detalles)


if __name__ == "__main__":
    unittest.main()

