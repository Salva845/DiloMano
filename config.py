"""Configuración central del pipeline de Dilo Mano.

Los valores se concentran aquí para que los perfiles realmente afecten a los
componentes. Las rutas siempre se resuelven desde el proyecto, no desde el
directorio desde el que se ejecutó Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class AudioConfig:
    model_path: Path = BASE_DIR / "vosk-model-es-0.42"
    sample_rate: int = 16_000
    block_size: int = 1_600  # 100 ms; probar también 800 en el hardware final.
    queue_blocks: int = 8
    stability_updates: int = 2
    partial_min_interval_ms: int = 40
    endpoint_start_s: float = 5.0
    endpoint_end_s: float = 0.50
    endpoint_max_s: float = 20.0


@dataclass(frozen=True, slots=True)
class NLPConfig:
    enable_stanza: bool = True
    spell_unknown_words: bool = True
    max_spelling_letters: int = 18
    translation_queue_size: int = 64


@dataclass(frozen=True, slots=True)
class VideoConfig:
    speed: float = 1.0
    frame_buffer_size: int = 3
    ui_poll_ms: int = 8
    max_pending_items: int = 48
    max_provisional_items: int = 12
    max_queue_seconds: float = 6.0
    resize_filter: str = "BILINEAR"
    estimated_clip_duration: float = 0.8
    show_subtitles: bool = True
    subtitle_font_size: int = 22
    subtitle_show_position: bool = True


@dataclass(frozen=True, slots=True)
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    nlp: NLPConfig = field(default_factory=NLPConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    window_size: tuple[int, int] = (900, 650)
    min_window_size: tuple[int, int] = (500, 360)
    ui_event_poll_ms: int = 30


DEFAULT_CONFIG = AppConfig()


class HardwareProfiles:
    """Perfiles prudentes; nunca aumentan la latencia de captura."""

    _PROFILES = {
        "LOW_END": {"block_size": 1_600, "frame_buffer_size": 2},
        "MID_RANGE": {"block_size": 1_600, "frame_buffer_size": 3},
        "HIGH_END": {"block_size": 800, "frame_buffer_size": 4},
    }

    @classmethod
    def build(cls, profile_name: str, base: AppConfig = DEFAULT_CONFIG) -> AppConfig:
        values = cls._PROFILES.get(profile_name.upper())
        if values is None:
            raise ValueError(f"Perfil desconocido: {profile_name}")
        return replace(
            base,
            audio=replace(base.audio, block_size=values["block_size"]),
            video=replace(base.video, frame_buffer_size=values["frame_buffer_size"]),
        )

    @classmethod
    def apply_profile(cls, profile_name: str) -> AppConfig:
        """Compatibilidad con versiones anteriores; devuelve el nuevo config."""
        return cls.build(profile_name)


class PerformanceConfig:
    """Alias de compatibilidad para código externo de versiones anteriores."""

    AUDIO_SAMPLERATE = DEFAULT_CONFIG.audio.sample_rate
    AUDIO_BLOCKSIZE = DEFAULT_CONFIG.audio.block_size
    AUDIO_QUEUE_SIZE = DEFAULT_CONFIG.audio.queue_blocks
    VIDEO_FPS = 30
    VIDEO_SKIP_FRAMES = 0
    VIDEO_CACHE_SIZE = DEFAULT_CONFIG.video.frame_buffer_size
    TRANSLATION_CACHE_SIZE = 2_000
    WORD_CACHE_SIZE = 4_000

    @classmethod
    def get_audio_config(cls) -> dict[str, int]:
        return {
            "samplerate": cls.AUDIO_SAMPLERATE,
            "blocksize": cls.AUDIO_BLOCKSIZE,
            "queue_size": cls.AUDIO_QUEUE_SIZE,
        }

    @classmethod
    def get_video_config(cls) -> dict[str, int]:
        return {
            "fps": cls.VIDEO_FPS,
            "skip_frames": cls.VIDEO_SKIP_FRAMES,
            "cache_size": cls.VIDEO_CACHE_SIZE,
        }
