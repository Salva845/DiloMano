"""Métricas ligeras y thread-safe para observar la ruta crítica."""

from __future__ import annotations

from collections import defaultdict, deque
from contextlib import contextmanager
import json
from math import ceil
from pathlib import Path
from statistics import median
from threading import Lock
from time import monotonic_ns
from typing import Iterator


class PipelineMetrics:
    def __init__(self, samples_per_metric: int = 2_000) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._samples: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=samples_per_metric)
        )

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount

    def observe_ms(self, name: str, value_ms: float) -> None:
        with self._lock:
            self._samples[name].append(float(value_ms))

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        started = monotonic_ns()
        try:
            yield
        finally:
            self.observe_ms(name, (monotonic_ns() - started) / 1_000_000)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = dict(self._counters)
            samples = {name: list(values) for name, values in self._samples.items()}

        latencies: dict[str, dict[str, float | int]] = {}
        for name, values in samples.items():
            if not values:
                continue
            ordered = sorted(values)
            latencies[name] = {
                "count": len(ordered),
                "p50_ms": round(median(ordered), 3),
                "p95_ms": round(ordered[max(0, ceil(len(ordered) * 0.95) - 1)], 3),
                "max_ms": round(ordered[-1], 3),
            }
        return {"counters": counters, "latencies": latencies}

    def write_snapshot(self, path: Path) -> None:
        payload = json.dumps(self.snapshot(), ensure_ascii=False, indent=2)
        Path(path).write_text(payload + "\n", encoding="utf-8")


pipeline_metrics = PipelineMetrics()
