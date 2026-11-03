
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine, SessionLocal

from app.models.user import User

from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import (
        verify_password,
        create_access_token,
        hash_password,
        decode_access_token
    )

from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

app = FastAPI(
        title="Result Processing System",
        description="University Result Processing System API",
        version="1.0.0",
    )

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except InvalidTokenError:
        raise credentials_exception

    db = SessionLocal()
    try:
        user = db.execute(
            text("SELECT * FROM users WHERE username = :username"),
            {"username": username}
        ).mappings().first()

        if user is None:
            raise credentials_exception

        return user

    finally:
        db.close()


def require_admin(current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return current_user


def require_teacher(current_user=Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(
            status_code=403,
            detail="Teacher access required"
        )
    return current_user


def require_student(current_user=Depends(get_current_user)):
    if current_user["role"] != "student":
        raise HTTPException(
            status_code=403,
            detail="Student access required"
        )
    return current_user



@app.get("/me")
def read_current_user(current_user=Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "role": current_user["role"],
        "reference_id": current_user["reference_id"]
    }


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

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()

    try:
        user = db.execute(
            text("SELECT * FROM users WHERE username = :username"),
            {"username": form_data.username}
        ).mappings().first()

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        if not verify_password(
            form_data.password,
            user["hashed_password"]
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        access_token = create_access_token({
            "sub": user["username"],
            "role": user["role"],
            "reference_id": user["reference_id"]
        })

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": user["role"],
            "username": user["username"]
        }

    finally:
        db.close()


@app.post("/create-admin", dependencies=[Depends(require_admin)])
def create_admin(username: str, password: str):
    db = SessionLocal()

    try:
        existing_user = db.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": username}
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Username already exists"
            )

        hashed_password = hash_password(password)

        db.execute(
            text("""
                INSERT INTO users (username, hashed_password, role)
                VALUES (:username, :hashed_password, 'admin')
            """),
            {
                "username": username,
                "hashed_password": hashed_password
            }
        )

        db.commit()

        return {"message": "Admin account created successfully"}

    finally:
        db.close()


@app.post("/create-teacher-accounts", dependencies=[Depends(require_admin)])
def create_teacher_accounts():
    db = SessionLocal()

    try:
        teachers = db.execute(
            text("""
                SELECT teacher_id
                FROM teachers
                WHERE department_id = 1
                ORDER BY teacher_id
            """)
        ).mappings().all()

        created_accounts = []

        for teacher in teachers:
            teacher_id = teacher["teacher_id"]

            existing_user = db.execute(
                text("SELECT id FROM users WHERE username = :username"),
                {"username": teacher_id}
            ).first()

            if existing_user:
                continue

            password = f"{teacher_id}@Rps2026"

            db.execute(
                text("""
                    INSERT INTO users
                    (username, hashed_password, role, reference_id)
                    VALUES (:username, :password, 'teacher', :reference_id)
                """),
                {
                    "username": teacher_id,
                    "password": hash_password(password),
                    "reference_id": teacher_id
                }
            )

            created_accounts.append({
                "username": teacher_id,
                "temporary_password": password
            })

        db.commit()

        return {
            "message": "Teacher accounts created",
            "created": created_accounts
        }

    finally:
        db.close()



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


@app.get("/students", dependencies=[Depends(require_admin)])
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


@app.post("/students", status_code=201, dependencies=[Depends(require_admin)])
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



@app.put("/students/{student_id}", dependencies=[Depends(require_admin)])
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




@app.delete("/students/{student_id}", dependencies=[Depends(require_admin)])
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





@app.get("/courses", dependencies=[Depends(require_admin)])
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

@app.post("/courses", status_code=201, dependencies=[Depends(require_admin)])
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

@app.put("/courses/{course_id}", dependencies=[Depends(require_admin)])
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

@app.delete("/courses/{course_id}", dependencies=[Depends(require_admin)])
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

@app.post("/teachers", status_code=201, dependencies=[Depends(require_admin)])
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

@app.get("/teachers", dependencies=[Depends(require_admin)])
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

@app.put("/teachers/{teacher_id}", dependencies=[Depends(require_admin)])
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

@app.delete("/teachers/{teacher_id}", dependencies=[Depends(require_admin)])
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


@app.post("/course-assignments", status_code=201, dependencies=[Depends(require_admin)])
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

@app.get("/course-assignments", dependencies=[Depends(require_admin)])
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


@app.delete("/course-assignments/{assignment_id}", dependencies=[Depends(require_admin)])
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
def get_teacher_courses(
    teacher_code: str,
    current_user=Depends(require_teacher)
):

    if teacher_code != current_user["reference_id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own courses"
        )


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
def get_course_students(
    teacher_code: str,
    course_code: str,
    current_user=Depends(require_teacher)
):

    if teacher_code != current_user["reference_id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own courses"
        )

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


class CourseStudentCreate(BaseModel):
    student_id: str
    course_code: str


@app.post("/course-students", status_code=201, dependencies=[Depends(require_admin)])
def add_student_to_course(data: CourseStudentCreate):

    with engine.begin() as connection:

        # Check whether student and course exist
        check_query = text("""
            SELECT c.semester
            FROM courses c
            CROSS JOIN students s
            WHERE c.course_code = :course_code
            AND s.student_id = :student_id
        """)

        result = connection.execute(
            check_query,
            {
                "course_code": data.course_code,
                "student_id": data.student_id
            }
        ).first()

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Student or course not found"
            )

        # Add student to course
        insert_query = text("""
            INSERT INTO course_students (
                student_id,
                course_code,
                semester
            )
            VALUES (
                :student_id,
                :course_code,
                :semester
            )
            RETURNING id, student_id, course_code, semester
        """)

        try:
            new_enrollment = connection.execute(
                insert_query,
                {
                    "student_id": data.student_id,
                    "course_code": data.course_code,
                    "semester": result.semester
                }
            ).fetchone()

        except Exception as error:
            from sqlalchemy.exc import IntegrityError

            if isinstance(error, IntegrityError):
                raise HTTPException(
                    status_code=409,
                    detail="Student is already enrolled in this course"
                ) from error

            raise

    return {
        "message": "Student added to course successfully",
        "enrollment": dict(new_enrollment._mapping)
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
def get_course_marks(
    teacher_code: str,
    course_code: str,
    current_user=Depends(require_teacher)
):

    if teacher_code != current_user["reference_id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own courses"
        )

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
    marks: MarksCreate,
    current_user=Depends(require_teacher)
):

    if teacher_code != current_user["reference_id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only update marks for your own courses"
        )

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
def get_student_results(
    student_id: str,
    department_id: int,
    session_id: int,
    semester: int,
    current_user=Depends(get_current_user)
):

    if current_user["role"] == "student":
        if student_id != current_user["reference_id"]:
            raise HTTPException(
                status_code=403,
                detail="You can only view your own results"
            )

    elif current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    # Validate semester

    if semester < 1 or semester > 8:
        raise HTTPException(
            status_code=400,
            detail="Semester must be between 1 and 8"
        )

    with engine.connect() as connection:

        # Check student
        student = connection.execute(
            text("""
                SELECT student_id, name, email
                FROM students
                WHERE student_id = :student_id
                AND department_id = :department_id
                AND session_id = :session_id
            """),
            {
                "student_id": student_id,
                "department_id": department_id,
                "session_id": session_id
            }
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

        course_semester = row["semester"]

        if course_semester not in semesters:
            semesters[course_semester] = {
                "semester": course_semester,
                "courses": [],
                "gpa": None,
                "total_credits": 0,
                "weighted_points": 0
            }

        course = dict(row)

        semesters[course_semester]["courses"].append(course)

        # Calculate GPA only for courses with saved marks
        if row["grade_point"] is not None and row["total_marks"] is not None:

            credit = float(row["credit"])
            grade_point = float(row["grade_point"])

            semesters[course_semester]["total_credits"] += credit

            semesters[course_semester]["weighted_points"] += (
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
        "semesters": [
            data for data in semesters.values()
            if data["semester"] == semester
        ],
        "cgpa": cgpa
    }
