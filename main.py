"""Aplicación Dilo Mano con pipeline desacoplado y medible."""

from __future__ import annotations

import argparse
import queue
import signal
import threading
import tkinter as tk

from asset_catalog import default_catalog
from config import AppConfig, BASE_DIR, DEFAULT_CONFIG, HardwareProfiles
from events import SignPlan, TranscriptEvent, WordToken
from metrics import pipeline_metrics
from streaming_listener import StreamingListener
from translator import TranslationWorker, Translator
from video_player import VideoPlayer


class App:
    def __init__(
        self,
        root: tk.Tk,
        mic_id=None,
        config: AppConfig = DEFAULT_CONFIG,
    ) -> None:
        self.root = root
        self.config = config
        self.mic_id = mic_id
        self.running = True
        self.muted = False
        self._state_lock = threading.Lock()
        self._mode_value = "tiempo_real"
        self._ui_events: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=256)
        self._listener_thread: threading.Thread | None = None

        root.title("Dilo Mano")
        root.geometry(f"{config.window_size[0]}x{config.window_size[1]}")
        root.minsize(*config.min_window_size)
        root.protocol("WM_DELETE_WINDOW", self.on_closing)

        frame_video = tk.Frame(root, bg="black")
        frame_video.pack(fill="both", expand=True)
        self.player = VideoPlayer(frame_video, config.video)

        controls = tk.Frame(root, padx=8, pady=6)
        controls.pack(fill="x")
        self.label = tk.Label(
            controls,
            text="Preparando reconocimiento...",
            font=("Arial", 13),
            anchor="w",
        )
        self.label.pack(fill="x")

        actions = tk.Frame(controls)
        actions.pack(fill="x", pady=(5, 0))
        self.status_label = tk.Label(actions, text="ASR: cargando", anchor="w")
        self.status_label.pack(side="left", padx=(0, 10))

        self.mode = tk.StringVar(value="tiempo_real")
        tk.OptionMenu(
            actions,
            self.mode,
            "tiempo_real",
            "frase_final",
            command=self.on_mode_change,
        ).pack(side="left", padx=4)

        self.speed = tk.DoubleVar(value=config.video.speed)
        tk.Scale(
            actions,
            from_=0.5,
            to=3.0,
            resolution=0.1,
            orient="horizontal",
            variable=self.speed,
            length=140,
            label="Velocidad",
            command=self.on_speed_change,
        ).pack(side="left", padx=4)

        tk.Button(actions, text="Limpiar cola", command=self.clear_video_queue).pack(
            side="right", padx=4
        )
        self.mute_button = tk.Button(
            actions,
            text="Mutear",
            command=self.toggle_mute,
        )
        self.mute_button.pack(side="right", padx=4)

        self.stats_label = tk.Label(controls, text="", anchor="w", font=("Arial", 9))
        self.stats_label.pack(fill="x", pady=(4, 0))

        self.translator = Translator(
            catalog=default_catalog,
            config=config.nlp,
        )
        self.translation_worker = TranslationWorker(
            self.translator,
            self._on_plan_worker,
        )
        self.translation_worker.start()
        self._nlp_warmup_thread = threading.Thread(
            target=self._warmup_nlp_worker,
            name="stanza-warmup",
            daemon=True,
        )
        self._nlp_warmup_thread.start()

        self.listener = StreamingListener(
            self._on_transcript_worker,
            config=config.audio,
            status_callback=self._on_listener_status_worker,
        )
        self._listener_thread = threading.Thread(
            target=self._run_listener,
            name="microphone-listener",
            daemon=True,
        )
        self._listener_thread.start()

        catalog_report = default_catalog.report()
        self._post_ui("catalog", catalog_report)
        self.root.after(config.ui_event_poll_ms, self._drain_ui_events)

    def _post_ui(self, name: str, value: object) -> None:
        try:
            self._ui_events.put_nowait((name, value))
        except queue.Full:
            pipeline_metrics.increment("ui_event_overflows")

    def _run_listener(self) -> None:
        try:
            self.listener.start(self.mic_id)
        except Exception as exc:
            self._post_ui("error", str(exc))

    def _warmup_nlp_worker(self) -> None:
        ready = self.translator.prewarm()
        self._post_ui("nlp_status", ready)

    def _on_listener_status_worker(self, name: str, value: object) -> None:
        self._post_ui("listener_status", (name, value))

    def _event_for_final_mode(self, event: TranscriptEvent) -> TranscriptEvent:
        words = tuple(
            WordToken(text=word, index=index)
            for index, word in enumerate(event.full_text.split())
        )
        return TranscriptEvent(
            utterance_id=event.utterance_id,
            text=event.full_text,
            full_text=event.full_text,
            words=words,
            start_index=0,
            is_final=True,
            revision_from=0,
        )

    def _on_transcript_worker(self, event: TranscriptEvent) -> None:
        self._post_ui("transcript", event)
        with self._state_lock:
            mode = self._mode_value
            muted = self.muted
        if muted:
            return
        if mode == "frase_final":
            if not event.is_final:
                return
            event = self._event_for_final_mode(event)
        if not self.translation_worker.submit(event):
            self._post_ui("error", "La cola de traducción está saturada")

    def _on_plan_worker(self, plan: SignPlan) -> None:
        accepted = self.player.enqueue_plan(plan)
        self._post_ui("plan", (plan, accepted))

    def _drain_ui_events(self) -> None:
        if not self.running:
            return
        latest_transcript: TranscriptEvent | None = None
        while True:
            try:
                name, value = self._ui_events.get_nowait()
            except queue.Empty:
                break

            if name == "transcript":
                latest_transcript = value  # type: ignore[assignment]
            elif name == "listener_status":
                status_name, status_value = value  # type: ignore[misc]
                if status_name == "loading_model":
                    self.status_label.configure(text="ASR: cargando modelo")
                elif status_name in {"recognizer_ready", "stream_ready"}:
                    self.status_label.configure(text="ASR: escuchando")
                elif status_name == "native_sample_rate":
                    self.status_label.configure(
                        text=f"ASR: usando frecuencia nativa {status_value} Hz"
                    )
                elif status_name == "recognizer_reset":
                    self.status_label.configure(text="ASR: recuperado tras pérdida de audio")
                elif status_name == "stopped":
                    self.status_label.configure(text="ASR: detenido")
                elif status_name == "error":
                    self.status_label.configure(text=f"ASR: {status_value}")
            elif name == "error":
                self.status_label.configure(text=f"Error: {value}")
            elif name == "nlp_status" and not value:
                self.status_label.configure(
                    text="NLP: Stanza no disponible; usando coincidencia exacta"
                )
            elif name == "catalog":
                report = value  # type: ignore[assignment]
                missing = report.get("missing_entries", 0)
                valid = report.get("valid_entries", 0)
                self.stats_label.configure(
                    text=f"Catálogo: {valid} glosas válidas, {missing} rutas faltantes"
                )

        if latest_transcript is not None:
            state = "final" if latest_transcript.is_final else "estable"
            self.label.configure(
                text=f"{state.capitalize()}: {latest_transcript.full_text}"
            )

        video_stats = self.player.get_estadisticas()
        listener_stats = self.listener.get_stats()
        self.stats_label.configure(
            text=(
                f"Cola visual: {video_stats['cola_actual']} "
                f"({video_stats['cola_estimada_s']} s) | "
                f"Overflows audio: {listener_stats['audio_overflows']} | "
                f"Frames descartados: {video_stats['frames_dropped']}"
            )
        )
        self.root.after(self.config.ui_event_poll_ms, self._drain_ui_events)

    def on_mode_change(self, value: str) -> None:
        with self._state_lock:
            self._mode_value = value
        self.player.limpiar_cola()

    def on_speed_change(self, value: str) -> None:
        self.player.set_velocidad(float(value))

    def toggle_mute(self) -> None:
        with self._state_lock:
            self.muted = not self.muted
            muted = self.muted
        self.listener.set_muted(muted)
        self.mute_button.configure(text="Activar" if muted else "Mutear")
        self.status_label.configure(text="ASR: silenciado" if muted else "ASR: escuchando")

    def clear_video_queue(self) -> None:
        removed = self.player.limpiar_cola()
        self.status_label.configure(text=f"Cola limpiada: {removed} clips")

    def on_closing(self) -> None:
        if not self.running:
            return
        self.running = False
        self.listener.stop()
        self.translation_worker.stop()
        self.player.stop()
        if self._listener_thread is not None:
            self._listener_thread.join(timeout=3.0)
        if self._nlp_warmup_thread.is_alive():
            self._nlp_warmup_thread.join(timeout=1.0)
        try:
            pipeline_metrics.write_snapshot(BASE_DIR / "metrics-last.json")
        except OSError:
            pass
        self.root.destroy()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dilo Mano")
    parser.add_argument("--device", default=None, help="ID o nombre del micrófono")
    parser.add_argument(
        "--profile",
        choices=("LOW_END", "MID_RANGE", "HIGH_END"),
        default="MID_RANGE",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = HardwareProfiles.build(args.profile)
    device = int(args.device) if str(args.device).isdigit() else args.device
    root = tk.Tk()
    app = App(root, mic_id=device, config=config)

    def close_from_signal(*_args) -> None:
        root.after(0, app.on_closing)

    try:
        signal.signal(signal.SIGINT, close_from_signal)
        signal.signal(signal.SIGTERM, close_from_signal)
    except (ValueError, OSError):
        pass
    root.mainloop()


if __name__ == "__main__":
    main()
