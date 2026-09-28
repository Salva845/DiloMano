from __future__ import annotations

import unittest

from hypothesis_stabilizer import HypothesisStabilizer


class HypothesisStabilizerTests(unittest.TestCase):
    def test_emits_stable_short_words_and_final_suffix(self) -> None:
        stabilizer = HypothesisStabilizer(stability_updates=2)
        self.assertIsNone(stabilizer.accept_partial("yo no"))
        stable = stabilizer.accept_partial("yo no")
        self.assertIsNotNone(stable)
        self.assertEqual(stable.text, "yo no")
        self.assertEqual([word.index for word in stable.words], [0, 1])

        final = stabilizer.accept_final("yo no quiero")
        self.assertIsNotNone(final)
        self.assertTrue(final.is_final)
        self.assertEqual(final.text, "quiero")
        self.assertEqual(final.start_index, 2)

    def test_preserves_repeated_words_by_position(self) -> None:
        stabilizer = HypothesisStabilizer(stability_updates=2)
        stabilizer.accept_partial("no no")
        event = stabilizer.accept_partial("no no")
        self.assertEqual([word.text for word in event.words], ["no", "no"])
        self.assertEqual([word.index for word in event.words], [0, 1])

    def test_reports_revision_of_committed_suffix(self) -> None:
        stabilizer = HypothesisStabilizer(stability_updates=2)
        stabilizer.accept_partial("quiero casa")
        stabilizer.accept_partial("quiero casa")
        revision = stabilizer.accept_partial("quiero cazar")
        self.assertEqual(revision.revision_from, 1)
        self.assertEqual(revision.start_index, 1)
        self.assertEqual(revision.text, "")

        replacement = stabilizer.accept_partial("quiero cazar")
        self.assertIsNone(replacement.revision_from)
        self.assertEqual(replacement.text, "cazar")

    def test_empty_final_closes_existing_utterance_without_duplicate(self) -> None:
        stabilizer = HypothesisStabilizer(stability_updates=2)
        stabilizer.accept_partial("hola")
        stabilizer.accept_partial("hola")
        final = stabilizer.accept_final("")
        self.assertTrue(final.is_final)
        self.assertEqual(final.text, "")
        self.assertEqual(final.words, ())


if __name__ == "__main__":
    unittest.main()
