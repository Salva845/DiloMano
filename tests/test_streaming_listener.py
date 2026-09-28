from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from config import AudioConfig
from streaming_listener import StreamingListener


class StreamingListenerTests(unittest.TestCase):
    def test_overflow_does_not_splice_new_audio_into_old_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = AudioConfig(
                model_path=Path(directory),
                queue_blocks=1,
                block_size=1600,
            )
            listener = StreamingListener(lambda event: None, config=config)
            listener._running.set()
            listener._callback_audio(b"old", 1, None, None)
            listener._callback_audio(b"new", 1, None, None)

            self.assertEqual(listener._audio_queue.get_nowait(), b"old")
            self.assertTrue(listener._overflowed.is_set())
            self.assertEqual(listener.get_stats()["audio_overflows"], 1)


if __name__ == "__main__":
    unittest.main()
