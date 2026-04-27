from datetime import date, datetime, time

from pydantic import BaseModel, Field


class AlertOut(BaseModel):
    id: int
    session_id: int
    student_id: int | None
    type: str
    activity_type: str
    confidence: float
    timestamp: datetime
    priority: str
    details: str | None = None

    model_config = {"from_attributes": True}


class LogFilter(BaseModel):
    selected_date: date
    start_time: time | None = None
    end_time: time | None = None


class SessionOut(BaseModel):
    id: int
    source_type: str
    source_name: str | None
    start_time: datetime
    end_time: datetime | None
    status: str

    model_config = {"from_attributes": True}


class StudentRiskOut(BaseModel):
    student_id: int
    risk_score: int
    suspicious_count: int = 0
    malicious_count: int = 0


class ResultsOut(BaseModel):
    session_id: int | None
    status: str
    total_normal: int = 0
    total_suspicious: int = 0
    total_malicious: int = 0
    total_students: int = 0
    invigilator_detected: bool = False
    processed_frames: int = 0
    started_at: datetime | None = None
    ended_at: datetime | None = None
    student_risk_scores: list[StudentRiskOut] = Field(default_factory=list)
    message: str = "No session has been processed yet."


class StartResponse(BaseModel):
    session_id: int
    status: str
    message: str


class StateOut(BaseModel):
    active: bool
    session_id: int | None
    status: str
    latest_alerts: list[AlertOut] = Field(default_factory=list)
    results: ResultsOut
    error: str | None = None
