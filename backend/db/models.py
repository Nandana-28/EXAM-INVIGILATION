from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExamSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    source_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")

    students: Mapped[list["Student"]] = relationship(back_populates="session")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="session")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    session: Mapped[ExamSession] = relationship(back_populates="students")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(96), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    details: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    session: Mapped[ExamSession] = relationship(back_populates="alerts")
