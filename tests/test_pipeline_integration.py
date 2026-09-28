from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from asset_catalog import AssetCatalog
from config import NLPConfig
from hypothesis_stabilizer import HypothesisStabilizer
from translator import Translator


class PipelineIntegrationTests(unittest.TestCase):
    def test_stable_asr_delta_reaches_sign_plan_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            signs = base / "senas"
            signs.mkdir()
            (signs / "hola.mp4").touch()
            (signs / "yo.mp4").touch()
            catalog = AssetCatalog(
                {"hola": "senas/hola.mp4", "yo": "senas/yo.mp4"},
                base_dir=base,
            )
            translator = Translator(
                catalog=catalog,
                config=NLPConfig(enable_stanza=False, spell_unknown_words=False),
            )
            stabilizer = HypothesisStabilizer(stability_updates=2)

            self.assertIsNone(stabilizer.accept_partial("hola yo"))
            stable = stabilizer.accept_partial("hola yo")
            plan = translator.translate_event(stable)
            self.assertEqual([item.gloss for item in plan.items], ["hola", "yo"])

            final = stabilizer.accept_final("hola yo")
            final_plan = translator.translate_event(final)
            self.assertEqual(final_plan.items, ())
            self.assertTrue(final_plan.is_final)


if __name__ == "__main__":
    unittest.main()
