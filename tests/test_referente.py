import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from referente import cita_corta, ficha_desde_entradas, parsear_transcripcion


class ReferenteTest(unittest.TestCase):
    def test_parsea_marcas_y_limita_citas(self):
        texto = "[00:00] Abrimos con una pregunta sencilla\n[00:35] Y aquí llega la respuesta completa"
        entradas = parsear_transcripcion(texto)
        self.assertEqual([e["inicio"] for e in entradas], [0.0, 35.0])
        cita = cita_corta("uno dos tres cuatro cinco seis", 4)
        self.assertEqual(cita, "uno dos tres cuatro")

    def test_ficha_abre_con_fuente_y_fecha(self):
        ficha = ficha_desde_entradas(
            [{"inicio": 0.0, "texto": "Abrimos en acción"}, {"inicio": 50.0, "texto": "¿Qué cambia ahora?"}],
            url="https://www.youtube.com/watch?v=abc123",
            titulo="Ejemplo",
            formato="entrevista",
            fecha="2026-10-20",
        )
        self.assertTrue(ficha.startswith("Fuente: https://www.youtube.com/watch?v=abc123 · Fecha: 2026-10-20"))
        self.assertIn("## Bucles y pagos", ficha)


if __name__ == "__main__":
    unittest.main()

