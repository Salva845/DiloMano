"""Convierte hipótesis ASR revisables en deltas estables y cancelables."""

from __future__ import annotations

from collections import deque
from itertools import count
from typing import Iterable, Mapping, Sequence

from events import TranscriptEvent, WordToken


def _canonical(token: str) -> str:
    return token.casefold().strip()


def _common_prefix_length(sequences: Sequence[Sequence[WordToken]]) -> int:
    if not sequences:
        return 0
    limit = min(len(sequence) for sequence in sequences)
    for index in range(limit):
        expected = _canonical(sequences[0][index].text)
        if any(_canonical(sequence[index].text) != expected for sequence in sequences[1:]):
            return index
    return limit


def _prefix_between(left: Sequence[WordToken], right: Sequence[WordToken]) -> int:
    return _common_prefix_length((left, right))


class HypothesisStabilizer:
    """Confirma el prefijo común de varias hipótesis consecutivas.

    Los resultados parciales de un ASR pueden reescribir palabras previas. Este
    objeto emite solamente el prefijo que ha permanecido estable y comunica las
    revisiones para retirar elementos que todavía estén pendientes en video.
    """

    def __init__(self, stability_updates: int = 2) -> None:
        if stability_updates < 2:
            raise ValueError("stability_updates debe ser al menos 2")
        self.stability_updates = stability_updates
        self._history: deque[tuple[WordToken, ...]] = deque(maxlen=stability_updates)
        self._committed: tuple[WordToken, ...] = ()
        self._utterances = count(1)
        self._utterance_id = self._next_utterance_id()

    def _next_utterance_id(self) -> str:
        return f"utt-{next(self._utterances):08d}"

    @staticmethod
    def _tokens(
        text: str,
        word_data: Iterable[Mapping[str, object]] | None,
    ) -> tuple[WordToken, ...]:
        data = list(word_data or ())
        if data:
            tokens: list[WordToken] = []
            for index, item in enumerate(data):
                word = str(item.get("word", "")).strip()
                if not word:
                    continue
                confidence = item.get("conf")
                tokens.append(
                    WordToken(
                        text=word,
                        index=len(tokens),
                        start=float(item["start"]) if item.get("start") is not None else None,
                        end=float(item["end"]) if item.get("end") is not None else None,
                        confidence=float(confidence) if confidence is not None else None,
                    )
                )
            if tokens:
                return tuple(tokens)
        return tuple(
            WordToken(text=word, index=index)
            for index, word in enumerate(text.split())
            if word
        )

    def accept_partial(
        self,
        text: str,
        word_data: Iterable[Mapping[str, object]] | None = None,
    ) -> TranscriptEvent | None:
        tokens = self._tokens(text, word_data)
        if not tokens:
            return None
        self._history.append(tokens)
        if len(self._history) < self.stability_updates:
            return None

        stable_count = _common_prefix_length(tuple(self._history))
        stable = tokens[:stable_count]
        common_with_committed = _prefix_between(self._committed, stable)
        if stable == self._committed:
            return None

        revision_from = (
            common_with_committed
            if common_with_committed < len(self._committed)
            else None
        )
        delta = stable[common_with_committed:]
        self._committed = stable
        return TranscriptEvent(
            utterance_id=self._utterance_id,
            text=" ".join(token.text for token in delta),
            full_text=" ".join(token.text for token in tokens),
            words=tuple(
                WordToken(
                    text=token.text,
                    index=index,
                    start=token.start,
                    end=token.end,
                    confidence=token.confidence,
                )
                for index, token in enumerate(delta, start=common_with_committed)
            ),
            start_index=common_with_committed,
            is_final=False,
            revision_from=revision_from,
        )

    def accept_final(
        self,
        text: str,
        word_data: Iterable[Mapping[str, object]] | None = None,
    ) -> TranscriptEvent | None:
        final_tokens = self._tokens(text, word_data)
        if not final_tokens and not self._committed:
            self.reset()
            return None

        if not final_tokens:
            final_tokens = self._committed
        common = _prefix_between(self._committed, final_tokens)
        revision_from = common if common < len(self._committed) else None
        delta = final_tokens[common:]
        event = TranscriptEvent(
            utterance_id=self._utterance_id,
            text=" ".join(token.text for token in delta),
            full_text=" ".join(token.text for token in final_tokens),
            words=tuple(
                WordToken(
                    text=token.text,
                    index=index,
                    start=token.start,
                    end=token.end,
                    confidence=token.confidence,
                )
                for index, token in enumerate(delta, start=common)
            ),
            start_index=common,
            is_final=True,
            revision_from=revision_from,
        )
        self.reset()
        return event

    def reset(self) -> None:
        self._history.clear()
        self._committed = ()
        self._utterance_id = self._next_utterance_id()

    def abort(self) -> None:
        """Descarta la emisión actual después de pérdida o corte de audio."""
        self.reset()

    @property
    def committed_text(self) -> str:
        return " ".join(token.text for token in self._committed)
