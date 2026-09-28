"""Captura PCM y reconocimiento Vosk con deltas de hipótesis estables."""

from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
from time import monotonic_ns, sleep
from typing import Callable

from config import AudioConfig
from events import TranscriptEvent
from hypothesis_stabilizer import HypothesisStabilizer
from metrics import pipeline_metrics


EventCallback = Callable[[TranscriptEvent], None]
StatusCallback = Callable[[str, object], None]


class StreamingListener:
    def __init__(
        self,
        frase_callback: EventCallback,
        modelo_path: str | Path | None = None,
        samplerate: int | None = None,
        config: AudioConfig | None = None,
        status_callback: StatusCallback | None = None,
    ) -> None:
        base = config or AudioConfig()
        self.config = AudioConfig(
            model_path=Path(modelo_path).resolve() if modelo_path else base.model_path,
            sample_rate=samplerate or base.sample_rate,
            block_size=base.block_size,
            queue_blocks=base.queue_blocks,
            stability_updates=base.stability_updates,
            partial_min_interval_ms=base.partial_min_interval_ms,
            endpoint_start_s=base.endpoint_start_s,
            endpoint_end_s=base.endpoint_end_s,
            endpoint_max_s=base.endpoint_max_s,
        )
        self.event_callback = frase_callback
        self.status_callback = status_callback
        self._audio_queue: queue.Queue[bytes] = queue.Queue(
            maxsize=self.config.queue_blocks
        )
        self._running = threading.Event()
        self._stop_requested = threading.Event()
        self._muted = threading.Event()
        self._overflowed = threading.Event()
        self._reset_requested = threading.Event()
        self._processor_thread: threading.Thread | None = None
        self._stream = None
        self._model = None
        self._last_partial_ns = 0
        self._active_sample_rate = self.config.sample_rate
        self._active_block_size = self.config.block_size
        self._stabilizer = HypothesisStabilizer(self.config.stability_updates)
        self._stats_lock = threading.Lock()
        self._stats = {
            "audio_blocks": 0,
            "audio_overflows": 0,
            "partials": 0,
            "finals": 0,
            "events": 0,
            "resets": 0,
        }

    def _status(self, name: str, value: object = True) -> None:
        if self.status_callback is not None:
            try:
                self.status_callback(name, value)
            except Exception:
                pipeline_metrics.increment("status_callback_errors")

    def _increment(self, key: str) -> None:
        with self._stats_lock:
            self._stats[key] += 1
        pipeline_metrics.increment(key)

    def _callback_audio(self, indata, frames, time_info, status) -> None:
        """Callback PortAudio: copiar bytes y regresar inmediatamente."""
        if status:
            pipeline_metrics.increment("audio_callback_status")
        if not self._running.is_set() or self._muted.is_set():
            return
        try:
            self._audio_queue.put_nowait(bytes(indata))
            self._increment("audio_blocks")
        except queue.Full:
            # No se empalman bloques viejos y nuevos. El recognizer completo se
            # reinicia en el worker para volver a una frontera coherente.
            self._increment("audio_overflows")
            self._overflowed.set()

    @staticmethod
    def _clear_queue(audio_queue: queue.Queue[bytes]) -> int:
        removed = 0
        while True:
            try:
                audio_queue.get_nowait()
                removed += 1
            except queue.Empty:
                return removed

    def _reset_recognizer(self, recognizer) -> None:
        self._clear_queue(self._audio_queue)
        if hasattr(recognizer, "Reset"):
            recognizer.Reset()
        self._stabilizer.abort()
        self._overflowed.clear()
        self._reset_requested.clear()
        self._increment("resets")

    def _emit(self, event: TranscriptEvent | None) -> None:
        if event is None:
            return
        try:
            self.event_callback(event)
            self._increment("events")
            pipeline_metrics.observe_ms(
                "asr_event_callback_ms",
                (monotonic_ns() - event.created_ns) / 1_000_000,
            )
        except Exception as exc:
            pipeline_metrics.increment("asr_event_callback_errors")
            self._status("error", f"Callback ASR: {exc}")

    def _process_partial(self, recognizer) -> None:
        now = monotonic_ns()
        interval_ns = self.config.partial_min_interval_ms * 1_000_000
        if now - self._last_partial_ns < interval_ns:
            return
        self._last_partial_ns = now
        payload = json.loads(recognizer.PartialResult())
        text = str(payload.get("partial", "")).strip()
        if not text:
            return
        self._increment("partials")
        self._emit(
            self._stabilizer.accept_partial(text, payload.get("partial_result"))
        )

    def _process_final(self, recognizer) -> None:
        payload = json.loads(recognizer.Result())
        text = str(payload.get("text", "")).strip()
        self._increment("finals")
        self._emit(self._stabilizer.accept_final(text, payload.get("result")))

    def _process_audio(self, recognizer) -> None:
        self._status("recognizer_ready")
        try:
            while self._running.is_set():
                if self._overflowed.is_set() or self._reset_requested.is_set():
                    self._reset_recognizer(recognizer)
                    self._status("recognizer_reset")
                    continue
                try:
                    data = self._audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                with pipeline_metrics.timer("vosk_accept_ms"):
                    is_final = recognizer.AcceptWaveform(data)
                if is_final:
                    self._process_final(recognizer)
                else:
                    self._process_partial(recognizer)
        except Exception as exc:
            pipeline_metrics.increment("recognizer_errors")
            self._status("error", f"Reconocimiento: {exc}")
            self._running.clear()

    def _create_recognizer(self, vosk_module, sample_rate: int):
        recognizer = vosk_module.KaldiRecognizer(
            self._model,
            sample_rate,
        )
        recognizer.SetWords(True)
        if hasattr(recognizer, "SetPartialWords"):
            recognizer.SetPartialWords(True)
        if hasattr(recognizer, "SetMaxAlternatives"):
            recognizer.SetMaxAlternatives(0)
        if hasattr(recognizer, "SetEndpointerDelays"):
            recognizer.SetEndpointerDelays(
                self.config.endpoint_start_s,
                self.config.endpoint_end_s,
                self.config.endpoint_max_s,
            )
        return recognizer

    def start(self, device_id=None) -> None:
        """Inicia el stream. Es bloqueante y debe llamarse desde un worker."""
        if self._running.is_set():
            return
        self._stop_requested.clear()
        try:
            import sounddevice as sd
            import vosk
        except ImportError as exc:
            self._status("error", f"Dependencia no instalada: {exc}")
            raise

        model_path = self.config.model_path
        if not model_path.is_dir():
            raise FileNotFoundError(f"Modelo Vosk no encontrado: {model_path}")

        self._status("loading_model", str(model_path))
        if self._model is None:
            with pipeline_metrics.timer("vosk_model_load_ms"):
                self._model = vosk.Model(str(model_path))
        if self._stop_requested.is_set():
            return
        sample_rate = self.config.sample_rate
        try:
            sd.check_input_settings(
                device=device_id,
                channels=1,
                dtype="int16",
                samplerate=sample_rate,
            )
        except Exception:
            device_info = sd.query_devices(device_id, "input")
            sample_rate = int(device_info["default_samplerate"])
            self._status("native_sample_rate", sample_rate)
        block_duration = self.config.block_size / self.config.sample_rate
        block_size = max(1, round(sample_rate * block_duration))
        self._active_sample_rate = sample_rate
        self._active_block_size = block_size

        recognizer = self._create_recognizer(vosk, sample_rate)

        self._running.set()
        self._processor_thread = threading.Thread(
            target=self._process_audio,
            args=(recognizer,),
            name="asr-processor",
            daemon=True,
        )
        self._processor_thread.start()

        try:
            with sd.RawInputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                blocksize=block_size,
                callback=self._callback_audio,
                device=device_id,
                latency="low",
            ) as stream:
                self._stream = stream
                self._status("stream_ready", device_id)
                while self._running.is_set() and not self._stop_requested.is_set():
                    sleep(0.1)
        except Exception as exc:
            self._status("error", f"Micrófono: {exc}")
            raise
        finally:
            self._running.clear()
            self._stream = None
            if self._processor_thread is not None:
                self._processor_thread.join(timeout=2.0)
            self._processor_thread = None
            self._clear_queue(self._audio_queue)
            self._status("stopped")

    def iniciar(self, device_id=None) -> None:
        self.start(device_id)

    def set_muted(self, muted: bool) -> None:
        if muted:
            self._muted.set()
        else:
            self._muted.clear()
        self._reset_requested.set()

    def stop(self) -> None:
        self._stop_requested.set()
        self._running.clear()
        self._reset_requested.set()

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def get_stats(self) -> dict[str, int | bool]:
        with self._stats_lock:
            stats: dict[str, int | bool] = dict(self._stats)
        stats["running"] = self.running
        stats["muted"] = self._muted.is_set()
        stats["queued_blocks"] = self._audio_queue.qsize()
        stats["sample_rate"] = self._active_sample_rate
        stats["block_size"] = self._active_block_size
        return stats
