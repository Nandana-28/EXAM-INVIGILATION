from __future__ import annotations

import shutil
import json
from contextlib import asynccontextmanager
from datetime import date, time
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db import repository
from backend.db.base import get_db, init_db
from backend.db.schemas import AlertOut, ResultsOut, StartResponse, StateOut
from backend.services.session_manager import SessionManager

settings = get_settings()
manager = SessionManager(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dir / "assets"), name="assets")
    app.mount("/static", StaticFiles(directory=settings.frontend_dir), name="frontend-static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    index_path = settings.frontend_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend is not available.")
    return FileResponse(index_path)


@app.get("/health")
def health() -> dict[str, str | bool | None]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "model": manager.detector.weights_loaded,
    }


@app.post("/upload_video", response_model=StartResponse)
async def upload_video(file: UploadFile = File(...)) -> StartResponse:
    suffix = Path(file.filename or "exam_video.mp4").suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        raise HTTPException(status_code=400, detail="Upload a supported video file: mp4, avi, mov, mkv, or webm.")

    target = settings.upload_dir / f"{uuid4().hex}{suffix}"
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = manager.start_upload(target)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return StartResponse(session_id=result.session_id or 0, status=result.status, message="Uploaded video processing started.")


@app.post("/start_live", response_model=StartResponse)
def start_live() -> StartResponse:
    try:
        result = manager.start_live()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return StartResponse(session_id=result.session_id or 0, status=result.status, message="Live monitoring started.")


@app.post("/stop_session", response_model=ResultsOut)
def stop_session() -> ResultsOut:
    return manager.stop()


@app.get("/get_results", response_model=ResultsOut)
def get_results() -> ResultsOut:
    return manager.get_results()


@app.get("/model_metrics")
def model_metrics() -> dict:
    metrics_path = Path("models/evaluation/proctorx_metrics.json")
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="Model metrics file is not available.")
    return json.loads(metrics_path.read_text(encoding="utf-8"))


@app.get("/get_logs_by_date", response_model=list[AlertOut])
def get_logs_by_date(
    selected_date: date = Query(..., alias="date"),
    start_time: time | None = Query(default=None),
    end_time: time | None = Query(default=None),
    session_id: int | None = Query(default=None),
    timezone_offset_minutes: int = Query(default=0),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    alerts = repository.get_alerts_for_date(
        db,
        selected_date=selected_date,
        start_time=start_time,
        end_time=end_time,
        session_id=session_id,
        timezone_offset_minutes=timezone_offset_minutes,
    )
    return [AlertOut.model_validate(alert) for alert in alerts]


@app.get("/state", response_model=StateOut)
def state() -> StateOut:
    return manager.get_state()


@app.get("/video_feed")
def video_feed() -> StreamingResponse:
    return StreamingResponse(manager.mjpeg_stream(), media_type="multipart/x-mixed-replace; boundary=frame")
