# ProctorX - AI Smart Exam Invigilation System

ProctorX is a FastAPI, PostgreSQL, OpenCV, PyTorch, and Ultralytics YOLO-based exam invigilation platform with a clean campus dashboard. It supports uploaded videos and live webcam sessions, stable student IDs, invigilator separation, paper-passing heatmaps, high-confidence phone/paper alerts, date/time log filtering, and final-only analytics.

## Project Structure

```text
.
├── backend/
│   ├── main.py                         # FastAPI app and required endpoints
│   ├── core/config.py                  # Environment-driven runtime settings
│   ├── db/
│   │   ├── base.py                     # SQLAlchemy engine/session/bootstrap
│   │   ├── models.py                   # PostgreSQL ORM tables
│   │   ├── repository.py               # Session, student, alert, log, risk queries
│   │   └── schemas.py                  # API response models
│   ├── ml/
│   │   ├── detector.py                 # YOLO26/YOLO11 model integration
│   │   ├── tracker.py                  # Modified ByteTrack-style locked ID tracker
│   │   ├── rules.py                    # Phone, paper, exchange alert rules
│   │   ├── visualizer.py               # Boxes, labels, paper-passing heatmap overlay
│   │   ├── geometry.py                 # Bounding-box utilities
│   │   └── types.py                    # Shared dataclasses
│   └── services/
│       ├── session_manager.py          # Live/upload session lifecycle and MJPEG state
│       └── video_processor.py          # Frame loop, DB logging, final summaries
├── frontend/
│   ├── index.html                      # Landing page and ProctorX dashboard
│   ├── styles.css                      # Clean institutional UI styling
│   ├── app.js                          # Upload/live/log/analytics interactions
│   └── assets/campus-exam-hero.png     # Generated landing image
├── models/
│   ├── README.md                       # Dataset and custom-weight guidance
│   └── data/proctorx.yaml              # YOLO class config: person, phone, paper
├── scripts/train_yolo.py               # Custom YOLO training entrypoint
├── schema.sql                          # PostgreSQL schema
├── docker-compose.yml                  # PostgreSQL service
├── requirements.txt                    # Python dependencies
└── .env.example                        # Runtime configuration template
```

## Core Behavior

- Students are created only from `person` detections.
- Student public IDs start at `2`.
- The invigilator, when detected, is locked to ID `1`, labeled separately, excluded from cheating alerts, and drawn in red.
- Students are drawn in green as `Student ID: X`.
- The tracker never recycles public IDs and never moves a locked public ID to another active identity.
- Cheating alerts are emitted only at confidence `>= 80%`.
- Alert-producing objects are restricted to phone and paper/document signals.
- Body pose estimation is not used.
- Paper passing creates a high-priority malicious alert and a heat gradient between the involved students.
- The dashboard graph is final output only. It is drawn after `STOP` or video completion.

## Required API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/upload_video` | Upload a video and start processing |
| `POST` | `/start_live` | Start webcam processing |
| `POST` | `/stop_session` | Stop immediately and freeze final analytics |
| `GET` | `/get_results` | Return final/current summary and student risk scores |
| `GET` | `/get_logs_by_date` | Return logs for a selected date and optional time range |

Additional dashboard endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/video_feed` | MJPEG stream with boxes , IDs, and heatmaps |
| `GET` | `/state` | Polling state for alerts and session status |
| `GET` | `/health` | Service/model health check |

## Database Schema

The PostgreSQL schema is in `schema.sql` and contains:

- `students`: `id`, `session_id`, `label`, `first_seen`, `last_seen`
- `alerts`: `id`, `session_id`, `student_id`, `type`, `activity_type`, `confidence`, `timestamp`, `priority`, `details`
- `sessions`: `id`, `source_type`, `source_name`, `start_time`, `end_time`, `status`

`students.id` is the displayed ProctorX identity. It is composite-keyed with `session_id` so every exam can reuse Student `2`, Student `3`, and Invigilator `1` cleanly.

## Setup

1. Create the environment file:

```powershell
Copy-Item .env.example .env
```

2. Start PostgreSQL:

```powershell
docker compose up -d postgres
```

3. Create and activate a Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Start ProctorX:

```powershell
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

5. Open the dashboard:

```text
http://127.0.0.1:8000
```

## Model Training

Prepare a YOLO-format dataset under `datasets/proctorx`:

```text
datasets/proctorx/
├── images/train
├── images/val
├── images/test
├── labels/train
├── labels/val
└── labels/test
```

Train:

```powershell
python scripts/train_yolo.py --data models/data/proctorx.yaml --weights yolo26n.pt --epochs 80 --imgsz 960 --device cpu
```

Use the trained model:

```env
MODEL_WEIGHTS=models/runs/proctorx-yolo/weights/best.pt
```

## Model Evaluation Graphs

The dashboard Analytics page includes:

- `ProctorX - Model Training Curves`
- `Confusion Matrix`
- `Compare Models`

The demo graph data is stored in:

```text
models/evaluation/proctorx_metrics.json
```

After real training, replace those values with your actual validation metrics. To export the same graphs as PNG files for a report:

```powershell
python scripts/export_model_graphs.py
```

Output files are written to:

```text
reports/model_evaluation/
```

For GPU:

```powershell
python scripts/train_yolo.py --device 0
```

## Production Notes

- For real exam deployments, replace the default public checkpoint with a custom trained checkpoint for `person`, `phone`, and `paper`.
- For stronger identity locking under heavy occlusion, add camera calibration and enrollment-time appearance snapshots. The current tracker already avoids public ID reassignment and ID recycling.
- Use a supervised validation set from the target exam room to tune `DETECTION_CONFIDENCE`, `ALERT_CONFIDENCE_THRESHOLD`, and `ALERT_COOLDOWN_SECONDS`.
