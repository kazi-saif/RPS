from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from app.db.base import Base

class Department(Base):
    __tablename__ = 'departments'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

class AcademicSession(Base):
    __tablename__ = 'academic_sessions'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

class Teacher(Base):
    __tablename__ = 'teachers'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(String(30), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(254), unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    course_code = Column(String(30), unique=True, nullable=False)
    course_name = Column(String(100), nullable=False)
    credit = Column(Float, nullable=False)
    semester = Column(Integer, nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    category = Column(String(30), nullable=False, default='core')
    __table_args__ = (CheckConstraint("category IN ('core', 'optional theory', 'optional lab')"), CheckConstraint('credit > 0'), CheckConstraint('semester BETWEEN 1 AND 8'))

class Assignment(Base):
    __tablename__ = 'course_assignments'
    id = Column(Integer, primary_key=True)
    course_code = Column(String, ForeignKey('courses.course_code'), nullable=False)
    teacher_code = Column(String, ForeignKey('teachers.teacher_id'), nullable=False)
    session_id = Column(Integer, ForeignKey('academic_sessions.id'), nullable=False)
    __table_args__ = (UniqueConstraint('course_code', 'teacher_code', 'session_id'),)

class Enrollment(Base):
    __tablename__ = 'course_students'
    id = Column(Integer, primary_key=True)
    student_id = Column(String, ForeignKey('students.student_id'), nullable=False)
    course_code = Column(String, ForeignKey('courses.course_code'), nullable=False)
    semester = Column(Integer, nullable=False)
    session_id = Column(Integer, ForeignKey('academic_sessions.id'), nullable=False)
    __table_args__ = (UniqueConstraint('student_id', 'course_code', 'semester'),)

class Marks(Base):
    __tablename__ = 'course_marks'
    id = Column(Integer, primary_key=True)
    enrollment_id = Column(Integer, ForeignKey('course_students.id', ondelete='CASCADE'), unique=True, nullable=False)
    assignment_marks = Column(Float, nullable=False)
    class_test_marks = Column(Float, nullable=False)
    midterm_marks = Column(Float, nullable=False)
    final_marks = Column(Float, nullable=False)
    published = Column(Boolean, nullable=False, default=False)
    revision = Column(Integer, nullable=False, default=1, server_default='1')
    __table_args__ = (CheckConstraint('assignment_marks BETWEEN 0 AND 10'), CheckConstraint('class_test_marks BETWEEN 0 AND 20'), CheckConstraint('midterm_marks BETWEEN 0 AND 40'), CheckConstraint('final_marks BETWEEN 0 AND 80'))

class Cohort(Base):
    __tablename__ = 'cohorts'
    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    session_id = Column(Integer, ForeignKey('academic_sessions.id'), nullable=False)
    current_semester = Column(Integer, nullable=False)
    processing_semester = Column(Integer, nullable=False)
    automatic_core = Column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint('department_id', 'session_id'), CheckConstraint('current_semester BETWEEN 1 AND 8'), CheckConstraint('processing_semester BETWEEN 1 AND current_semester'))
