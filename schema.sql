CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(32) NOT NULL DEFAULT 'upload',
    source_name VARCHAR(512),
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    label VARCHAR(32) NOT NULL CHECK (label IN ('Student', 'Invigilator')),
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, session_id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id INTEGER,
    type VARCHAR(32) NOT NULL CHECK (type IN ('normal', 'suspicious', 'malicious')),
    activity_type VARCHAR(96) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    priority VARCHAR(32) NOT NULL DEFAULT 'standard',
    details VARCHAR(1024)
);

CREATE INDEX IF NOT EXISTS ix_students_session_id ON students(session_id);
CREATE INDEX IF NOT EXISTS ix_alerts_session_id ON alerts(session_id);
CREATE INDEX IF NOT EXISTS ix_alerts_student_id ON alerts(student_id);
CREATE INDEX IF NOT EXISTS ix_alerts_type ON alerts(type);
CREATE INDEX IF NOT EXISTS ix_alerts_timestamp ON alerts(timestamp);
