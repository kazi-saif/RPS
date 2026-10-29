
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
