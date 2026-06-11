from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "models" / "evaluation" / "proctorx_metrics.json"
OUTPUT_DIR = ROOT / "reports" / "model_evaluation"


def load_metrics() -> dict:
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def export_training_curves(metrics: dict) -> None:
    curves = metrics["training_curves"]
    epochs = curves["epochs"]

    plt.figure(figsize=(11, 5.5), dpi=160)
    plt.plot(epochs, curves["train_box_loss"], marker="o", linewidth=2.2, label="Train Box Loss")
    plt.plot(epochs, curves["val_box_loss"], marker="o", linewidth=2.2, label="Val Box Loss")
    plt.plot(epochs, curves["map50"], marker="o", linewidth=2.2, label="mAP50")
    plt.plot(epochs, curves["precision"], marker="o", linewidth=2.2, label="Precision")
    plt.plot(epochs, curves["recall"], marker="o", linewidth=2.2, label="Recall")
    plt.title("ProctorX - Model Training Curves", weight="bold")
    plt.xlabel("Epoch")
    plt.ylabel("Score / Loss")
    plt.grid(True, alpha=0.25)
    plt.legend(ncol=3, frameon=False)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "training_curves.png")
    plt.close()


def export_confusion_matrix(metrics: dict) -> None:
    confusion = metrics["confusion_matrix"]
    labels = confusion["labels"]
    matrix = np.array(confusion["matrix"])

    plt.figure(figsize=(7.2, 6.2), dpi=160)
    plt.imshow(matrix, cmap="YlGnBu")
    plt.title("ProctorX - Confusion Matrix", weight="bold")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.xticks(range(len(labels)), labels, rotation=30, ha="right")
    plt.yticks(range(len(labels)), labels)
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = int(matrix[row, col])
            color = "white" if value > matrix.max() * 0.55 else "#17202a"
            plt.text(col, row, str(value), ha="center", va="center", color=color, weight="bold")
    plt.colorbar(fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "confusion_matrix.png")
    plt.close()


def export_model_comparison(metrics: dict) -> None:
    rows = metrics["model_comparison"]
    names = [row["model"].replace(" + Locked ByteTrack", "") for row in rows]
    x = np.arange(len(names))
    width = 0.22

    plt.figure(figsize=(10.5, 5.6), dpi=160)
    plt.bar(x - width, [row["map50"] for row in rows], width, label="mAP50")
    plt.bar(x, [row["event_f1"] for row in rows], width, label="Event F1")
    plt.bar(x + width, [row["id_stability"] for row in rows], width, label="ID Stability")
    plt.title("ProctorX - Compare Models", weight="bold")
    plt.ylabel("Score")
    plt.ylim(0, 1.05)
    plt.xticks(x, names, rotation=10, ha="right")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "compare_models.png")
    plt.close()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = load_metrics()
    export_training_curves(metrics)
    export_confusion_matrix(metrics)
    export_model_comparison(metrics)
    print(f"Exported graphs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
