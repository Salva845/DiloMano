from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from asset_catalog import AssetCatalog, normalize_text


class AssetCatalogTests(unittest.TestCase):
    def test_normalization_is_shared_by_keys_and_queries(self) -> None:
        self.assertEqual(normalize_text("  ¿NIÑO?  "), "nino")

    def test_validates_paths_and_matches_longest_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            signs = base / "senas"
            signs.mkdir()
            (signs / "dolor.mp4").touch()
            (signs / "cabeza.mp4").touch()
            (signs / "frase.mp4").touch()
            (signs / "A.mp4").touch()
            catalog = AssetCatalog(
                {
                    "dolor": "senas/dolor.mp4",
                    "cabeza": "senas/cabeza.mp4",
                    "dolor de cabeza": "senas/frase.mp4",
                    "rota": "senas/no-existe.mp4",
                },
                base_dir=base,
            )

            entry, size = catalog.longest_match(["dolor", "de", "cabeza"])
            self.assertEqual(size, 3)
            self.assertEqual(entry.key, "dolor de cabeza")
            self.assertIsNotNone(catalog.lookup_letter("a"))
            self.assertEqual(catalog.report()["missing_entries"], 1)


if __name__ == "__main__":
    unittest.main()
