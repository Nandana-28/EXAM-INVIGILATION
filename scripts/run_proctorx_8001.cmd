@echo off
cd /d "%~dp0.."
set DATABASE_URL=sqlite:///backend/runs/proctorx-local.db
set YOLO_CONFIG_DIR=%CD%\backend\runs\ultralytics
".\.venv\Scripts\python.exe" -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
