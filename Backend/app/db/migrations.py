"""Small idempotent upgrade for the original local database."""
from sqlalchemy import inspect, text
from app.db.base import Base
from app.models import Assignment


def initialize_database(engine):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if 'course_assignments' in tables:
        columns = {c['name'] for c in inspector.get_columns('course_assignments')}
        if 'session_id' not in columns:
            with engine.begin() as connection:
                if connection.execute(text('SELECT count(*) FROM course_assignments')).scalar():
                    raise RuntimeError('Legacy teacher assignments need a session mapping before upgrade. No assignments were changed.')
                # The legacy empty table has a different uniqueness constraint.
                Assignment.__table__.drop(connection)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        if 'courses' in tables and 'category' not in {c['name'] for c in inspector.get_columns('courses')}:
            connection.execute(text("ALTER TABLE courses ADD COLUMN category VARCHAR(30) NOT NULL DEFAULT 'core'"))
        if 'course_students' in tables and 'session_id' not in {c['name'] for c in inspector.get_columns('course_students')}:
            orphan_count = connection.execute(text('SELECT count(*) FROM course_students e LEFT JOIN students s ON s.student_id = e.student_id WHERE s.student_id IS NULL')).scalar()
            if orphan_count:
                raise RuntimeError('Legacy enrollments reference missing students. Repair those records before upgrade.')
            connection.execute(text('ALTER TABLE course_students ADD COLUMN session_id INTEGER REFERENCES academic_sessions(id)'))
            connection.execute(text('UPDATE course_students SET session_id = (SELECT session_id FROM students WHERE students.student_id = course_students.student_id)'))
    with engine.begin() as connection:
        marks_columns = {c['name'] for c in inspect(engine).get_columns('course_marks')}
        if 'revision' not in marks_columns:
            connection.execute(text('ALTER TABLE course_marks ADD COLUMN revision INTEGER NOT NULL DEFAULT 1'))
        duplicates = connection.execute(text("SELECT role, reference_id FROM users WHERE reference_id IS NOT NULL GROUP BY role, reference_id HAVING count(*) > 1")).first()
        if duplicates:
            raise RuntimeError('Duplicate login accounts reference the same person. Resolve duplicate accounts before upgrading; no accounts were deleted.')
        connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_users_role_reference ON users (role, reference_id)'))
    Base.metadata.create_all(engine)
