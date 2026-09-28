from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from asset_catalog import AssetCatalog
from config import NLPConfig
from events import TranscriptEvent, WordToken
from translator import Translator


def event(
    utterance: str,
    text: str,
    words: tuple[WordToken, ...],
    *,
    final: bool,
) -> TranscriptEvent:
    return TranscriptEvent(
        utterance_id=utterance,
        text=text,
        full_text=text,
        words=words,
        start_index=words[0].index if words else 0,
        is_final=final,
    )


class TranslatorTests(unittest.TestCase):
    def _translator(self, base: Path) -> Translator:
        signs = base / "senas"
        signs.mkdir()
        for filename in (
            "hola.mp4",
            "no.mp4",
            "porque.mp4",
            "A.mp4",
            "B.mp4",
            "C.mp4",
        ):
            (signs / filename).touch()
        catalog = AssetCatalog(
            {
                "hola": "senas/hola.mp4",
                "no": "senas/no.mp4",
                "por que": "senas/porque.mp4",
            },
            base_dir=base,
        )
        return Translator(
            catalog=catalog,
            config=NLPConfig(enable_stanza=False, spell_unknown_words=True),
        )

    def test_translates_short_word_without_stanza(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            translator = self._translator(Path(directory))
            plan = translator.translate_event(
                event("u1", "no", (WordToken("no", 0),), final=True)
            )
            self.assertEqual([item.gloss for item in plan.items], ["no"])
            self.assertFalse(translator.lemmatizer.cache_info()["attempted"])

    def test_holds_prefix_until_multiword_phrase_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            translator = self._translator(Path(directory))
            first = translator.translate_event(
                event("u2", "por", (WordToken("por", 0),), final=False)
            )
            self.assertEqual(first.items, ())
            second = TranscriptEvent(
                utterance_id="u2",
                text="que",
                full_text="por que",
                words=(WordToken("que", 1),),
                start_index=1,
                is_final=True,
            )
            plan = translator.translate_event(second)
            self.assertEqual([item.gloss for item in plan.items], ["por que"])
            self.assertEqual(plan.items[0].start_index, 0)
            self.assertEqual(plan.items[0].end_index, 2)

    def test_unknown_word_is_not_partially_spelled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            translator = self._translator(Path(directory))
            plan = translator.translate_event(
                event("u3", "abz", (WordToken("abz", 0),), final=True)
            )
            # No existe Z; no se produce una palabra incompleta.
            self.assertEqual(plan.items, ())

    def test_spelling_keeps_the_complete_word_for_subtitles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            translator = self._translator(Path(directory))
            plan = translator.translate_event(
                event("u4", "abc", (WordToken("abc", 0),), final=True)
            )
            self.assertEqual(len(plan.items), 3)
            self.assertEqual([item.source_text for item in plan.items], ["abc"] * 3)


if __name__ == "__main__":
    unittest.main()
