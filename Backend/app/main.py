
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine, SessionLocal

app = FastAPI(
    title="Result Processing System",
    description="University Result Processing System API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:5500",
        "http://0.0.0.0:5000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


class StudentCreate(BaseModel):
    student_id: str
    name: str
    email: EmailStr


class StudentUpdate(BaseModel):
    name: str
    email: EmailStr


class CourseCreate(BaseModel):
    course_code: str
    course_name: str
    credit: float
    semester: int


class CourseUpdate(BaseModel):
    course_code: str
    course_name: str
    credit: float
    semester: int


class TeacherCreate(BaseModel):
    teacher_id: str
    name: str
    email: EmailStr


class TeacherUpdate(BaseModel):
    name: str
    email: EmailStr


class CourseAssignmentCreate(BaseModel):
    course_code: str
    teacher_code: str




@app.get("/")
def home():
    return {
        "message": "Result Processing System API",
        "status": "runningc",
    }


@app.get("/students")
def get_students():
    with engine.connect() as connection:
        result = connection.execute(
            text(
                "SELECT id, student_id, name, email "
                "FROM students ORDER BY id"
            )
        )
        students = [dict(row._mapping) for row in result]

    return {"students": students}


@app.post("/students", status_code=201)
def create_student(student: StudentCreate):
    query = text(
        """
        INSERT INTO students (student_id, name, email)
        VALUES (:student_id, :name, :email)
        RETURNING id, student_id, name, email
        """
    )

    try:
        with engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "student_id": student.student_id,
                    "name": student.name,
                    "email": str(student.email),
                },
            )
            new_student = dict(result.fetchone()._mapping)

        return new_student

    except Exception as error:
        from sqlalchemy.exc import IntegrityError

        if isinstance(error, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="Student ID or email already exists",
            ) from error

        raise



@app.put("/students/{student_id}")
def update_student(student_id: str, student: StudentUpdate):
    query = text(
        """
        UPDATE students
        SET name = :name, email = :email
        WHERE student_id = :student_id
        RETURNING id, student_id, name, email
        """
    )

    try:
        with engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "student_id": student_id,
                    "name": student.name,
                    "email": str(student.email),
                },
            )

            updated_student = result.fetchone()

            if updated_student is None:
                raise HTTPException(
                    status_code=404,
                    detail="Student not found",
                )

            return dict(updated_student._mapping)

    except HTTPException:
        raise

    except Exception as error:
        from sqlalchemy.exc import IntegrityError

        if isinstance(error, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="Email already exists",
            ) from error

        raise




@app.delete("/students/{student_id}")
def delete_student(student_id: str):
    db = SessionLocal()

    try:
        result = db.execute(
            text("""
                DELETE FROM students
                WHERE student_id = :student_id
                RETURNING id, student_id, name, email
            """),
            {"student_id": student_id}
        )

        deleted_student = result.mappings().first()

        if deleted_student is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

        db.commit()

        return {
            "message": "Student deleted successfully",
            "student": dict(deleted_student)
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()





@app.get("/courses")
def get_courses():
    query = text("""
        SELECT id, course_code, course_name, credit, semester
        FROM courses
        ORDER BY semester, course_code
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        courses = [dict(row._mapping) for row in result]

    return {"courses": courses}



# courese work

@app.post("/courses", status_code=201)
def create_course(course: CourseCreate):

    query = text("""
        INSERT INTO courses (
            course_code,
            course_name,
            credit,
            semester
        )
        VALUES (
            :course_code,
            :course_name,
            :credit,
            :semester
        )
        RETURNING id, course_code, course_name, credit, semester
    """)

    try:
        with engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "course_code": course.course_code,
                    "course_name": course.course_name,
                    "credit": course.credit,
                    "semester": course.semester,
                },
            )

            new_course = dict(result.fetchone()._mapping)

        return new_course

    except Exception as error:
        from sqlalchemy.exc import IntegrityError

        if isinstance(error, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="Course code already exists or course data is invalid"
            ) from error

        raise


#pur api for course

@app.put("/courses/{course_id}")
def update_course(course_id: int, course: CourseUpdate):

    query = text("""
        UPDATE courses
        SET
            course_code = :course_code,
            course_name = :course_name,
            credit = :credit,
            semester = :semester
        WHERE id = :course_id
        RETURNING id, course_code, course_name, credit, semester
    """)

    try:
        with engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "course_id": course_id,
                    "course_code": course.course_code,
                    "course_name": course.course_name,
                    "credit": course.credit,
                    "semester": course.semester,
                },
            )

            updated_course = result.fetchone()

            if updated_course is None:
                raise HTTPException(
                    status_code=404,
                    detail="Course not found"
                )

            return dict(updated_course._mapping)

    except Exception as error:
        from sqlalchemy.exc import IntegrityError

        if isinstance(error, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="Course code already exists or course data is invalid"
            ) from error

        raise


@app.delete("/courses/{course_id}")
def delete_course(course_id: int):

    query = text("""
        DELETE FROM courses
        WHERE id = :course_id
        RETURNING id, course_code, course_name
    """)

    with engine.begin() as connection:
        result = connection.execute(
            query,
            {"course_id": course_id}
        )

        deleted_course = result.fetchone()

        if deleted_course is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found"
            )

    return {
        "message": "Course deleted successfully",
        "course": dict(deleted_course._mapping)
    }

# teacher post api

@app.post("/teachers", status_code=201)
def create_teacher(teacher: TeacherCreate):

    query = text("""
        INSERT INTO teachers (
            teacher_id,
            name,
            email
        )
        VALUES (
            :teacher_id,
            :name,
            :email
        )
        RETURNING id, teacher_id, name, email
    """)

    try:
        with engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "teacher_id": teacher.teacher_id,
                    "name": teacher.name,
                    "email": teacher.email,
                },
            )

            new_teacher = dict(result.fetchone()._mapping)

        return new_teacher

    except Exception as error:
        from sqlalchemy.exc import IntegrityError

        if isinstance(error, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="Teacher ID or email already exists"
            ) from error

        raise

@app.get("/teachers")
def get_teachers():

    query = text("""
        SELECT id, teacher_id, name, email
        FROM teachers
        ORDER BY id
    """)

    with engine.connect() as connection:
        result = connection.execute(query)

        teachers = [
            dict(row._mapping)
            for row in result
        ]

    return {"teachers": teachers}

@app.put("/teachers/{teacher_id}")
def update_teacher(teacher_id: int, teacher: TeacherUpdate):

    query = text("""
        UPDATE teachers
        SET
            name = :name,
            email = :email
        WHERE id = :teacher_id
        RETURNING id, teacher_id, name, email
    """)

    try:
        with engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "teacher_id": teacher_id,
                    "name": teacher.name,
                    "email": teacher.email,
                },
            )

            updated_teacher = result.fetchone()

            if updated_teacher is None:
                raise HTTPException(
                    status_code=404,
                    detail="Teacher not found"
                )

            return dict(updated_teacher._mapping)

    except Exception as error:
        from sqlalchemy.exc import IntegrityError

        if isinstance(error, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="Email already exists"
            ) from error

        raise

@app.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int):

    query = text("""
        DELETE FROM teachers
        WHERE id = :teacher_id
        RETURNING id, teacher_id, name, email
    """)

    with engine.begin() as connection:
        result = connection.execute(
            query,
            {"teacher_id": teacher_id}
        )

        deleted_teacher = result.fetchone()

        if deleted_teacher is None:
            raise HTTPException(
                status_code=404,
                detail="Teacher not found"
            )

    return {
        "message": "Teacher deleted successfully",
        "teacher": dict(deleted_teacher._mapping)
    }


@app.post("/course-assignments", status_code=201)
def create_course_assignment(assignment: CourseAssignmentCreate):

    query = text("""
        INSERT INTO course_assignments (
            course_code,
            teacher_code
        )
        VALUES (
            :course_code,
            :teacher_code
        )
        RETURNING id, course_code, teacher_code, assigned_at
    """)

    try:
        with engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "course_code": assignment.course_code,
                    "teacher_code": assignment.teacher_code,
                },
            )

            new_assignment = dict(result.fetchone()._mapping)

        return new_assignment

    except Exception as error:
        from sqlalchemy.exc import IntegrityError

        if isinstance(error, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="Invalid course/teacher or assignment already exists"
            ) from error

        raise

@app.get("/course-assignments")
def get_course_assignments():

    query = text("""
        SELECT
            id,
            course_code,
            teacher_code,
            assigned_at
        FROM course_assignments
        ORDER BY id
    """)

    with engine.connect() as connection:
        result = connection.execute(query)

        assignments = [
            dict(row._mapping)
            for row in result
        ]

    return {"assignments": assignments}


@app.delete("/course-assignments/{assignment_id}")
def delete_course_assignment(assignment_id: int):

    query = text("""
        DELETE FROM course_assignments
        WHERE id = :assignment_id
    """)

    with engine.begin() as connection:
        result = connection.execute(
            query,
            {"assignment_id": assignment_id}
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Course assignment not found"
            )

    return {
        "message": "Course assignment deleted successfully"
    }




@app.get("/teacher-courses/{teacher_code}")
def get_teacher_courses(teacher_code: str):

    query = text("""
        SELECT
            c.course_code,
            c.course_name,
            c.credit,
            c.semester
        FROM course_assignments ca
        JOIN courses c
            ON ca.course_code = c.course_code
        WHERE ca.teacher_code = :teacher_code
        ORDER BY c.semester, c.course_code
    """)

    with engine.connect() as connection:
        result = connection.execute(
            query,
            {"teacher_code": teacher_code}
        )

        courses = [
            dict(row._mapping)
            for row in result
        ]

    return {"courses": courses}


@app.get("/teacher-courses/{teacher_code}/{course_code}/students")
def get_course_students(teacher_code: str, course_code: str):

    with engine.connect() as connection:

        # Check whether this teacher is assigned to this course
        assignment_query = text("""
            SELECT 1
            FROM course_assignments
            WHERE teacher_code = :teacher_code
            AND course_code = :course_code
        """)

        assignment = connection.execute(
            assignment_query,
            {
                "teacher_code": teacher_code,
                "course_code": course_code
            }
        ).first()

        if not assignment:
            raise HTTPException(
                status_code=403,
                detail="You are not assigned to this course"
            )

        # Get enrolled students
        students_query = text("""
            SELECT
                s.student_id,
                s.name,
                s.email
            FROM course_students cs
            JOIN students s
                ON cs.student_id = s.student_id
            JOIN courses c
                ON cs.course_code = c.course_code
            WHERE cs.course_code = :course_code
            AND cs.semester = c.semester
            ORDER BY s.student_id
        """)

        result = connection.execute(
            students_query,
            {"course_code": course_code}
        )

        students = [
            dict(row._mapping)
            for row in result
        ]

    return {
        "course_code": course_code,
        "students": students
    }






class MarksCreate(BaseModel):
    assignment_marks: float = 0
    class_test_marks: float = 0
    midterm_marks: float = 0
    final_marks: float = 0


def calculate_grade(total_marks):
    percentage = (total_marks / 150) * 100

    if percentage >= 80:
        return "A+", 4.00
    elif percentage >= 75:
        return "A", 3.75
    elif percentage >= 70:
        return "A-", 3.50
    elif percentage >= 65:
        return "B+", 3.25
    elif percentage >= 60:
        return "B", 3.00
    elif percentage >= 55:
        return "B-", 2.75
    elif percentage >= 50:
        return "C+", 2.50
    elif percentage >= 45:
        return "C", 2.25
    elif percentage >= 40:
        return "D", 2.00
    else:
        return "F", 0.00


@app.get("/teacher-courses/{teacher_code}/{course_code}/marks")
def get_course_marks(teacher_code: str, course_code: str):

    with engine.connect() as connection:

        # Check teacher assignment
        assignment = connection.execute(
            text("""
                SELECT 1
                FROM course_assignments
                WHERE teacher_code = :teacher_code
                AND course_code = :course_code
            """),
            {
                "teacher_code": teacher_code,
                "course_code": course_code
            }
        ).first()

        if not assignment:
            raise HTTPException(
                status_code=403,
                detail="You are not assigned to this course"
            )

        # Get students and their marks
        result = connection.execute(
            text("""
                SELECT
                    s.student_id,
                    s.name,
                    cm.assignment_marks,
                    cm.class_test_marks,
                    cm.midterm_marks,
                    cm.final_marks,
                    cm.total_marks,
                    cm.grade,
                    cm.grade_point
                FROM course_students cs
                JOIN students s
                    ON cs.student_id = s.student_id
                JOIN courses c
                    ON cs.course_code = c.course_code
                LEFT JOIN course_marks cm
                    ON cm.student_id = cs.student_id
                    AND cm.course_code = cs.course_code
                    AND cm.semester = cs.semester
                WHERE cs.course_code = :course_code
                AND cs.semester = c.semester
                ORDER BY s.student_id
            """),
            {"course_code": course_code}
        )

        students = [
            dict(row._mapping)
            for row in result
        ]

    return {
        "course_code": course_code,
        "students": students
    }


@app.post(
    "/teacher-courses/{teacher_code}/{course_code}/marks/{student_id}"
)
def save_course_marks(
    teacher_code: str,
    course_code: str,
    student_id: str,
    marks: MarksCreate
):

    # Validate individual marks
    if not 0 <= marks.assignment_marks <= 10:
        raise HTTPException(400, "Assignment marks must be between 0 and 10")

    if not 0 <= marks.class_test_marks <= 20:
        raise HTTPException(400, "Class Test marks must be between 0 and 20")

    if not 0 <= marks.midterm_marks <= 40:
        raise HTTPException(400, "Midterm marks must be between 0 and 40")

    if not 0 <= marks.final_marks <= 80:
        raise HTTPException(400, "Final marks must be between 0 and 80")

    total = round(
        marks.assignment_marks
        + marks.class_test_marks
        + marks.midterm_marks
        + marks.final_marks,
        2
    )

    grade, grade_point = calculate_grade(total)

    with engine.begin() as connection:

        # Check teacher assignment and get course semester
        assignment = connection.execute(
            text("""
                SELECT c.semester
                FROM course_assignments ca
                JOIN courses c
                    ON ca.course_code = c.course_code
                WHERE ca.teacher_code = :teacher_code
                AND ca.course_code = :course_code
            """),
            {
                "teacher_code": teacher_code,
                "course_code": course_code
            }
        ).first()

        if not assignment:
            raise HTTPException(
                status_code=403,
                detail="You are not assigned to this course"
            )

        semester = assignment.semester

        # Check student enrollment
        enrollment = connection.execute(
            text("""
                SELECT 1
                FROM course_students
                WHERE student_id = :student_id
                AND course_code = :course_code
                AND semester = :semester
            """),
            {
                "student_id": student_id,
                "course_code": course_code,
                "semester": semester
            }
        ).first()

        if not enrollment:
            raise HTTPException(
                status_code=404,
                detail="Student is not enrolled in this course"
            )

        # Insert new marks or update existing marks
        result = connection.execute(
            text("""
                INSERT INTO course_marks (
                    student_id,
                    course_code,
                    semester,
                    assignment_marks,
                    class_test_marks,
                    midterm_marks,
                    final_marks,
                    total_marks,
                    grade,
                    grade_point,
                    updated_at
                )
                VALUES (
                    :student_id,
                    :course_code,
                    :semester,
                    :assignment_marks,
                    :class_test_marks,
                    :midterm_marks,
                    :final_marks,
                    :total_marks,
                    :grade,
                    :grade_point,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (student_id, course_code, semester)
                DO UPDATE SET
                    assignment_marks = EXCLUDED.assignment_marks,
                    class_test_marks = EXCLUDED.class_test_marks,
                    midterm_marks = EXCLUDED.midterm_marks,
                    final_marks = EXCLUDED.final_marks,
                    total_marks = EXCLUDED.total_marks,
                    grade = EXCLUDED.grade,
                    grade_point = EXCLUDED.grade_point,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING
                    student_id,
                    course_code,
                    semester,
                    assignment_marks,
                    class_test_marks,
                    midterm_marks,
                    final_marks,
                    total_marks,
                    grade,
                    grade_point
            """),
            {
                "student_id": student_id,
                "course_code": course_code,
                "semester": semester,
                "assignment_marks": marks.assignment_marks,
                "class_test_marks": marks.class_test_marks,
                "midterm_marks": marks.midterm_marks,
                "final_marks": marks.final_marks,
                "total_marks": total,
                "grade": grade,
                "grade_point": grade_point
            }
        )

        saved_marks = dict(result.first()._mapping)

    return {
        "message": "Marks saved successfully",
        "marks": saved_marks
    }


# ================================
# STUDENT RESULT API
# ================================

@app.get("/student-results/{student_id}")
def get_student_results(student_id: str):

    with engine.connect() as connection:

        # Check student
        student = connection.execute(
            text("""
                SELECT student_id, name, email
                FROM students
                WHERE student_id = :student_id
            """),
            {"student_id": student_id}
        ).mappings().first()

        if not student:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

        # Get all course results
        result = connection.execute(
            text("""
                SELECT
                    cs.semester,
                    c.course_code,
                    c.course_name,
                    c.credit,
                    cm.assignment_marks,
                    cm.class_test_marks,
                    cm.midterm_marks,
                    cm.final_marks,
                    cm.total_marks,
                    cm.grade,
                    cm.grade_point
                FROM course_students cs
                JOIN courses c
                    ON cs.course_code = c.course_code
                LEFT JOIN course_marks cm
                    ON cs.student_id = cm.student_id
                    AND cs.course_code = cm.course_code
                    AND cs.semester = cm.semester
                WHERE cs.student_id = :student_id
                ORDER BY cs.semester, c.course_code
            """),
            {"student_id": student_id}
        ).mappings().all()

    # Organize results semester-wise
    semesters = {}

    total_weighted_points = 0
    total_credits = 0

    for row in result:

        semester = row["semester"]

        if semester not in semesters:
            semesters[semester] = {
                "semester": semester,
                "courses": [],
                "gpa": None,
                "total_credits": 0,
                "weighted_points": 0
            }

        course = dict(row)

        # Add course to semester
        semesters[semester]["courses"].append(course)

        # Calculate GPA only for courses with saved marks
        if row["grade_point"] is not None and row["total_marks"] is not None:

            credit = float(row["credit"])
            grade_point = float(row["grade_point"])

            semesters[semester]["total_credits"] += credit

            semesters[semester]["weighted_points"] += (
                credit * grade_point
            )

            total_credits += credit
            total_weighted_points += credit * grade_point

    # Calculate semester GPA
    for semester_data in semesters.values():

        credits = semester_data["total_credits"]

        if credits > 0:
            semester_data["gpa"] = round(
                semester_data["weighted_points"] / credits,
                2
            )

        semester_data.pop("weighted_points")

    # Calculate overall CGPA
    cgpa = None

    if total_credits > 0:
        cgpa = round(total_weighted_points / total_credits, 2)

    return {
        "student": dict(student),
        "semesters": list(semesters.values()),
        "cgpa": cgpa
    }