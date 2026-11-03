from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
import secrets
import time
from threading import Lock
from collections import deque
from decimal import Decimal
from fastapi.exceptions import RequestValidationError
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, ConfigDict, StringConstraints, model_validator
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from jwt import InvalidTokenError
from app.db.base import Base
from app.db.migrations import initialize_database
from app.db.session import engine, SessionLocal
from app.models import Student, User, Department, AcademicSession, Teacher, Course, Assignment, Enrollment, Marks, Cohort
from app.services.curriculum import sync_fixed_curriculum
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token

@asynccontextmanager
async def lifespan(app):
    initialize_database(engine)
    with SessionLocal.begin() as db:
        sync_fixed_curriculum(db)
    yield

app = FastAPI(title='Result Processing System', version='2.1.0', lifespan=lifespan, docs_url=None, redoc_url=None)
# Basic local-server protection. Multi-worker public deployments need a shared limiter.
login_attempts = {}
account_attempts = {}
account_attempts_lock = Lock()
@app.middleware('http')
async def protect_login(request, call_next):
    if request.method == 'POST' and request.url.path == '/login':
        now = time.monotonic()
        # Limits apply per client; other clients can still sign in.
        for key in list(login_attempts):
            attempts = login_attempts[key]
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if not attempts:
                del login_attempts[key]
        client = request.client.host if request.client else 'local'
        attempts = login_attempts.setdefault(client, deque())
        if len(attempts) >= 100:
            return JSONResponse(status_code=429, content={'detail': 'Too many sign-in attempts. Wait one minute and try again.'}, headers={'Retry-After': '60'})
        attempts.append(now)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response

oauth = OAuth2PasswordBearer(tokenUrl='/login')
FRONTEND = Path(__file__).resolve().parents[2] / 'Frontend'

def db_session():
    with SessionLocal() as db:
        yield db
DB = Annotated[Session, Depends(db_session)]

def current_user(db: DB, token: str = Depends(oauth)):
    try:
        payload = decode_access_token(token)
        user = db.scalar(select(User).where(User.username == payload['sub']))
        if not user or user.token_version != payload['ver']:
            raise ValueError()
        return user
    except (InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, 'Please sign in again', headers={'WWW-Authenticate': 'Bearer'})

def ready_user(user: User = Depends(current_user)):
    if user.must_change_password:
        raise HTTPException(403, 'Change your temporary password before continuing')
    return user

def admin(user: User = Depends(ready_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Admin access required')
    return user

@app.exception_handler(RequestValidationError)
async def invalid_input(request, error):
    return JSONResponse(status_code=422, content={'detail': [{'loc': list(e['loc']), 'msg': e['msg'], 'type': e['type']} for e in error.errors()]})

@app.exception_handler(IntegrityError)
async def integrity_error(request, error):
    return JSONResponse(status_code=409, content={'detail': 'This record already exists or is linked to other records. Remove its links first.'})

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30, pattern=r'^[A-Za-z0-9_-]+$')]
Password = Annotated[str, Field(min_length=12, max_length=128)]
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
class Named(Input):
    name: Text
class SessionInput(Named):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]

class Person(Input):
    name: Text
    email: EmailStr
    department_id: int = Field(gt=0)
class StudentInput(Person):
    student_id: Code
    session_id: int = Field(gt=0)
class TeacherInput(Person):
    teacher_id: Code
class CourseInput(Input):
    course_code: Code
    course_name: Text
    credit: float = Field(gt=0, le=10)
    semester: int = Field(ge=1, le=8)
    department_id: int = Field(gt=0)
    category: str = Field(default='core', pattern='^(core|optional theory|optional lab)$')

    @model_validator(mode='after')
    def validate_optional_semester(self):
        if self.category != 'core' and self.semester != 8:
            raise ValueError('Optional courses belong to Semester 8')
        return self
class AssignmentInput(Input):
    course_code: Code
    teacher_code: Code
    session_id: int = Field(gt=0)
class EnrollmentInput(Input):
    student_id: Code
    course_code: Code
class CohortInput(Input):
    department_id: int = Field(gt=0)
    session_id: int = Field(gt=0)
    current_semester: int = Field(ge=1, le=8)
    processing_semester: int = Field(ge=1, le=8)
    automatic_core: bool = True

    @model_validator(mode='after')
    def validate_progress(self):
        if self.processing_semester > self.current_semester:
            raise ValueError('Result processing semester cannot exceed current semester')
        return self

class AccountInput(Input):
    username: Code
    role: str = Field(pattern='^(admin|teacher|student)$')
    reference_id: Code | None = None
class PasswordInput(Input):
    current_password: str
    new_password: Password
class MarksInput(Input):
    revision: int | None = Field(default=None, ge=1)
    assignment_marks: float = Field(ge=0, le=10)
    class_test_marks: float = Field(ge=0, le=20)
    midterm_marks: float = Field(ge=0, le=40)
    final_marks: float = Field(ge=0, le=80)

    @model_validator(mode='after')
    def validate_precision(self):
        for field in ('assignment_marks', 'class_test_marks', 'midterm_marks', 'final_marks'):
            value = Decimal(str(getattr(self, field)))
            if value != value.quantize(Decimal('0.01')):
                raise ValueError('Marks must have at most two decimal places')
        return self

class PublicationInput(Input):
    published: bool
    revision: int = Field(ge=1)

def record(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}

def require_record(db, model, identifier):
    row = db.get(model, identifier)
    if not row:
        raise HTTPException(404, 'Record not found')
    return row

@app.post('/login')
def login(db: DB, form: OAuth2PasswordRequestForm = Depends()):
    with account_attempts_lock:
        now = time.monotonic()
        for key in list(account_attempts):
            attempts = account_attempts[key]
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if not attempts:
                del account_attempts[key]
        attempts = account_attempts.setdefault(form.username, deque())
        if len(attempts) >= 20:
            raise HTTPException(429, 'Too many sign-in attempts for this account. Wait one minute.', headers={'Retry-After': '60'})
        attempts.append(now)
    user = db.scalar(select(User).where(User.username == form.username))
    # Verify a real hash on both paths to avoid disclosing whether a username exists.
    if not verify_password(form.password, user.hashed_password if user else DUMMY_HASH):
        raise HTTPException(401, 'Invalid username or password')
    if not user:
        raise HTTPException(401, 'Invalid username or password')
    return {'access_token': create_access_token({'sub': user.username, 'ver': user.token_version}), 'token_type': 'bearer', **user_info(user)}

DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
def user_info(user):
    return {'username': user.username, 'role': user.role, 'reference_id': user.reference_id, 'must_change_password': user.must_change_password}

@app.get('/me')
def me(db: DB, user: User = Depends(current_user)):
    info = user_info(user)
    if user.role in ('student', 'teacher'):
        model, field = (Student, Student.student_id) if user.role == 'student' else (Teacher, Teacher.teacher_id)
        person = db.scalar(select(model).where(field == user.reference_id))
        if person:
            info['department_id'] = person.department_id
            if user.role == 'student':
                info['session_id'] = person.session_id
    return info

@app.post('/change-password')
def change_password(data: PasswordInput, db: DB, user: User = Depends(current_user)):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, 'Current password is incorrect')
    if data.current_password == data.new_password:
        raise HTTPException(400, 'Choose a different password')
    user.hashed_password = hash_password(data.new_password)
    user.must_change_password = False
    user.token_version += 1
    db.commit()
    return {'message': 'Password changed. Please sign in again.'}

@app.get('/lookups')
def lookups(db: DB, user: User = Depends(ready_user)):
    return {'departments': [record(x) for x in db.scalars(select(Department).order_by(Department.name))], 'sessions': [record(x) for x in db.scalars(select(AcademicSession).order_by(AcademicSession.name))], 'cohorts': [record(x) for x in db.scalars(select(Cohort))]}

# Explicit schemas keep each management endpoint validated and documented.
def register_resource(path, model, schema, key):
    def listing(db: DB, user: User = Depends(admin)):
        return {key: [record(x) for x in db.scalars(select(model).order_by(model.id))]}
    def create(data, db: DB, user: User = Depends(admin)):
        row = model(**data.model_dump())
        db.add(row)
        if model in (Student, Course, Cohort):
            sync_fixed_curriculum(db)
        db.commit()
        return record(row)
    create.__annotations__['data'] = schema
    def update(identifier: int, data, db: DB, user: User = Depends(admin)):
        row = require_record(db, model, identifier)
        values = data.model_dump()
        if model is Cohort and (values['department_id'] != row.department_id or values['session_id'] != row.session_id):
            raise HTTPException(409, 'Create a separate batch setting for a different department or session')
        if model is Course:
            enrolled = db.scalar(select(Enrollment.id).where(Enrollment.course_code == row.course_code).limit(1))
            if enrolled and values['category'] != row.category:
                raise HTTPException(409, 'Course type cannot change after students are enrolled')
            saved_marks = db.scalar(select(Marks.id).join(Enrollment, Enrollment.id == Marks.enrollment_id).where(Enrollment.course_code == row.course_code).limit(1))
            if saved_marks and values['credit'] != row.credit:
                raise HTTPException(409, 'Credits cannot change after marks are saved; this would change existing GPA')
        if model is Cohort:
            latest = db.scalar(select(Enrollment.semester).join(Marks, Marks.enrollment_id == Enrollment.id).join(Student, Student.student_id == Enrollment.student_id).where(Enrollment.session_id == row.session_id, Student.department_id == row.department_id).order_by(Enrollment.semester.desc()).limit(1))
            if latest and values['current_semester'] < latest:
                raise HTTPException(409, 'Current semester cannot be earlier than a semester with saved marks')
        # Stable public codes are referenced by assignments, enrollments and accounts.
        for field in ('student_id', 'teacher_id', 'course_code'):
            if field in values and values[field] != getattr(row, field):
                raise HTTPException(400, 'Record codes cannot be changed; create a new record instead')
        if model is Student and values['session_id'] != row.session_id and db.scalar(select(Enrollment.id).where(Enrollment.student_id == row.student_id).limit(1)):
            raise HTTPException(409, 'Remove enrollments before changing the student session')
        if model is Course and values['semester'] != row.semester:
            if db.scalar(select(Enrollment.id).where(Enrollment.course_code == row.course_code).limit(1)) or db.scalar(select(Assignment.id).where(Assignment.course_code == row.course_code).limit(1)):
                raise HTTPException(409, 'Remove enrollments before changing the semester')
        if model in (Student, Teacher, Course) and values['department_id'] != row.department_id:
            if model is Student:
                linked = db.scalar(select(Enrollment.id).where(Enrollment.student_id == row.student_id).limit(1))
            elif model is Teacher:
                linked = db.scalar(select(Assignment.id).where(Assignment.teacher_code == row.teacher_id).limit(1))
            else:
                linked = db.scalar(select(Assignment.id).where(Assignment.course_code == row.course_code).limit(1)) or db.scalar(select(Enrollment.id).where(Enrollment.course_code == row.course_code).limit(1))
            if linked:
                raise HTTPException(409, 'Remove course assignments and enrollments before changing the department')
        for field, value in values.items():
            setattr(row, field, value)
        if model in (Student, Course, Cohort):
            sync_fixed_curriculum(db)
        db.commit()
        return record(row)
    update.__annotations__['data'] = schema
    def remove_record(identifier: int, db: DB, user: User = Depends(admin)):
        row = require_record(db, model, identifier)
        if model in (Student, Teacher):
            role = 'student' if model is Student else 'teacher'
            code = row.student_id if model is Student else row.teacher_id
            if db.scalar(select(User.id).where(User.role == role, User.reference_id == code)):
                raise HTTPException(409, 'Delete the linked login account first')
        if model is Student:
            ids = list(db.scalars(select(Enrollment.id).where(Enrollment.student_id == row.student_id)))
            if ids:
                # Protect a result saved concurrently with the delete request.
                removed = db.execute(delete(Enrollment).where(Enrollment.id.in_(ids), ~select(Marks.id).where(Marks.enrollment_id == Enrollment.id).exists()))
                if removed.rowcount != len(ids):
                    raise HTTPException(409, 'This student has saved marks and cannot be deleted')
        db.delete(row)
        db.commit()
        return {'message': 'Record deleted'}
    for endpoint, method, suffix in [(listing, 'GET', ''), (create, 'POST', ''), (update, 'PUT', '/{identifier}'), (remove_record, 'DELETE', '/{identifier}')]:
        app.add_api_route(path + suffix, endpoint, methods=[method], name=f'{method} {key}')

from app.routes.imports import import_router
app.include_router(import_router(DB, admin, Input, StudentInput, TeacherInput))

register_resource('/cohorts', Cohort, CohortInput, 'cohorts')
register_resource('/departments', Department, Named, 'departments')
register_resource('/sessions', AcademicSession, SessionInput, 'sessions')
register_resource('/students', Student, StudentInput, 'students')
register_resource('/teachers', Teacher, TeacherInput, 'teachers')
register_resource('/courses', Course, CourseInput, 'courses')

@app.get('/accounts')
def accounts(db: DB, user: User = Depends(admin)):
    return {'accounts': [{'id': x.id, **user_info(x)} for x in db.scalars(select(User).order_by(User.id))]}

@app.post('/accounts')
def create_account(data: AccountInput, db: DB, user: User = Depends(admin)):
    if data.role != 'admin':
        model, field = (Student, Student.student_id) if data.role == 'student' else (Teacher, Teacher.teacher_id)
        if not data.reference_id or not db.scalar(select(model).where(field == data.reference_id)):
            raise HTTPException(400, 'Choose an existing student or teacher code')
        if db.scalar(select(User).where(User.role == data.role, User.reference_id == data.reference_id)):
            raise HTTPException(409, 'This person already has an account')
    elif data.reference_id:
        raise HTTPException(400, 'Admin accounts do not have a reference code')
    password = secrets.token_urlsafe(16)
    account = User(username=data.username, hashed_password=hash_password(password), role=data.role, reference_id=data.reference_id)
    db.add(account)
    db.commit()
    return {'username': account.username, 'temporary_password': password}

@app.post('/accounts/{identifier}/reset-password')
def reset_password(identifier: int, db: DB, user: User = Depends(admin)):
    target = require_record(db, User, identifier)
    if target.id == user.id:
        raise HTTPException(400, 'Use Change password for your own account')
    password = secrets.token_urlsafe(16)
    target.hashed_password = hash_password(password)
    target.must_change_password = True
    target.token_version += 1
    db.commit()
    return {'username': target.username, 'temporary_password': password}

@app.delete('/accounts/{identifier}')
def delete_account(identifier: int, db: DB, user: User = Depends(admin)):
    if identifier == user.id:
        raise HTTPException(400, 'You cannot delete your own account')
    db.delete(require_record(db, User, identifier))
    db.commit()
    return {'message': 'Account deleted'}

@app.get('/course-assignments')
def assignments(db: DB, user: User = Depends(admin)):
    rows = db.execute(select(Assignment, Course).join(Course, Course.course_code == Assignment.course_code))
    return {'assignments': [{**record(a), 'semester': c.semester, 'department_id': c.department_id} for a, c in rows]}

@app.post('/course-assignments')
def assign(data: AssignmentInput, db: DB, user: User = Depends(admin)):
    course = db.scalar(select(Course).where(Course.course_code == data.course_code))
    teacher = db.scalar(select(Teacher).where(Teacher.teacher_id == data.teacher_code))
    if not course or not teacher or course.department_id != teacher.department_id:
        raise HTTPException(400, 'Choose a teacher and course from the same department')
    require_record(db, AcademicSession, data.session_id)
    row = Assignment(**data.model_dump())
    db.add(row)
    db.commit()
    return record(row)

@app.delete('/course-assignments/{identifier}')
def unassign(identifier: int, db: DB, user: User = Depends(admin)):
    db.delete(require_record(db, Assignment, identifier))
    db.commit()
    return {'message': 'Assignment removed'}

@app.get('/course-students')
def enrollments(db: DB, user: User = Depends(admin)):
    return {'enrollments': [record(x) for x in db.scalars(select(Enrollment))]}

def validate_optional_choices(db, courses, student_ids):
    selected = {}
    for course in courses:
        if course.category == 'core':
            continue
        if course.category in selected and selected[course.category] != course.course_code:
            raise HTTPException(400, 'Select at most one optional theory course and one optional lab')
        selected[course.category] = course.course_code
    if not selected or not student_ids:
        return
    existing = db.execute(select(Enrollment.student_id, Course.category, Course.course_code).join(Course, Course.course_code == Enrollment.course_code).where(Enrollment.student_id.in_(student_ids), Course.category.in_(selected), Course.semester == 8))
    for student_id, category, code in existing:
        if selected[category] != code:
            raise HTTPException(409, f'{student_id} already has an {category} course. Remove that optional enrollment before choosing another.')

@app.post('/course-students')
def enroll(data: EnrollmentInput, db: DB, user: User = Depends(admin)):
    course = db.scalar(select(Course).where(Course.course_code == data.course_code))
    student = db.scalar(select(Student).where(Student.student_id == data.student_id))
    if not course or not student or course.department_id != student.department_id:
        raise HTTPException(400, 'Choose a student and course from the same department')
    validate_optional_choices(db, [course], [student.student_id])
    row = Enrollment(**data.model_dump(), semester=course.semester, session_id=student.session_id)
    db.add(row)
    db.commit()
    return record(row)

class SemesterEnrollmentInput(Input):
    department_id: int = Field(gt=0)
    session_id: int = Field(gt=0)
    semester: int = Field(ge=1, le=8)
    course_codes: list[Code] = Field(min_length=1, max_length=100)
    preview: bool = True

@app.get('/academic-plan')
def academic_plan(department_id: int, session_id: int, semester: int, db: DB, user: User = Depends(admin)):
    require_record(db, Department, department_id)
    require_record(db, AcademicSession, session_id)
    if not 1 <= semester <= 8:
        raise HTTPException(422, 'Semester must be between 1 and 8')
    students = list(db.scalars(select(Student).where(Student.department_id == department_id, Student.session_id == session_id)))
    courses = list(db.scalars(select(Course).where(Course.department_id == department_id, Course.semester == semester).order_by(Course.course_code)))
    teachers = list(db.scalars(select(Teacher).where(Teacher.department_id == department_id).order_by(Teacher.teacher_id)))
    assignments = list(db.scalars(select(Assignment).where(Assignment.session_id == session_id)))
    enrollments = list(db.scalars(select(Enrollment).where(Enrollment.session_id == session_id, Enrollment.semester == semester)))
    cohort = db.scalar(select(Cohort).where(Cohort.department_id == department_id, Cohort.session_id == session_id))
    return {'cohort': record(cohort) if cohort else None, 'student_count': len(students), 'teachers': [record(t) for t in teachers], 'courses': [{**record(c), 'teacher_codes': [a.teacher_code for a in assignments if a.course_code == c.course_code], 'assignments': [record(a) for a in assignments if a.course_code == c.course_code], 'enrolled_count': sum(e.course_code == c.course_code for e in enrollments)} for c in courses]}

@app.post('/semester-enrollments')
def semester_enrollments(data: SemesterEnrollmentInput, db: DB, user: User = Depends(admin)):
    require_record(db, Department, data.department_id)
    require_record(db, AcademicSession, data.session_id)
    codes = set(data.course_codes)
    courses = list(db.scalars(select(Course).where(Course.course_code.in_(codes), Course.department_id == data.department_id, Course.semester == data.semester)))
    if len(courses) != len(codes):
        raise HTTPException(400, 'All selected courses must match the department and semester')
    students = list(db.scalars(select(Student).where(Student.department_id == data.department_id, Student.session_id == data.session_id)))
    if not students:
        raise HTTPException(400, 'This department and session have no students')
    validate_optional_choices(db, courses, [s.student_id for s in students])
    existing = set(db.execute(select(Enrollment.student_id, Enrollment.course_code).where(Enrollment.session_id == data.session_id, Enrollment.course_code.in_(codes))).all())
    pending = [(s.student_id, c.course_code) for s in students for c in courses if (s.student_id, c.course_code) not in existing]
    if not data.preview:
        db.add_all(Enrollment(student_id=s, course_code=c, semester=data.semester, session_id=data.session_id) for s,c in pending)
        db.commit()
    return {'student_count': len(students), 'course_count': len(courses), 'new_enrollments': len(pending), 'already_enrolled': len(students) * len(courses) - len(pending), 'created': 0 if data.preview else len(pending)}

@app.post('/semester-enrollments/remove-optional')
def remove_optional(data: SemesterEnrollmentInput, db: DB, user: User = Depends(admin)):
    require_record(db, Department, data.department_id)
    require_record(db, AcademicSession, data.session_id)
    codes = set(data.course_codes)
    courses = list(db.scalars(select(Course).where(Course.course_code.in_(codes), Course.department_id == data.department_id, Course.semester == data.semester, Course.category != 'core')))
    if len(courses) != len(codes):
        raise HTTPException(400, 'Only optional courses in the selected department and semester can be removed')
    rows = list(db.scalars(select(Enrollment).join(Student, Student.student_id == Enrollment.student_id).where(Enrollment.course_code.in_(codes), Enrollment.session_id == data.session_id, Student.department_id == data.department_id)))
    ids = [e.id for e in rows]
    if ids and db.scalar(select(Marks.id).where(Marks.enrollment_id.in_(ids)).limit(1)):
        raise HTTPException(409, 'An optional course has saved marks. Its enrollments cannot be removed.')
    if not data.preview and ids:
        removed = db.execute(delete(Enrollment).where(Enrollment.id.in_(ids), ~select(Marks.id).where(Marks.enrollment_id == Enrollment.id).exists()))
        if removed.rowcount != len(ids):
            raise HTTPException(409, 'Marks were saved while removing enrollments. Refresh and review before continuing.')
        db.commit()
    return {'count': len(rows), 'removed': 0 if data.preview else len(rows)}

@app.delete('/course-students/{identifier}')
def unenroll(identifier: int, db: DB, user: User = Depends(admin)):
    row = require_record(db, Enrollment, identifier)
    course = db.scalar(select(Course).where(Course.course_code == row.course_code))
    student = db.scalar(select(Student).where(Student.student_id == row.student_id))
    fixed = db.scalar(select(Cohort).where(Cohort.department_id == student.department_id, Cohort.session_id == row.session_id, Cohort.automatic_core.is_(True)))
    if fixed and course.category == 'core':
        raise HTTPException(409, 'This is a fixed curriculum course and is enrolled automatically')
    if db.scalar(select(Marks).where(Marks.enrollment_id == row.id)):
        raise HTTPException(409, 'Enrollment has saved marks and cannot be deleted')
    removed = db.execute(delete(Enrollment).where(Enrollment.id == row.id, ~select(Marks.id).where(Marks.enrollment_id == Enrollment.id).exists()))
    if removed.rowcount != 1:
        raise HTTPException(409, 'This enrollment changed or has saved marks. Refresh before continuing.')
    db.commit()
    return {'message': 'Enrollment removed'}

def teacher_access(db, user, teacher_code, course_code=None, session_id=None):
    if user.role != 'teacher' or user.reference_id != teacher_code:
        raise HTTPException(403, 'You can only access your assigned courses')
    if course_code and not db.scalar(select(Assignment).where(Assignment.teacher_code == teacher_code, Assignment.course_code == course_code, Assignment.session_id == session_id)):
        raise HTTPException(403, 'You are not assigned to this course')

@app.get('/teacher-courses/{teacher_code}')
def teacher_courses(teacher_code: str, db: DB, user: User = Depends(ready_user)):
    teacher_access(db, user, teacher_code)
    rows = db.execute(select(Course, Assignment, AcademicSession).join(Assignment, Assignment.course_code == Course.course_code).join(AcademicSession, AcademicSession.id == Assignment.session_id).where(Assignment.teacher_code == teacher_code).order_by(Assignment.session_id, Course.semester, Course.course_code))
    return {'courses': [{**record(c), 'session_id': a.session_id, 'session_name': session.name} for c, a, session in rows]}

def calculate_grade(total):
    percentage = Decimal(str(total)) / Decimal(150) * Decimal(100)
    for threshold, grade, gp in [(80,'A+',4), (75,'A',3.75), (70,'A-',3.5), (65,'B+',3.25), (60,'B',3), (55,'B-',2.75), (50,'C+',2.5), (45,'C',2.25), (40,'D',2)]:
        if percentage >= threshold:
            return grade, gp
    return 'F', 0

def marks_info(marks):
    if marks is None:
        return {'total_marks': None, 'grade': None, 'grade_point': None, 'published': False}
    data = record(marks)
    total = float(sum(Decimal(str(data[key])) for key in ('assignment_marks', 'class_test_marks', 'midterm_marks', 'final_marks')))
    grade, gp = calculate_grade(total)
    return {**data, 'total_marks': total, 'grade': grade, 'grade_point': gp}

@app.get('/teacher-courses/{teacher_code}/{course_code}/marks')
def course_marks(teacher_code: str, course_code: str, session_id: int, db: DB, user: User = Depends(ready_user)):
    teacher_access(db, user, teacher_code, course_code, session_id)
    rows = db.execute(select(Student, Enrollment, Marks).join(Enrollment, Enrollment.student_id == Student.student_id).outerjoin(Marks, Marks.enrollment_id == Enrollment.id).where(Enrollment.course_code == course_code, Enrollment.session_id == session_id).order_by(Student.student_id))
    course = db.scalar(select(Course).where(Course.course_code == course_code))
    cohort = db.scalar(select(Cohort).where(Cohort.department_id == course.department_id, Cohort.session_id == session_id))
    return {'entry_allowed': not cohort or course.semester <= cohort.current_semester, 'students': [{'student_id': s.student_id, 'name': s.name, **marks_info(m)} for s, e, m in rows]}

@app.post('/teacher-courses/{teacher_code}/{course_code}/marks/{student_id}')
def save_marks(teacher_code: str, course_code: str, student_id: str, session_id: int, data: MarksInput, db: DB, user: User = Depends(ready_user)):
    teacher_access(db, user, teacher_code, course_code, session_id)
    enrollment = db.scalar(select(Enrollment).where(Enrollment.student_id == student_id, Enrollment.course_code == course_code, Enrollment.session_id == session_id))
    if not enrollment:
        raise HTTPException(404, 'Student is not enrolled in this course')
    student = db.scalar(select(Student).where(Student.student_id == student_id))
    cohort = db.scalar(select(Cohort).where(Cohort.department_id == student.department_id, Cohort.session_id == session_id))
    if cohort and enrollment.semester > cohort.current_semester:
        raise HTTPException(409, 'This is a future semester. Update the batch current semester before entering its marks.')
    row = db.scalar(select(Marks).where(Marks.enrollment_id == enrollment.id))
    values = data.model_dump(exclude={'revision'})
    if row:
        if row.published:
            raise HTTPException(409, 'Ask an admin to unpublish this result before editing')
        if data.revision != row.revision:
            raise HTTPException(409, 'These marks changed since you loaded them. Refresh the course before saving.')
        changed = db.execute(update(Marks).where(Marks.id == row.id, Marks.published.is_(False), Marks.revision == data.revision).values(**values, revision=Marks.revision + 1))
        if changed.rowcount != 1:
            raise HTTPException(409, 'These marks changed. Refresh the course before saving.')
    else:
        if data.revision is not None:
            raise HTTPException(409, 'This result changed. Refresh the course before saving.')
        row = Marks(enrollment_id=enrollment.id, **values)
        db.add(row)
    db.commit()
    db.refresh(row)
    return {'marks': marks_info(row)}

@app.get('/results-review')
def results_review(db: DB, user: User = Depends(admin)):
    rows = db.execute(select(Marks, Enrollment, Student, Course).join(Enrollment, Marks.enrollment_id == Enrollment.id).join(Student, Student.student_id == Enrollment.student_id).join(Course, Course.course_code == Enrollment.course_code).order_by(Student.student_id, Course.course_code))
    return {'results': [{**marks_info(m), 'student_id': s.student_id, 'name': s.name, 'course_code': c.course_code, 'semester': e.semester, 'session_id': e.session_id, 'department_id': c.department_id} for m,e,s,c in rows]}

@app.put('/results-review/{identifier}')
def publish(identifier: int, data: PublicationInput, db: DB, user: User = Depends(admin)):
    row = require_record(db, Marks, identifier)
    changed = db.execute(update(Marks).where(Marks.id == row.id, Marks.revision == data.revision).values(published=data.published, revision=Marks.revision + 1))
    if changed.rowcount != 1:
        raise HTTPException(409, 'This result changed since review. Refresh and review the latest marks before publishing.')
    db.commit()
    db.refresh(row)
    return marks_info(row)

@app.get('/student-results/{student_id}')
def student_results(student_id: str, db: DB, semester: int | None = None, user: User = Depends(ready_user)):
    if user.role != 'admin' and (user.role != 'student' or user.reference_id != student_id):
        raise HTTPException(403, 'You can only view your own results')
    if semester is not None and not 1 <= semester <= 8:
        raise HTTPException(422, 'Semester must be between 1 and 8')
    student = db.scalar(select(Student).where(Student.student_id == student_id))
    if not student:
        raise HTTPException(404, 'Student not found')
    rows = db.execute(select(Enrollment, Course, Marks).join(Course, Course.course_code == Enrollment.course_code).outerjoin(Marks, Marks.enrollment_id == Enrollment.id).where(Enrollment.student_id == student_id).order_by(Enrollment.semester, Course.course_code))
    semesters = {}
    weighted = credits = Decimal(0)
    for enrollment, course, marks in rows:
        visible = marks if marks and (marks.published or user.role == 'admin') else None
        info = marks_info(visible)
        bucket = semesters.setdefault(enrollment.semester, {'semester': enrollment.semester, 'courses': [], 'weighted': Decimal(0), 'total_credits': Decimal(0), 'graded_courses': 0})
        bucket['courses'].append({**record(course), **info})
        if visible:
            credit = Decimal(str(course.credit))
            points = Decimal(str(info['grade_point'])) * credit
            bucket['graded_courses'] += 1
            bucket['weighted'] += points
            bucket['total_credits'] += credit
            weighted += points
            credits += credit
    for bucket in semesters.values():
        points = bucket.pop('weighted')
        bucket['gpa'] = float(round(points / bucket['total_credits'], 2)) if bucket['total_credits'] else None
        bucket['complete'] = bucket['graded_courses'] == len(bucket['courses'])
        bucket['total_credits'] = float(bucket['total_credits'])
    cohort = db.scalar(select(Cohort).where(Cohort.department_id == student.department_id, Cohort.session_id == student.session_id))
    return {'cohort': record(cohort) if cohort else None, 'student': record(student), 'semesters': [v for k,v in semesters.items() if semester is None or k == semester], 'cgpa': float(round(weighted / credits, 2)) if credits else None}

@app.get('/health')
def health():
    with engine.connect() as connection:
        connection.execute(select(1))
    return {'status': 'running', 'version': app.version, 'database': 'connected'}

@app.get('/')
def home():
    return FileResponse(FRONTEND / 'index.html')

app.mount('/static', StaticFiles(directory=FRONTEND), name='static')
