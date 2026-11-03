"""Validate complete CSV batches before inserting any records."""
import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError, Field
from sqlalchemy import select
from app.services.curriculum import sync_fixed_curriculum
from app.models import Department, AcademicSession, Student, Teacher


def import_router(DB, admin, Input, StudentInput, TeacherInput):
    router = APIRouter()

    class ImportInput(Input):
        csv_text: str = Field(min_length=1, max_length=1_000_000)
        department_id: int = Field(gt=0)
        session_id: int | None = Field(default=None, gt=0)
        preview: bool = True

    @router.post('/bulk-import/{kind}')
    def bulk_import(kind: str, data: ImportInput, db: DB, user=Depends(admin)):
        if kind not in ('students', 'teachers'):
            raise HTTPException(404, 'Import supports students and teachers')
        if not db.get(Department, data.department_id):
            raise HTTPException(400, 'Choose an existing department')
        if kind == 'students' and (not data.session_id or not db.get(AcademicSession, data.session_id)):
            raise HTTPException(400, 'Choose an existing academic session')
        model, schema, code = (Student, StudentInput, 'student_id') if kind == 'students' else (Teacher, TeacherInput, 'teacher_id')
        expected = [code, 'name', 'email']
        reader = csv.DictReader(io.StringIO(data.csv_text.lstrip('\ufeff')), strict=True)
        try:
            if reader.fieldnames != expected:
                raise HTTPException(400, f'CSV headers must be exactly: {",".join(expected)}')
            existing_codes = set(db.scalars(select(getattr(model, code))))
            existing_emails = set(db.scalars(select(model.email)))
            rows, errors = [], []
            seen_codes, seen_emails = set(), set()
            for number, row in enumerate(reader, start=2):
                if number > 1001:
                    raise HTTPException(400, 'Import at most 1,000 records per file')
                if None in row or any(value is None for value in row.values()):
                    errors.append({'row': number, 'message': 'Wrong number of columns'})
                    continue
                values = {key: value.strip() for key, value in row.items()}
                values['department_id'] = data.department_id
                if kind == 'students':
                    values['session_id'] = data.session_id
                try:
                    values = schema.model_validate(values).model_dump()
                except ValidationError as error:
                    errors.append({'row': number, 'message': '; '.join(f"{e['loc'][0]}: {e['msg']}" for e in error.errors())})
                    continue
                if values[code] in existing_codes or values[code] in seen_codes:
                    errors.append({'row': number, 'message': f'{code} already exists or is repeated in this file'})
                if values['email'] in existing_emails or values['email'] in seen_emails:
                    errors.append({'row': number, 'message': 'Email already exists or is repeated in this file'})
                seen_codes.add(values[code])
                seen_emails.add(values['email'])
                rows.append(values)
        except csv.Error:
            raise HTTPException(400, 'Invalid CSV format. Export the file again as CSV UTF-8.')
        if not rows and not errors:
            raise HTTPException(400, 'The CSV file contains no records')
        if errors:
            return {'valid': False, 'errors': errors, 'created': 0, 'count': len(rows)}
        if not data.preview:
            db.add_all(model(**row) for row in rows)
            if kind == 'students':
                sync_fixed_curriculum(db)
            db.commit()
        return {'valid': True, 'errors': [], 'rows': rows[:20], 'count': len(rows), 'created': 0 if data.preview else len(rows)}

    return router
