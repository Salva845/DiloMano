"""Traducción contextual, no bloqueante y compatible con el catálogo visual."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import queue
import threading
from typing import Callable, Sequence

from asset_catalog import AssetCatalog, default_catalog, normalize_text
from config import BASE_DIR, NLPConfig
from events import SignItem, SignPlan, TranscriptEvent, WordToken
from lsm_planner import LSMPlanner
from metrics import pipeline_metrics


normalizar = normalize_text


class StanzaLemmatizer:
    """Carga Stanza de forma perezosa y procesa fragmentos con contexto."""

    def __init__(self, enabled: bool = True, cache_size: int = 2_000) -> None:
        self.enabled = enabled
        self.cache_size = cache_size
        self._pipeline = None
        self._attempted = False
        self._error: str | None = None
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, tuple[str, ...]] = OrderedDict()

    def _ensure_pipeline(self) -> bool:
        if not self.enabled:
            return False
        if self._pipeline is not None:
            return True
        if self._attempted:
            return False
        with self._lock:
            if self._pipeline is not None:
                return True
            if self._attempted:
                return False
            self._attempted = True
            try:
                import stanza

                with pipeline_metrics.timer("stanza_load_ms"):
                    try:
                        self._pipeline = stanza.Pipeline(
                            lang="es",
                            processors="tokenize,mwt,pos,lemma",
                            use_gpu=False,
                            tokenize_no_ssplit=True,
                            logging_level="ERROR",
                            download_method=None,
                            verbose=False,
                        )
                    except Exception:
                        # Algunos paquetes antiguos no incluyen el procesador MWT.
                        self._pipeline = stanza.Pipeline(
                            lang="es",
                            processors="tokenize,pos,lemma",
                            use_gpu=False,
                            tokenize_no_ssplit=True,
                            logging_level="ERROR",
                            download_method=None,
                            verbose=False,
                        )
                return True
            except Exception as exc:
                self._error = str(exc)
                pipeline_metrics.increment("stanza_load_errors")
                self._pipeline = None
                return False

    def lemmatize(self, tokens: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(normalize_text(token) for token in tokens)
        cache_key = " ".join(normalized)
        if not cache_key:
            return ()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._cache.move_to_end(cache_key)
                pipeline_metrics.increment("lemma_cache_hits")
                return cached

        if not self._ensure_pipeline():
            return normalized

        try:
            with self._lock, pipeline_metrics.timer("stanza_inference_ms"):
                document = self._pipeline(" ".join(tokens))
            lemmas = tuple(
                normalize_text(word.lemma or word.text)
                for sentence in document.sentences
                for word in sentence.words
            )
            # Una expansión MWT puede cambiar la alineación. En streaming es
            # preferible conservar el token original a asignar una glosa errónea.
            if len(lemmas) != len(normalized):
                lemmas = normalized
        except Exception as exc:
            self._error = str(exc)
            pipeline_metrics.increment("stanza_inference_errors")
            lemmas = normalized

        with self._lock:
            self._cache[cache_key] = lemmas
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return lemmas

    @property
    def ready(self) -> bool:
        return self._pipeline is not None

    @property
    def error(self) -> str | None:
        return self._error

    def cache_info(self) -> dict[str, object]:
        with self._lock:
            return {
                "size": len(self._cache),
                "ready": self.ready,
                "attempted": self._attempted,
                "error": self._error,
            }


_legacy_lemmatizer = StanzaLemmatizer(enabled=True)


def obtener_raiz(palabra: str) -> str:
    lemmas = _legacy_lemmatizer.lemmatize((palabra,))
    return lemmas[0] if lemmas else normalize_text(palabra)


@dataclass(slots=True)
class _UtteranceBuffer:
    words: dict[int, WordToken]
    next_index: int = 0


class Translator:
    def __init__(
        self,
        catalog: AssetCatalog | None = None,
        config: NLPConfig | None = None,
        planner: LSMPlanner | None = None,
    ) -> None:
        self.catalog = catalog or default_catalog
        self.config = config or NLPConfig()
        self.planner = planner or LSMPlanner()
        self.lemmatizer = StanzaLemmatizer(enabled=self.config.enable_stanza)
        self._buffers: dict[str, _UtteranceBuffer] = {}

    def prewarm(self) -> bool:
        """Carga Stanza en segundo plano antes de necesitar una flexión."""
        return self.lemmatizer._ensure_pipeline()

    def _sign_item(
        self,
        *,
        entry,
        source_text: str,
        utterance_id: str,
        start_index: int,
        end_index: int,
        provisional: bool,
        source_event_ns: int,
    ) -> SignItem:
        return SignItem(
            gloss=entry.key,
            source_text=source_text,
            video_path=entry.video_path,
            utterance_id=utterance_id,
            start_index=start_index,
            end_index=end_index,
            provisional=provisional,
            source_event_ns=source_event_ns,
        )

    def _spell(
        self,
        token: str,
        utterance_id: str,
        index: int,
        provisional: bool,
        source_event_ns: int,
    ) -> list[SignItem]:
        normalized = normalize_text(token).replace(" ", "")
        if (
            not self.config.spell_unknown_words
            or not normalized
            or len(normalized) > self.config.max_spelling_letters
        ):
            return []
        items: list[SignItem] = []
        letters: list[str] = []
        cursor = 0
        while cursor < len(normalized):
            if normalized.startswith("rr", cursor) and self.catalog.lookup_letter("rr"):
                letters.append("rr")
                cursor += 2
            else:
                letters.append(normalized[cursor])
                cursor += 1
        for letter in letters:
            entry = self.catalog.lookup_letter(letter)
            if entry is None:
                pipeline_metrics.increment("missing_letter_assets")
                return []
            items.append(
                self._sign_item(
                    entry=entry,
                    # Mantener la palabra completa mientras se deletrea evita
                    # que el subtítulo parpadee letra por letra.
                    source_text=token,
                    utterance_id=utterance_id,
                    start_index=index,
                    end_index=index + 1,
                    provisional=provisional,
                    source_event_ns=source_event_ns,
                )
            )
        return items

    def _plan_validated_sentence(self, event: TranscriptEvent) -> SignPlan | None:
        if not event.is_final:
            return None
        glosses = self.planner.plan_validated_sentence(event.full_text)
        if glosses is None:
            return None
        items: list[SignItem] = []
        for index, gloss in enumerate(glosses):
            entry = self.catalog.lookup(gloss)
            if entry is None:
                pipeline_metrics.increment("validated_rule_missing_gloss")
                return None
            items.append(
                self._sign_item(
                    entry=entry,
                    source_text=gloss,
                    utterance_id=event.utterance_id,
                    start_index=index,
                    end_index=index + 1,
                    provisional=False,
                    source_event_ns=event.created_ns,
                )
            )
        return SignPlan(
            utterance_id=event.utterance_id,
            source_text=event.full_text,
            items=tuple(items),
            is_final=True,
            revision_from=0,
        )

    def translate_event(self, event: TranscriptEvent) -> SignPlan:
        """Traduce un delta estable manteniendo contexto por utterance."""
        with pipeline_metrics.timer("translation_total_ms"):
            validated = self._plan_validated_sentence(event)
            if validated is not None:
                self._buffers.pop(event.utterance_id, None)
                return validated

            buffer = self._buffers.setdefault(
                event.utterance_id,
                _UtteranceBuffer(words={}),
            )
            if event.revision_from is not None:
                for index in tuple(buffer.words):
                    if index >= event.revision_from:
                        del buffer.words[index]
                buffer.next_index = min(buffer.next_index, event.revision_from)

            for word in event.words:
                buffer.words[word.index] = word

            available: list[WordToken] = []
            index = buffer.next_index
            while index in buffer.words:
                available.append(buffer.words[index])
                index += 1

            source_tokens = [word.text for word in available]
            lemmas: tuple[str, ...] = ()
            lemmas_loaded = False
            items: list[SignItem] = []
            cursor = 0
            provisional = not event.is_final

            while cursor < len(source_tokens):
                remaining = source_tokens[cursor:]
                entry, size = self.catalog.longest_match(remaining)
                if entry is None and not lemmas_loaded:
                    lemmas = self.lemmatizer.lemmatize(source_tokens)
                    lemmas_loaded = True
                if entry is None and lemmas:
                    entry, size = self.catalog.longest_match(lemmas[cursor:])

                # Retener solo cuando el último token podría comenzar una frase
                # multipalabra. No agrega retraso a palabras que no son prefijo.
                if (
                    not event.is_final
                    and cursor == len(source_tokens) - 1
                    and self.catalog.is_phrase_prefix((source_tokens[cursor],))
                ):
                    break

                absolute_index = buffer.next_index + cursor
                if entry is not None:
                    phrase = " ".join(source_tokens[cursor : cursor + size])
                    items.append(
                        self._sign_item(
                            entry=entry,
                            source_text=phrase,
                            utterance_id=event.utterance_id,
                            start_index=absolute_index,
                            end_index=absolute_index + size,
                            provisional=provisional,
                            source_event_ns=event.created_ns,
                        )
                    )
                    cursor += size
                    continue

                spelled = self._spell(
                    source_tokens[cursor],
                    event.utterance_id,
                    absolute_index,
                    provisional,
                    event.created_ns,
                )
                if spelled:
                    items.extend(spelled)
                    pipeline_metrics.increment("spelled_words")
                else:
                    pipeline_metrics.increment("unresolved_words")
                cursor += 1

            buffer.next_index += cursor
            if event.is_final:
                self._buffers.pop(event.utterance_id, None)

            return SignPlan(
                utterance_id=event.utterance_id,
                source_text=event.full_text,
                items=tuple(items),
                is_final=event.is_final,
                revision_from=event.revision_from,
            )

    def traducir(self, frase: str) -> list[str]:
        """API compatible para pruebas y llamadas no streaming."""
        tokens = tuple(
            WordToken(text=word, index=index)
            for index, word in enumerate(frase.split())
        )
        event = TranscriptEvent(
            utterance_id=f"manual-{id(tokens)}",
            text=frase,
            full_text=frase,
            words=tokens,
            start_index=0,
            is_final=True,
        )
        return [str(item.video_path) for item in self.translate_event(event).items]

    def verificar_stanza_status(self) -> dict[str, object]:
        ready = self.lemmatizer._ensure_pipeline()
        info = self.lemmatizer.cache_info()
        return {
            **info,
            "stanza_ready": ready,
            "nlp_available": ready,
            "models_dir": None,
            "models_exist": ready,
            "can_lemmatize": ready,
        }

    def test_stanza_offline(self, texto_prueba: str = "hola mundo") -> bool:
        tokens = texto_prueba.split()
        self.lemmatizer.lemmatize(tokens)
        return self.lemmatizer.ready

    def reiniciar_stanza(self) -> bool:
        self.lemmatizer = StanzaLemmatizer(enabled=self.config.enable_stanza)
        return self.lemmatizer._ensure_pipeline()

    def get_cache_info(self) -> dict[str, object]:
        return {
            "lemma": self.lemmatizer.cache_info(),
            "normalization": normalize_text.cache_info(),
            "active_utterances": len(self._buffers),
        }

    def estadisticas_diccionario(self) -> dict[str, object]:
        return self.catalog.report()

    def debug_palabra(self, palabra: str) -> dict[str, object]:
        normalized = normalize_text(palabra)
        lemma = self.lemmatizer.lemmatize((palabra,))[0]
        entry = self.catalog.lookup(normalized) or self.catalog.lookup(lemma)
        return {
            "original": palabra,
            "normalizada": normalized,
            "raiz": lemma,
            "en_diccionario": entry is not None,
            "ruta": str(entry.video_path) if entry else None,
            "archivo_existe": bool(entry and entry.video_path.is_file()),
            "stanza_ready": self.lemmatizer.ready,
        }


PlanCallback = Callable[[SignPlan], None]


class TranslationWorker:
    """Serializa Stanza y la planificación fuera del hilo de Tkinter."""

    _STOP = object()

    def __init__(self, translator: Translator, callback: PlanCallback) -> None:
        self.translator = translator
        self.callback = callback
        self._queue: queue.Queue[TranscriptEvent | object] = queue.Queue(
            maxsize=translator.config.translation_queue_size
        )
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._thread = threading.Thread(
            target=self._run,
            name="translation-worker",
            daemon=True,
        )
        self._thread.start()

    def submit(self, event: TranscriptEvent) -> bool:
        if not self._running.is_set():
            return False
        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            pipeline_metrics.increment("translation_queue_overflows")
            return False

    def _run(self) -> None:
        while self._running.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is self._STOP:
                break
            assert isinstance(item, TranscriptEvent)
            try:
                plan = self.translator.translate_event(item)
                self.callback(plan)
            except Exception:
                pipeline_metrics.increment("translation_worker_errors")

    def stop(self) -> None:
        self._running.clear()
        try:
            self._queue.put_nowait(self._STOP)
        except queue.Full:
            pass
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._thread = None
