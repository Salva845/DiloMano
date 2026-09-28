"""Valida el diccionario y los clips sin iniciar la interfaz."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from asset_catalog import AssetCatalog  # noqa: E402


def literal_duplicate_keys(path: Path) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    dictionary = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(target, "id", None) == "diccionario_senas" for target in node.targets)
    )
    if not isinstance(dictionary, ast.Dict):
        return {}
    keys = [ast.literal_eval(key) for key in dictionary.keys]
    return {key: count for key, count in Counter(keys).items() if count > 1}


def probe_videos(paths: list[str]) -> dict[str, str]:
    errors: dict[str, str] = {}
    try:
        import imageio.v2 as imageio
    except ImportError:
        return {"__dependency__": "imageio no está instalado"}
    for raw_path in paths:
        reader = None
        try:
            reader = imageio.get_reader(raw_path)
            metadata = reader.get_meta_data()
            fps = float(metadata.get("fps") or 0)
            if fps <= 0:
                errors[raw_path] = "FPS inválido o ausente"
        except Exception as exc:
            errors[raw_path] = str(exc)
        finally:
            if reader is not None:
                try:
                    reader.close()
                except Exception:
                    pass
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--probe-video", action="store_true")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    catalog = AssetCatalog(base_dir=PROJECT_DIR)
    report = catalog.report()
    report["literal_duplicate_keys"] = literal_duplicate_keys(
        PROJECT_DIR / "diccionario.py"
    )
    if args.probe_video:
        report["video_probe_errors"] = probe_videos(
            sorted({str(entry.video_path) for entry in catalog.valid_entries.values()})
        )

    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.json_out:
        args.json_out.write_text(serialized + "\n", encoding="utf-8")

    has_errors = bool(
        report["missing_entries"]
        or report["normalization_collisions"]
        or report["literal_duplicate_keys"]
        or report.get("video_probe_errors")
    )
    return 1 if args.strict and has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
