from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from backend.db.models import Alert, ExamSession, Student, utc_now
from backend.db.schemas import StudentRiskOut


def create_session(db: Session, source_type: str, source_name: str | None = None) -> ExamSession:
    session = ExamSession(source_type=source_type, source_name=source_name, start_time=utc_now(), status="running")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def finish_session(db: Session, session_id: int, status: str = "completed") -> None:
    exam_session = db.get(ExamSession, session_id)
    if exam_session is None:
        return
    exam_session.status = status
    exam_session.end_time = utc_now()
    db.commit()


def upsert_identity(db: Session, session_id: int, public_id: int, label: str) -> Student:
    student = db.get(Student, (public_id, session_id))
    now = utc_now()
    if student is None:
        student = Student(id=public_id, session_id=session_id, label=label, first_seen=now, last_seen=now)
        db.add(student)
    else:
        student.label = label
        student.last_seen = now
    db.commit()
    db.refresh(student)
    return student


def create_alert(
    db: Session,
    session_id: int,
    student_id: int | None,
    classification: str,
    activity_type: str,
    confidence: float,
    priority: str = "standard",
    details: str | None = None,
) -> Alert:
    alert = Alert(
        session_id=session_id,
        student_id=student_id,
        type=classification,
        activity_type=activity_type,
        confidence=float(confidence),
        timestamp=utc_now(),
        priority=priority,
        details=details,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_alerts_for_date(
    db: Session,
    selected_date: date,
    start_time: time | None = None,
    end_time: time | None = None,
    session_id: int | None = None,
    timezone_offset_minutes: int = 0,
) -> list[Alert]:
    offset = timedelta(minutes=timezone_offset_minutes)
    day_start = datetime.combine(selected_date, start_time or time.min).replace(tzinfo=timezone.utc) + offset
    day_end = datetime.combine(selected_date, end_time or time.max).replace(tzinfo=timezone.utc) + offset
    clauses = [Alert.timestamp >= day_start, Alert.timestamp <= day_end]
    if session_id is not None:
        clauses.append(Alert.session_id == session_id)
    stmt = select(Alert).where(and_(*clauses)).order_by(Alert.timestamp.desc())
    return list(db.scalars(stmt).all())


def get_recent_alerts(db: Session, session_id: int, limit: int = 30) -> list[Alert]:
    stmt = select(Alert).where(Alert.session_id == session_id).order_by(Alert.timestamp.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def count_students(db: Session, session_id: int) -> tuple[int, bool]:
    total_students = db.scalar(
        select(func.count(Student.id)).where(Student.session_id == session_id, Student.label == "Student")
    )
    invigilator_total = db.scalar(
        select(func.count(Student.id)).where(Student.session_id == session_id, Student.label == "Invigilator")
    )
    return int(total_students or 0), bool(invigilator_total)


def count_alert_types(db: Session, session_id: int) -> dict[str, int]:
    stmt = select(Alert.type, func.count(Alert.id)).where(Alert.session_id == session_id).group_by(Alert.type)
    return {row[0]: int(row[1]) for row in db.execute(stmt).all()}


def get_student_risk_scores(db: Session, session_id: int) -> list[StudentRiskOut]:
    students = list(
        db.scalars(select(Student).where(Student.session_id == session_id, Student.label == "Student").order_by(Student.id)).all()
    )
    risks: list[StudentRiskOut] = []
    for student in students:
        suspicious = int(
            db.scalar(
                select(func.count(Alert.id)).where(
                    Alert.session_id == session_id,
                    Alert.student_id == student.id,
                    Alert.type == "suspicious",
                )
            )
            or 0
        )
        malicious = int(
            db.scalar(
                select(func.count(Alert.id)).where(
                    Alert.session_id == session_id,
                    Alert.student_id == student.id,
                    Alert.type == "malicious",
                )
            )
            or 0
        )
        risks.append(
            StudentRiskOut(
                student_id=student.id,
                suspicious_count=suspicious,
                malicious_count=malicious,
                risk_score=min(100, suspicious * 15 + malicious * 35),
            )
        )
    return risks
