from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Student(Base):
    __tablename__ = 'students'
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey('departments.id'))
    session_id: Mapped[int] = mapped_column(ForeignKey('academic_sessions.id'))
