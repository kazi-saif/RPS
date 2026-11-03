"""Keep fixed core enrollments in sync without creating marks or choosing electives."""
from sqlalchemy import select
from app.models import Cohort, Student, Course, Enrollment


def sync_fixed_curriculum(db):
    db.flush()
    created = 0
    for cohort in db.scalars(select(Cohort).where(Cohort.automatic_core.is_(True))):
        students = list(db.scalars(select(Student).where(Student.department_id == cohort.department_id, Student.session_id == cohort.session_id)))
        courses = list(db.scalars(select(Course).where(Course.department_id == cohort.department_id, Course.category == 'core')))
        existing = set(db.execute(select(Enrollment.student_id, Enrollment.course_code).where(Enrollment.session_id == cohort.session_id)).all())
        for student in students:
            for course in courses:
                if (student.student_id, course.course_code) not in existing:
                    db.add(Enrollment(student_id=student.student_id, course_code=course.course_code, semester=course.semester, session_id=cohort.session_id))
                    created += 1
    return created
