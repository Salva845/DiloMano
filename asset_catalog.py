"""Catálogo normalizado y validado de glosas y videos."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import unicodedata
from typing import Iterable, Mapping

from config import BASE_DIR
from diccionario import diccionario_senas


_NON_WORD_RE = re.compile(r"[^a-z0-9\s]", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


@lru_cache(maxsize=8_000)
def normalize_text(text: str) -> str:
    """Produce la misma clave para ASR, aliases y catálogo."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text.casefold().strip())
    without_marks = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    without_punctuation = _NON_WORD_RE.sub(" ", without_marks)
    return _SPACE_RE.sub(" ", without_punctuation).strip()


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    key: str
    source_key: str
    video_path: Path


class AssetCatalog:
    def __init__(
        self,
        mapping: Mapping[str, str] | None = None,
        base_dir: Path = BASE_DIR,
    ) -> None:
        self.base_dir = Path(base_dir).resolve()
        self._raw_mapping = dict(diccionario_senas if mapping is None else mapping)
        self._entries: dict[str, CatalogEntry] = {}
        self._letters: dict[str, CatalogEntry] = {}
        self._missing: dict[str, Path] = {}
        self._collisions: dict[str, list[str]] = {}
        self._phrase_prefixes: set[str] = set()
        self._max_phrase_words = 1
        self._build()

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = self.base_dir / path
        return path.resolve()

    def _build(self) -> None:
        sources_by_normalized: dict[str, list[str]] = {}
        for source_key, raw_path in self._raw_mapping.items():
            key = normalize_text(source_key)
            if not key:
                continue
            path = self._resolve(raw_path)
            sources_by_normalized.setdefault(key, []).append(source_key)
            if not path.is_file():
                self._missing[source_key] = path
                continue
            self._entries[key] = CatalogEntry(key, source_key, path)
            self._max_phrase_words = max(self._max_phrase_words, len(key.split()))
            parts = key.split()
            for size in range(1, len(parts)):
                self._phrase_prefixes.add(" ".join(parts[:size]))

        self._collisions = {
            key: sources
            for key, sources in sources_by_normalized.items()
            if len(sources) > 1
        }
        self._load_letter_assets()

    def _load_letter_assets(self) -> None:
        signs_dir = self.base_dir / "senas"
        if not signs_dir.is_dir():
            return
        for path in signs_dir.glob("*.mp4"):
            stem = path.stem
            if (len(stem) != 1 and stem.casefold() != "rr") or not stem.isalpha():
                continue
            letter = normalize_text(stem)
            self._letters[letter] = CatalogEntry(
                key=f"letter:{letter}",
                source_key=stem,
                video_path=path.resolve(),
            )

    def lookup(self, text: str) -> CatalogEntry | None:
        return self._entries.get(normalize_text(text))

    def lookup_letter(self, letter: str) -> CatalogEntry | None:
        return self._letters.get(normalize_text(letter))

    def is_phrase_prefix(self, tokens: Iterable[str]) -> bool:
        key = " ".join(normalize_text(token) for token in tokens)
        return key in self._phrase_prefixes

    def longest_match(
        self,
        tokens: Iterable[str],
        start: int = 0,
    ) -> tuple[CatalogEntry | None, int]:
        normalized = [normalize_text(token) for token in tokens]
        if start >= len(normalized):
            return None, 0
        max_size = min(self._max_phrase_words, len(normalized) - start)
        for size in range(max_size, 0, -1):
            key = " ".join(normalized[start : start + size])
            entry = self._entries.get(key)
            if entry is not None:
                return entry, size
        return None, 0

    @property
    def max_phrase_words(self) -> int:
        return self._max_phrase_words

    @property
    def valid_entries(self) -> Mapping[str, CatalogEntry]:
        return self._entries

    def report(self) -> dict[str, object]:
        video_dir = self.base_dir / "senas"
        disk_videos = {path.resolve() for path in video_dir.glob("*.mp4")}
        mapped_videos = {
            entry.video_path for entry in (*self._entries.values(), *self._letters.values())
        }
        return {
            "declared_entries": len(self._raw_mapping),
            "valid_entries": len(self._entries),
            "missing_entries": len(self._missing),
            "missing": {key: str(path) for key, path in self._missing.items()},
            "normalization_collisions": self._collisions,
            "letter_assets": sorted(self._letters),
            "unmapped_video_files": sorted(str(path) for path in disk_videos - mapped_videos),
        }


default_catalog = AssetCatalog()
