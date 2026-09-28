from pathlib import Path
import unittest

from config import VideoConfig
from events import SignItem
from video_player import VideoPlayer


class SubtitleTests(unittest.TestCase):
    @staticmethod
    def _player(**config_overrides) -> VideoPlayer:
        player = object.__new__(VideoPlayer)
        player.config = VideoConfig(**config_overrides)
        return player

    @staticmethod
    def _item(source_text: str, start: int, end: int) -> SignItem:
        return SignItem(
            gloss="hola",
            source_text=source_text,
            video_path=Path("hola.mp4"),
            utterance_id="test",
            start_index=start,
            end_index=end,
            provisional=False,
        )

    def test_word_and_sentence_position_are_shown(self) -> None:
        player = self._player()
        self.assertEqual(
            player._subtitle_text(self._item("hola", 2, 3)),
            "hola  ·  palabra 3",
        )

    def test_multiword_sign_uses_a_position_range(self) -> None:
        player = self._player()
        self.assertEqual(
            player._subtitle_text(self._item("por que", 0, 2)),
            "por que  ·  palabras 1-2",
        )

    def test_position_can_be_hidden(self) -> None:
        player = self._player(subtitle_show_position=False)
        self.assertEqual(player._subtitle_text(self._item("hola", 0, 1)), "hola")


if __name__ == "__main__":
    unittest.main()
