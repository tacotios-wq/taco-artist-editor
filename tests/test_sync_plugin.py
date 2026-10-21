import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from sync_semanal import plan_seco, validar_allowlist
from ta_core import cargar_json


class SyncYPluginTest(unittest.TestCase):
    def test_allowlist_es_explicita(self):
        fuentes = validar_allowlist(cargar_json(ROOT / "sync" / "ALLOWLIST.yaml"))
        self.assertGreaterEqual(len(fuentes), 10)
        self.assertTrue(all(f["origen"].startswith("~") for f in fuentes))
        self.assertTrue(all(f["forma"] in {"CODIGO", "DESTILADO", "FUERA"} for f in fuentes))

    def test_plan_seco_es_determinista(self):
        self.assertEqual(plan_seco(ROOT), plan_seco(ROOT))
        self.assertFalse(plan_seco(ROOT)["escrituras"])

    def test_manifests_y_cinco_skills(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(plugin["name"], "taco-artist-editor")
        self.assertEqual(market["plugins"][0]["source"], "./")
        skills = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
        self.assertEqual(len(skills), 5)
        for nombre in skills:
            texto = (ROOT / "skills" / nombre / "SKILL.md").read_text()
            self.assertIn(f"name: {nombre}", texto)
            self.assertIn("description:", texto)


if __name__ == "__main__":
    unittest.main()

