"""Scheduler de clips con cola acotada, prefetch y render seguro en Tk."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from itertools import chain, count
from pathlib import Path
import queue
import threading
from time import monotonic, monotonic_ns
from typing import Any

import tkinter as tk

from config import VideoConfig
from events import SignItem, SignPlan
from metrics import pipeline_metrics


@dataclass(slots=True)
class _PreparedVideo:
    item: SignItem
    reader: Any
    iterator: Any
    first_frames: list[Any]
    fps: float


@dataclass(slots=True)
class _FramePacket:
    image: Any
    item: SignItem


class VideoPlayer:
    def __init__(self, ventana, config: VideoConfig | None = None) -> None:
        self.config = config or VideoConfig()
        self.frame_video = tk.Frame(ventana, bg="black")
        self.frame_video.pack(fill="both", expand=True)
        self.label_video = tk.Label(self.frame_video, bg="black")
        self.label_video.place(relx=0.5, rely=0.5, anchor="center")
        self.subtitle_label = tk.Label(
            self.frame_video,
            bg="black",
            fg="white",
            font=("Segoe UI", self.config.subtitle_font_size, "bold"),
            padx=14,
            pady=7,
            justify="center",
        )
        if self.config.show_subtitles:
            self.subtitle_label.place(
                relx=0.5,
                rely=0.94,
                anchor="s",
                relwidth=0.92,
            )
            self.subtitle_label.lift()

        self._condition = threading.Condition()
        self._pending: deque[SignItem] = deque()
        self._running = True
        self._current: SignItem | None = None
        self._speed = self.config.speed
        self._target_size = (640, 480)
        self._frame_queue: queue.Queue[_FramePacket] = queue.Queue(
            maxsize=self.config.frame_buffer_size
        )
        self._prefetch_generation = 0
        self._prefetch_thread: threading.Thread | None = None
        self._prefetched: _PreparedVideo | None = None
        self._manual_ids = count(1)
        self._first_frame_keys: set[tuple[str, int, int, Path]] = set()
        self._subtitle_item_key: tuple[str, int, int, Path, str, str] | None = None
        self._average_clip_duration = self.config.estimated_clip_duration
        self._stats = {
            "enqueued": 0,
            "played": 0,
            "rejected_provisional": 0,
            "rejected_overflow": 0,
            "revisions": 0,
            "frames_displayed": 0,
            "frames_dropped": 0,
            "video_errors": 0,
        }

        self.frame_video.bind("<Configure>", self._on_resize)
        self._worker = threading.Thread(
            target=self._process_loop,
            name="video-decoder",
            daemon=True,
        )
        self._worker.start()
        self.frame_video.after(self.config.ui_poll_ms, self._poll_frames)

    @staticmethod
    def _item_key(item: SignItem) -> tuple[str, int, int, Path]:
        return (
            item.utterance_id,
            item.start_index,
            item.end_index,
            item.video_path,
        )

    @staticmethod
    def _subtitle_key(item: SignItem) -> tuple[str, int, int, Path, str, str]:
        return (*VideoPlayer._item_key(item), item.source_text, item.gloss)

    def _on_resize(self, event) -> None:
        with self._condition:
            self._target_size = (max(100, event.width), max(100, event.height))
        self.subtitle_label.configure(wraplength=max(100, event.width - 40))

    def _subtitle_text(self, item: SignItem) -> str:
        text = item.source_text.strip() or item.gloss
        if not self.config.subtitle_show_position:
            return text
        first = item.start_index + 1
        last = item.end_index
        position = (
            f"palabras {first}-{last}"
            if last > first
            else f"palabra {first}"
        )
        return f"{text}  ·  {position}"

    def _clear_subtitle(self) -> None:
        if self._subtitle_item_key is None:
            return
        self.subtitle_label.configure(text="")
        self._subtitle_item_key = None

    def set_velocidad(self, multiplicador: float) -> None:
        with self._condition:
            self._speed = max(0.5, min(3.0, float(multiplicador)))

    def _invalidate_prefetch_locked(self) -> None:
        self._prefetch_generation += 1
        prepared = self._prefetched
        self._prefetched = None
        if prepared is not None:
            try:
                prepared.reader.close()
            except Exception:
                pass

    def enqueue_plan(self, plan: SignPlan) -> int:
        accepted = 0
        with self._condition:
            if not self._running:
                return 0

            if plan.revision_from is not None:
                self._pending = deque(
                    item
                    for item in self._pending
                    if not (
                        item.utterance_id == plan.utterance_id
                        and item.end_index > plan.revision_from
                    )
                )
                self._invalidate_prefetch_locked()
                self._stats["revisions"] += 1

            if plan.is_final:
                self._pending = deque(
                    replace(item, provisional=False)
                    if item.utterance_id == plan.utterance_id
                    else item
                    for item in self._pending
                )

            for item in plan.items:
                provisional_count = sum(p.provisional for p in self._pending)
                estimated_seconds = (
                    len(self._pending) * self._average_clip_duration / max(self._speed, 0.1)
                )
                if item.provisional and (
                    provisional_count >= self.config.max_provisional_items
                    or estimated_seconds >= self.config.max_queue_seconds
                ):
                    self._stats["rejected_provisional"] += 1
                    pipeline_metrics.increment("video_rejected_provisional")
                    continue
                if len(self._pending) >= self.config.max_pending_items:
                    provisional_index = next(
                        (
                            index
                            for index in range(len(self._pending) - 1, -1, -1)
                            if self._pending[index].provisional
                        ),
                        None,
                    )
                    if provisional_index is not None:
                        del self._pending[provisional_index]
                    else:
                        self._stats["rejected_overflow"] += 1
                        pipeline_metrics.increment("video_queue_overflows")
                        continue
                self._pending.append(item)
                self._stats["enqueued"] += 1
                accepted += 1

            if accepted or plan.revision_from is not None or plan.is_final:
                self._condition.notify_all()
        return accepted

    def reproducir_videos(self, lista_videos) -> int:
        """Compatibilidad con la API anterior."""
        if isinstance(lista_videos, (str, Path)):
            lista_videos = [lista_videos]
        utterance_id = f"manual-video-{next(self._manual_ids)}"
        items = tuple(
            SignItem(
                gloss=Path(path).stem,
                source_text=Path(path).stem,
                video_path=Path(path).resolve(),
                utterance_id=utterance_id,
                start_index=index,
                end_index=index + 1,
                provisional=False,
            )
            for index, path in enumerate(lista_videos)
            if Path(path).is_file()
        )
        return self.enqueue_plan(
            SignPlan(
                utterance_id=utterance_id,
                source_text="",
                items=items,
                is_final=True,
            )
        )

    def _prepare_video(self, item: SignItem) -> _PreparedVideo:
        import imageio.v2 as imageio

        reader = imageio.get_reader(str(item.video_path))
        metadata = reader.get_meta_data()
        fps = float(metadata.get("fps") or 30.0)
        if fps <= 0 or fps > 240:
            fps = 30.0
        iterator = iter(reader)
        first_frames: list[Any] = []
        try:
            first_frames.append(next(iterator))
        except StopIteration:
            pass
        return _PreparedVideo(item, reader, iterator, first_frames, fps)

    def _start_prefetch_next(self) -> None:
        with self._condition:
            if not self._running or not self._pending:
                return
            item = self._pending[0]
            if self._prefetched and self._item_key(self._prefetched.item) == self._item_key(item):
                return
            if self._prefetch_thread and self._prefetch_thread.is_alive():
                return
            self._prefetch_generation += 1
            generation = self._prefetch_generation

        def prepare() -> None:
            prepared: _PreparedVideo | None = None
            try:
                prepared = self._prepare_video(item)
            except Exception:
                pipeline_metrics.increment("video_prefetch_errors")
            with self._condition:
                still_next = bool(
                    self._pending
                    and self._item_key(self._pending[0]) == self._item_key(item)
                )
                if (
                    prepared is not None
                    and self._running
                    and generation == self._prefetch_generation
                    and still_next
                ):
                    old = self._prefetched
                    self._prefetched = prepared
                    if old is not None:
                        try:
                            old.reader.close()
                        except Exception:
                            pass
                elif prepared is not None:
                    try:
                        prepared.reader.close()
                    except Exception:
                        pass

        self._prefetch_thread = threading.Thread(
            target=prepare,
            name="video-prefetch",
            daemon=True,
        )
        self._prefetch_thread.start()

    def _take_prepared(self, item: SignItem) -> _PreparedVideo | None:
        with self._condition:
            if self._prefetched and self._item_key(self._prefetched.item) == self._item_key(item):
                prepared = self._prefetched
                self._prefetched = None
                return prepared
        return None

    def _offer_frame(self, packet: _FramePacket) -> None:
        try:
            self._frame_queue.put_nowait(packet)
        except queue.Full:
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._frame_queue.put_nowait(packet)
            except queue.Full:
                pass
            self._stats["frames_dropped"] += 1
            pipeline_metrics.increment("render_frames_dropped")

    def _resize_frame(self, frame) -> Any:
        from PIL import Image

        with self._condition:
            target_size = self._target_size
            filter_name = self.config.resize_filter
        image = Image.fromarray(frame)
        resampling = (
            Image.Resampling.BILINEAR
            if filter_name.upper() == "BILINEAR"
            else Image.Resampling.LANCZOS
        )
        image.thumbnail(target_size, resampling)
        return image

    def _play(self, item: SignItem) -> float:
        prepared = self._take_prepared(item)
        if prepared is None:
            prepared = self._prepare_video(item)
        self._start_prefetch_next()

        deadline = monotonic()
        frame_index = 0
        try:
            for frame in chain(prepared.first_frames, prepared.iterator):
                with self._condition:
                    if not self._running:
                        break
                    speed = self._speed
                interval = 1.0 / max(1.0, prepared.fps * speed)
                remaining = deadline - monotonic()
                if remaining > 0:
                    threading.Event().wait(remaining)
                elif -remaining > interval * 1.5 and frame_index > 0:
                    frame_index += 1
                    deadline += interval
                    self._stats["frames_dropped"] += 1
                    pipeline_metrics.increment("decoder_frames_dropped")
                    continue
                self._offer_frame(_FramePacket(self._resize_frame(frame), item))
                frame_index += 1
                deadline += interval
        finally:
            try:
                prepared.reader.close()
            except Exception:
                pass
        return frame_index / prepared.fps if prepared.fps > 0 else 0.0

    def _process_loop(self) -> None:
        while True:
            with self._condition:
                while self._running and not self._pending:
                    self._condition.wait(timeout=0.5)
                if not self._running:
                    break
                item = self._pending.popleft()
                self._current = item
            try:
                with pipeline_metrics.timer("video_clip_total_ms"):
                    source_duration = self._play(item)
                if source_duration > 0:
                    self._average_clip_duration = (
                        self._average_clip_duration * 0.8 + source_duration * 0.2
                    )
                self._stats["played"] += 1
            except Exception:
                self._stats["video_errors"] += 1
                pipeline_metrics.increment("video_errors")
            finally:
                with self._condition:
                    self._current = None

    def _poll_frames(self) -> None:
        if not self._running:
            return
        latest: _FramePacket | None = None
        while True:
            try:
                latest = self._frame_queue.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            try:
                from PIL import ImageTk

                photo = ImageTk.PhotoImage(latest.image)
                self.label_video.configure(image=photo)
                self.label_video.image = photo
                item_key = self._item_key(latest.item)
                subtitle_key = self._subtitle_key(latest.item)
                if (
                    self.config.show_subtitles
                    and subtitle_key != self._subtitle_item_key
                ):
                    self.subtitle_label.configure(text=self._subtitle_text(latest.item))
                    self.subtitle_label.lift()
                    self._subtitle_item_key = subtitle_key
                self._stats["frames_displayed"] += 1
                pipeline_metrics.increment("frames_displayed")
                if item_key not in self._first_frame_keys:
                    self._first_frame_keys.add(item_key)
                    pipeline_metrics.observe_ms(
                        "stable_token_to_first_frame_ms",
                        (monotonic_ns() - latest.item.source_event_ns) / 1_000_000,
                    )
            except tk.TclError:
                with self._condition:
                    self._running = False
                    self._condition.notify_all()
                return
        elif self.config.show_subtitles:
            with self._condition:
                playback_finished = self._current is None
            if playback_finished and self._frame_queue.empty():
                self._clear_subtitle()
        self.frame_video.after(self.config.ui_poll_ms, self._poll_frames)

    def limpiar_cola(self) -> int:
        with self._condition:
            removed = len(self._pending)
            self._pending.clear()
            self._invalidate_prefetch_locked()
            return removed

    def get_estadisticas(self) -> dict[str, object]:
        with self._condition:
            return {
                **self._stats,
                "cola_actual": len(self._pending),
                "reproduciendo": self._current is not None,
                "running": self._running,
                "velocidad": self._speed,
                "cola_estimada_s": round(
                    len(self._pending)
                    * self._average_clip_duration
                    / max(self._speed, 0.1),
                    2,
                ),
                "current": self._current.gloss if self._current else None,
            }

    @property
    def reproduciendo(self) -> bool:
        with self._condition:
            return self._current is not None

    def stop(self) -> None:
        with self._condition:
            self._running = False
            self._pending.clear()
            self._invalidate_prefetch_locked()
            self._condition.notify_all()
        if self._worker.is_alive():
            self._worker.join(timeout=3.0)
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=1.0)
        while True:
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._clear_subtitle()
        except tk.TclError:
            pass
