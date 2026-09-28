"""Contratos de datos compartidos por el pipeline en tiempo real."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic_ns
from typing import Tuple


@dataclass(frozen=True, slots=True)
class WordToken:
    """Una palabra reconocida con su posición dentro de la emisión."""

    text: str
    index: int
    start: float | None = None
    end: float | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    """Delta estable de una hipótesis de reconocimiento.

    ``text`` contiene únicamente el fragmento nuevo o corregido. ``full_text``
    conserva la hipótesis completa para mostrarla y para procesamiento con
    contexto. Si ``revision_from`` no es ``None``, cualquier resultado aún no
    reproducido desde ese índice puede sustituirse.
    """

    utterance_id: str
    text: str
    full_text: str
    words: Tuple[WordToken, ...]
    start_index: int
    is_final: bool
    revision_from: int | None = None
    created_ns: int = field(default_factory=monotonic_ns)


@dataclass(frozen=True, slots=True)
class SignItem:
    """Una glosa resuelta a un asset visual."""

    gloss: str
    source_text: str
    video_path: Path
    utterance_id: str
    start_index: int
    end_index: int
    provisional: bool = False
    estimated_duration: float = 0.8
    source_event_ns: int = field(default_factory=monotonic_ns)


@dataclass(frozen=True, slots=True)
class SignPlan:
    """Plan visual ordenado producido por el traductor."""

    utterance_id: str
    source_text: str
    items: Tuple[SignItem, ...]
    is_final: bool
    revision_from: int | None = None
    created_ns: int = field(default_factory=monotonic_ns)
