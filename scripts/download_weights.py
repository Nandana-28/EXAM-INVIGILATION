from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    run_dir = Path("backend/runs/ultralytics").resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(run_dir))

    from ultralytics import YOLO

    for weights in ("yolo26n.pt", "yolo11n.pt"):
        print(f"Downloading or validating {weights}...")
        YOLO(weights)


if __name__ == "__main__":
    main()
