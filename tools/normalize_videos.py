"""Genera copias homogéneas de los clips sin sobrescribir los originales."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]


def find_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError(
            "FFmpeg no está disponible. Instala requirements.txt o agrega ffmpeg al PATH."
        ) from exc


def normalize_video(
    ffmpeg: str,
    source: Path,
    destination: Path,
    *,
    width: int,
    height: int,
    fps: int,
    overwrite: bool,
) -> bool:
    if destination.exists() and not overwrite:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    filter_graph = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps={fps}"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-vf",
        filter_graph,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(fps),
        "-movflags",
        "+faststart",
        str(destination),
    ]
    subprocess.run(command, check=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=PROJECT_DIR / "senas")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "senas_normalizadas",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    if input_dir == output_dir:
        print("La salida debe ser distinta de la carpeta original", file=sys.stderr)
        return 2
    if not input_dir.is_dir():
        print(f"No existe la carpeta de entrada: {input_dir}", file=sys.stderr)
        return 2

    ffmpeg = find_ffmpeg()
    converted = 0
    skipped = 0
    failed = 0
    for source in sorted(input_dir.glob("*.mp4")):
        destination = output_dir / source.name
        try:
            if normalize_video(
                ffmpeg,
                source,
                destination,
                width=args.width,
                height=args.height,
                fps=args.fps,
                overwrite=args.overwrite,
            ):
                converted += 1
            else:
                skipped += 1
        except subprocess.CalledProcessError:
            failed += 1
            print(f"Falló: {source.name}", file=sys.stderr)

    print(f"Convertidos={converted} Omitidos={skipped} Fallidos={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
