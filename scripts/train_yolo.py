from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a ProctorX YOLO11+ detector for person, phone, and paper.")
    parser.add_argument("--data", default="models/data/proctorx.yaml", help="Ultralytics data YAML.")
    parser.add_argument("--weights", default="yolo26n.pt", help="Base YOLO checkpoint. Use yolo11n.pt if YOLO26 is unavailable.")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--project", default="models/runs")
    parser.add_argument("--name", default="proctorx-yolo")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset YAML not found: {data_path}")

    model = YOLO(args.weights)
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        patience=20,
        cos_lr=True,
        close_mosaic=10,
    )


if __name__ == "__main__":
    main()
