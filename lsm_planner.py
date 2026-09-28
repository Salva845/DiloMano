"""Planificador extensible de español a glosas LSM validadas.

El fallback preserva el orden léxico para mantener compatibilidad. Las reglas
de reordenamiento solo se aplican cuando están declaradas en ``lsm_rules.json``;
esto evita convertir generalizaciones no validadas en una traducción falsa.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence

from asset_catalog import normalize_text
from config import BASE_DIR


@dataclass(frozen=True, slots=True)
class ValidatedSentenceRule:
    source: str
    glosses: tuple[str, ...]
    region: str = "general"
    reviewed_by: str = ""


class LSMPlanner:
    def __init__(self, rules_path: Path | None = None) -> None:
        self.rules_path = rules_path or BASE_DIR / "lsm_rules.json"
        self._sentence_rules: dict[str, ValidatedSentenceRule] = {}
        self._load()

    def _load(self) -> None:
        if not self.rules_path.is_file():
            return
        try:
            payload = json.loads(self.rules_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for item in payload.get("validated_sentence_templates", []):
            source = normalize_text(str(item.get("source", "")))
            glosses = tuple(
                normalize_text(str(gloss))
                for gloss in item.get("glosses", [])
                if normalize_text(str(gloss))
            )
            reviewed_by = str(item.get("reviewed_by", "")).strip()
            if not source or not glosses or not reviewed_by:
                continue
            self._sentence_rules[source] = ValidatedSentenceRule(
                source=source,
                glosses=glosses,
                region=str(item.get("region", "general")),
                reviewed_by=reviewed_by,
            )

    def plan_validated_sentence(self, text: str) -> tuple[str, ...] | None:
        rule = self._sentence_rules.get(normalize_text(text))
        return rule.glosses if rule is not None else None

    def order_lexical_tokens(self, tokens: Sequence[str]) -> tuple[str, ...]:
        """Fallback explícito: aún no afirma realizar gramática completa LSM."""
        return tuple(normalize_text(token) for token in tokens if normalize_text(token))

    @property
    def validated_rule_count(self) -> int:
        return len(self._sentence_rules)

