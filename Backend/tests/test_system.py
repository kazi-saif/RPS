"""Real HTTP integration tests using an isolated temporary database."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
class SystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.env = {**os.environ, 'RPS_DATABASE_URL': 'sqlite:///' + cls.temp.name + '/test.sqlite3', 'RPS_SECRET_KEY': 'test-only-secret-longer-than-thirty-two-characters', 'PYTHONPATH': str(ROOT)}
        seed = "from app.main import Base, engine, SessionLocal, User, hash_password; Base.metadata.create_all(engine); db=SessionLocal(); db.add(User(username='admin', hashed_password=hash_password('Admin-password-123'), role='admin', must_change_password=False)); db.commit()"
        subprocess.run([sys.executable, '-c', seed], env=cls.env, cwd=ROOT, check=True)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        cls.url = f'http://127.0.0.1:{port}'
        cls.log = open(cls.temp.name + '/server.log', 'w+')
        cls.process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)], env=cls.env, cwd=ROOT, stdout=cls.log, stderr=cls.log)
        for _ in range(100):
            try:
                urlopen(cls.url + '/health', timeout=1).close(); break
            except OSError:
                if cls.process.poll() is not None:
                    cls.log.seek(0); raise RuntimeError(cls.log.read())
                time.sleep(.05)
        else:
            raise RuntimeError('Server did not start')
    @classmethod
    def tearDownClass(cls):
        cls.process.terminate(); cls.process.wait(timeout=10); cls.log.close(); cls.temp.cleanup()
    def request(self, path, data=None, token=None, method=None, expected=200, form=False):
        headers = {}
        if token: headers['Authorization'] = 'Bearer ' + token
        body = None
        if data is not None:
            body = (urlencode(data) if form else json.dumps(data)).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        req = Request(self.url + path, data=body, headers=headers, method=method or ('POST' if data is not None else 'GET'))
        try:
            response = urlopen(req, timeout=10)
        except HTTPError as error:
            response = error
        raw = response.read()
        response.close()
        self.assertEqual(response.status, expected, raw.decode()[:1000])
        return json.loads(raw) if raw else None
    def login(self, username, password):
        return self.request('/login', {'username':username,'password':password}, form=True)['access_token']
    def test_bulk_import_is_validated_and_atomic(self):
        admin = self.login('admin','Admin-password-123')
        department = self.request('/departments', {'name':'Import department'}, admin)
        session = self.request('/sessions', {'name':'Import session'}, admin)
        data = {'department_id':department['id'], 'session_id':session['id'], 'csv_text':'student_id,name,email\nBS001,"Student, One",bulk1@example.com\nBS002,Student Two,bulk2@example.com\n'}
        self.request('/bulk-import/students',data,expected=401)
        preview = self.request('/bulk-import/students', data, admin)
        self.assertTrue(preview['valid']); self.assertEqual(preview['count'],2)
        self.assertEqual(preview['rows'][0]['name'],'Student, One')
        self.assertFalse(any(s['student_id']=='BS001' for s in self.request('/students',token=admin)['students']))
        bad = {**data,'csv_text':data['csv_text']+'BS003,Bad,not-an-email\n','preview':False}
        self.assertFalse(self.request('/bulk-import/students',bad,admin)['valid'])
        self.assertFalse(any(s['student_id']=='BS001' for s in self.request('/students',token=admin)['students']))
        self.assertEqual(self.request('/bulk-import/students',{**data,'preview':False},admin)['created'],2)
        self.assertFalse(self.request('/bulk-import/students',{**data,'preview':False},admin)['valid'])
        duplicates={**data,'csv_text':'student_id,name,email\nBS004,One,new@example.com\nBS004,Two,new@example.com\n'}
        self.assertFalse(self.request('/bulk-import/students',duplicates,admin)['valid'])
        self.request('/bulk-import/students',{**data,'csv_text':'name,email\nOne,one@example.com'},admin,expected=400)
        teacher={'department_id':department['id'],'csv_text':'teacher_id,name,email\nBT001,Teacher One,bulkteacher@example.com','preview':False}
        self.assertEqual(self.request('/bulk-import/teachers',teacher,admin)['created'],1)
        self.request('/bulk-import/students',{**data,'session_id':99999},admin,expected=400)
        self.request('/bulk-import/teachers',{**teacher,'department_id':99999},admin,expected=400)
        self.request('/bulk-import/students',{**data,'csv_text':'student_id,name,email\n'},admin,expected=400)
        self.request('/bulk-import/teachers',{**teacher,'csv_text':'teacher_id,name,email\n"unfinished'},admin,expected=400)
        too_many='teacher_id,name,email\n'+''.join(f'BT{i},Name,t{i}@example.com\n' for i in range(1001))
        self.request('/bulk-import/teachers',{**teacher,'csv_text':too_many},admin,expected=400)

    def test_complete_journey_and_permissions(self):
        admin = self.login('admin','Admin-password-123')
        self.request('/students', expected=401)
        self.request('/login', {'username':'admin','password':'bad'}, form=True, expected=401)
        department = self.request('/departments', {'name':'Computer Science'}, admin)
        session = self.request('/sessions', {'name':'2026–2027'}, admin)
        self.request('/departments', {'name':'Computer Science'}, admin, expected=409)
        student = self.request('/students', {'student_id':'S001','name':'Test Student','email':'student@example.com','department_id':department['id'],'session_id':session['id']}, admin)
        teacher = self.request('/teachers', {'teacher_id':'T001','name':'Test Teacher','email':'teacher@example.com','department_id':department['id']}, admin)
        course_data={'course_code':'C101','course_name':'Programming','credit':3,'semester':1,'department_id':department['id']}
        course=self.request('/courses', course_data, admin)
        self.request('/courses', {**course_data,'course_code':'BAD','credit':-1}, admin, expected=422)
        self.request('/courses', {**course_data,'course_code':'BAD','semester':99}, admin, expected=422)
        self.request('/students', {'student_id':'X','name':'Invalid','email':'no','department_id':1,'session_id':1}, admin, expected=422)
        self.request('/course-assignments', {'course_code':'C101','teacher_code':'T001','session_id':session['id']}, admin)
        enrollment=self.request('/course-students', {'course_code':'C101','student_id':'S001'}, admin)
        self.request('/course-students', {'course_code':'C101','student_id':'S001'}, admin, expected=409)
        accounts={}
        for role, code in [('student','S001'),('teacher','T001')]:
            credentials=self.request('/accounts', {'username':code,'role':role,'reference_id':code}, admin)
            temporary=self.login(code,credentials['temporary_password'])
            self.request('/lookups', token=temporary, expected=403)
            self.request('/change-password', {'current_password':credentials['temporary_password'],'new_password':'New-password-123'}, temporary)
            self.request('/me', token=temporary, expected=401)
            accounts[role]=self.login(code,'New-password-123')
        teacher_token=accounts['teacher']; student_token=accounts['student']
        self.request('/students', token=teacher_token, expected=403)
        self.request('/accounts', token=student_token, expected=403)
        self.request('/teacher-courses/T002', token=teacher_token, expected=403)
        self.request(f"/teacher-courses/T001/C999/marks?session_id={session['id']}", token=teacher_token, expected=403)
        self.assertEqual(len(self.request('/teacher-courses/T001',token=teacher_token)['courses']),1)
        self.request('/student-results/S999', token=student_token, expected=403)
        self.request('/student-results/S001', token=teacher_token, expected=403)
        marks={'assignment_marks':10,'class_test_marks':20,'midterm_marks':40,'final_marks':80}
        path=f"/teacher-courses/T001/C101/marks/S001?session_id={session['id']}"
        self.request(path, {**marks,'final_marks':81}, teacher_token, expected=422)
        self.request(path, {}, teacher_token, expected=422)
        saved=self.request(path,marks,teacher_token)['marks']
        self.assertEqual(saved['total_marks'],150); self.assertEqual(saved['grade'],'A+')
        pending=self.request('/student-results/S001',token=student_token)
        self.assertIsNone(pending['cgpa']); self.assertNotIn('assignment_marks',pending['semesters'][0]['courses'][0])
        self.request(f"/results-review/{saved['id']}",{'published':True,'revision':saved['revision']},student_token,method='PUT',expected=403)
        saved=self.request(f"/results-review/{saved['id']}",{'published':True,'revision':saved['revision']},admin,method='PUT')
        published=self.request('/student-results/S001?semester=1',token=student_token)
        self.assertEqual(published['cgpa'],4); self.assertEqual(published['semesters'][0]['gpa'],4)
        # A failed one-credit course alongside a four-point three-credit course gives 3.00 CGPA.
        second = self.request('/courses', {**course_data, 'course_code':'C102', 'credit':1, 'semester':2}, admin)
        self.request('/course-assignments', {'course_code':'C102','teacher_code':'T001','session_id':session['id']}, admin)
        self.request('/course-students', {'course_code':'C102','student_id':'S001'}, admin)
        failed = self.request(f"/teacher-courses/T001/C102/marks/S001?session_id={session['id']}", {k:0 for k in marks}, teacher_token)['marks']
        self.request(f"/results-review/{failed['id']}", {'published':True,'revision':failed['revision']}, admin, method='PUT')
        combined = self.request('/student-results/S001?semester=1', token=student_token)
        self.assertEqual(combined['cgpa'],3)
        self.assertEqual(combined['semesters'][0]['gpa'],4)
        self.assertEqual(len(combined['semesters']),1)
        other_department = self.request('/departments', {'name':'Business'}, admin)
        self.request('/courses', {**course_data,'course_code':'B101','department_id':other_department['id']}, admin)
        self.request('/course-students', {'student_id':'S001','course_code':'B101'}, admin, expected=400)
        self.request('/course-assignments', {'teacher_code':'T001','course_code':'B101','session_id':session['id']}, admin, expected=400)
        self.request(f"/courses/{course['id']}", {**course_data,'department_id':other_department['id']}, admin, method='PUT', expected=409)
        editable=self.request('/sessions',{'name':'Temporary'},admin)
        self.request(f"/sessions/{editable['id']}",{'name':'Renamed'},admin,method='PUT')
        self.request(f"/sessions/{editable['id']}",token=admin,method='DELETE')
        self.request('/student-results/S001?semester=9',token=student_token,expected=422)
        self.request(path,marks,teacher_token,expected=409)
        self.request(f"/course-students/{enrollment['id']}",token=admin,method='DELETE',expected=409)
        self.request(f"/courses/{course['id']}",token=admin,method='DELETE',expected=409)
        saved=self.request(f"/results-review/{saved['id']}",{'published':False,'revision':saved['revision']},admin,method='PUT')
        saved=self.request(path,{**{k:0 for k in marks},'revision':saved['revision']},teacher_token)['marks']
        saved=self.request(f"/results-review/{saved['id']}",{'published':True,'revision':saved['revision']},admin,method='PUT')
        self.assertEqual(self.request('/student-results/S001',token=student_token)['cgpa'],0)
        users=self.request('/accounts',token=admin)['accounts']; self.assertNotIn('hashed_password', users[0])
        target=next(x for x in users if x['username']=='T001')
        self.request(f"/accounts/{target['id']}/reset-password",token=admin,method='POST')
        self.request('/me',token=teacher_token,expected=401)
        self.request('/accounts/1',token=admin,method='DELETE',expected=400)
        # An expired, unsigned, or incomplete token must fail.
        self.request('/me',token='invalid',expected=401)
        seed = "from app.core.security import SECRET_KEY; from app.db.session import SessionLocal; from app.models import User; from sqlalchemy import select; import jwt; db=SessionLocal(); u=db.scalar(select(User).where(User.username=='admin')); print(jwt.encode({'sub':'admin','ver':u.token_version},SECRET_KEY,algorithm='HS256'))"
        no_exp=subprocess.check_output([sys.executable,'-c',seed],env=self.env,cwd=ROOT,text=True).strip()
        self.request('/me',token=no_exp,expected=401)
        with urlopen(self.url) as page:
            self.assertIn(b'Academic portal',page.read())
        with urlopen(self.url+'/static/app.js') as script:
            self.assertIn(b'function teacherPage',script.read())
        with urlopen(self.url+'/openapi.json') as schema:
            self.assertIn('/students',json.load(schema)['paths'])
    def test_rate_limit(self):
        for _ in range(21):
            req = Request(self.url+'/login', data=b'username=unknown&password=bad', headers={'Content-Type':'application/x-www-form-urlencoded'})
            try:
                response = urlopen(req)
            except HTTPError as error:
                response = error
            status = response.status
            response.close()
            if status == 429:
                break
        self.assertEqual(status, 429)

    def test_cohort_assignment_and_bulk_enrollment(self):
        admin=self.login('admin','Admin-password-123')
        department=self.request('/departments',{'name':'Cohort department'},admin)
        sessions=[self.request('/sessions',{'name':name},admin) for name in ['Cohort A','Cohort B']]
        for index,session in enumerate(sessions):
            self.request('/students',{'student_id':f'CO{index}','name':f'Student {index}','email':f'co{index}@example.com','department_id':department['id'],'session_id':session['id']},admin)
        teacher=self.request('/teachers',{'teacher_id':'COT','name':'Cohort teacher','email':'cot@example.com','department_id':department['id']},admin)
        for code,semester,category in [('COC',1,'core'),('COO',8,'optional theory'),('CO2',2,'core')]:
            self.request('/courses',{'course_code':code,'course_name':code,'credit':3,'semester':semester,'department_id':department['id'],'category':category},admin)
        # Provision a test-only teacher directly so no real credentials are involved.
        seed="from app.main import SessionLocal,User,hash_password; db=SessionLocal(); db.add(User(username='cohort-teacher',hashed_password=hash_password('Cohort-password-123'),role='teacher',reference_id='COT',must_change_password=False)); db.commit()"
        subprocess.run([sys.executable,'-c',seed],env=self.env,cwd=ROOT,check=True)
        teacher_token=self.login('cohort-teacher','Cohort-password-123')
        for session in sessions:
            payload={'department_id':department['id'],'session_id':session['id'],'semester':1,'course_codes':['COC']}
            preview=self.request('/semester-enrollments',payload,admin)
            self.assertEqual(preview['created'],0);self.assertEqual(preview['new_enrollments'],1)
            created=self.request('/semester-enrollments',{**payload,'preview':False},admin)
            self.assertEqual(created['created'],1)
            self.assertEqual(self.request('/semester-enrollments',{**payload,'preview':False},admin)['created'],0)
            self.request('/semester-enrollments',{**payload,'course_codes':['COC','CO2'],'preview':False},admin,expected=400)
        self.request('/course-assignments',{'course_code':'COC','teacher_code':'COT','session_id':sessions[0]['id']},admin)
        path=f"/teacher-courses/COT/COC/marks?session_id={sessions[0]['id']}"
        self.assertEqual([s['student_id'] for s in self.request(path,token=teacher_token)['students']],['CO0'])
        self.request(f"/teacher-courses/COT/COC/marks?session_id={sessions[1]['id']}",token=teacher_token,expected=403)
        marks={'assignment_marks':10,'class_test_marks':20,'midterm_marks':40,'final_marks':80}
        self.request(f"/teacher-courses/COT/COC/marks/CO1?session_id={sessions[0]['id']}",marks,teacher_token,expected=404)
        self.request('/teacher-courses/COT/COC/marks',token=teacher_token,expected=422)
        self.request('/course-assignments',{'course_code':'COC','teacher_code':'COT','session_id':sessions[1]['id']},admin)
        offerings=self.request('/teacher-courses/COT',token=teacher_token)['courses']
        self.assertEqual(len(offerings),2)
        self.assertEqual({c['session_id'] for c in offerings},{s['id'] for s in sessions})
        plan=self.request(f"/academic-plan?department_id={department['id']}&session_id={sessions[0]['id']}&semester=1",token=admin)
        self.assertEqual(plan['student_count'],1)
        self.assertEqual(len(plan['courses']),1)
        optional_plan=self.request(f"/academic-plan?department_id={department['id']}&session_id={sessions[0]['id']}&semester=8",token=admin)
        optional=next(c for c in optional_plan['courses'] if c['course_code']=='COO')
        self.assertEqual(optional['category'],'optional theory');self.assertEqual(optional['enrolled_count'],0)
        student=next(s for s in self.request('/students',token=admin)['students'] if s['student_id']=='CO0')
        student_update={k:v for k,v in student.items() if k!='id'}
        self.request(f"/students/{student['id']}",{**student_update,'session_id':sessions[1]['id']},admin,method='PUT',expected=409)
        self.request('/semester-enrollments',payload,teacher_token,expected=403)
        self.request('/academic-plan?department_id=1&session_id=1&semester=1',token=teacher_token,expected=403)

    def test_migrate_existing_database(self):
        code = """
from sqlalchemy import create_engine,text,inspect
from app.db.migrations import initialize_database
engine=create_engine('sqlite:///:memory:')
with engine.begin() as c:
 c.execute(text('CREATE TABLE courses (id INTEGER PRIMARY KEY, course_code VARCHAR UNIQUE, course_name VARCHAR, credit FLOAT, semester INTEGER, department_id INTEGER)'))
 c.execute(text('CREATE TABLE course_assignments (id INTEGER PRIMARY KEY, course_code VARCHAR, teacher_code VARCHAR, UNIQUE(course_code,teacher_code))'))
 c.execute(text('CREATE TABLE course_students (id INTEGER PRIMARY KEY, student_id VARCHAR, course_code VARCHAR, semester INTEGER, UNIQUE(student_id,course_code,semester))'))
from app.db.base import Base
Base.metadata.create_all(engine)
with engine.begin() as c:
 c.execute(text("INSERT INTO departments (id,name) VALUES (1,'Legacy department')"))
 c.execute(text("INSERT INTO academic_sessions (id,name) VALUES (1,'Legacy session')"))
 c.execute(text("INSERT INTO students (id,student_id,name,email,department_id,session_id) VALUES (1,'LS','Legacy student','legacy@example.com',1,1)"))
 c.execute(text("INSERT INTO courses (id,course_code,course_name,credit,semester,department_id) VALUES (1,'LC','Legacy course',3,1,1)"))
 c.execute(text("INSERT INTO course_students (id,student_id,course_code,semester) VALUES (1,'LS','LC',1)"))
 c.execute(text("INSERT INTO course_marks (id,enrollment_id,assignment_marks,class_test_marks,midterm_marks,final_marks,published) VALUES (1,1,10,20,40,80,1)"))
initialize_database(engine)
initialize_database(engine)
assert 'session_id' in {x['name'] for x in inspect(engine).get_columns('course_assignments')}
assert 'session_id' in {x['name'] for x in inspect(engine).get_columns('course_students')}
assert 'category' in {x['name'] for x in inspect(engine).get_columns('courses')}
with engine.connect() as c:
 assert c.execute(text('SELECT session_id FROM course_students WHERE id=1')).scalar()==1
 assert c.execute(text('SELECT final_marks FROM course_marks WHERE id=1')).scalar()==80
 assert c.execute(text('SELECT category FROM courses WHERE id=1')).scalar()=='core'
"""
        subprocess.run([sys.executable,'-c',code],env=self.env,cwd=ROOT,check=True)

    def test_fixed_curriculum_auto_enrollment(self):
        admin=self.login('admin','Admin-password-123')
        department=self.request('/departments',{'name':'Fixed curriculum department'},admin)
        session=self.request('/sessions',{'name':'Fixed curriculum session'},admin)
        base_course={'course_name':'Fixed course','credit':3,'department_id':department['id']}
        for code,semester,category in [('FIX1',1,'core'),('FIX6',6,'core'),('FIX7',7,'core'),('FIX8',8,'core'),('FIXOPT',8,'optional theory')]:
            self.request('/courses',{**base_course,'course_code':code,'semester':semester,'category':category},admin)
        student={'student_id':'FIXS','name':'Fixed Student','email':'fixeds@example.com','department_id':department['id'],'session_id':session['id']}
        self.request('/students',student,admin)
        config={'department_id':department['id'],'session_id':session['id'],'current_semester':7,'processing_semester':6,'automatic_core':True}
        self.request('/cohorts',{**config,'processing_semester':8},admin,expected=422)
        cohort=self.request('/cohorts',config,admin)
        enrolled=[e for e in self.request('/course-students',token=admin)['enrollments'] if e['student_id']=='FIXS']
        self.assertEqual({e['course_code'] for e in enrolled},{'FIX1','FIX6','FIX7','FIX8'})
        self.request(f"/course-students/{enrolled[0]['id']}",token=admin,method='DELETE',expected=409)
        self.request(f"/cohorts/{cohort['id']}",config,admin,method='PUT')
        self.assertEqual(len([e for e in self.request('/course-students',token=admin)['enrollments'] if e['student_id']=='FIXS']),4)
        # A newly registered student inherits every fixed core course.
        self.request('/students',{**student,'student_id':'FIXS2','email':'fixeds2@example.com'},admin)
        # Bulk-imported students inherit the same curriculum.
        self.request('/bulk-import/students',{'department_id':department['id'],'session_id':session['id'],'csv_text':'student_id,name,email\nFIXS3,Imported Student,fixeds3@example.com','preview':False},admin)
        # Adding another fixed course synchronizes every student in that batch.
        self.request('/courses',{**base_course,'course_code':'FIXNEW','semester':2},admin)
        all_enrolled=self.request('/course-students',token=admin)['enrollments']
        for student_id in ['FIXS','FIXS2','FIXS3']:
            self.assertEqual(len([e for e in all_enrolled if e['student_id']==student_id]),5)
            result=self.request('/student-results/'+student_id+'?semester=6',token=admin)
            self.assertEqual(result['cohort']['current_semester'],7)
            self.assertEqual(result['cohort']['processing_semester'],6)
            self.assertEqual(len(result['semesters']),1)
            self.assertEqual(result['semesters'][0]['courses'][0]['course_code'],'FIX6')
            self.assertIsNone(result['cgpa'])
        self.assertFalse(any(e['course_code']=='FIXOPT' for e in all_enrolled))
        # An incorrectly registered student can be removed if no account or marks exist.
        temporary=self.request('/students',{**student,'student_id':'FIXDELETE','email':'fixeddelete@example.com'},admin)
        self.request(f"/students/{temporary['id']}",token=admin,method='DELETE')
        self.assertFalse(any(e['student_id']=='FIXDELETE' for e in self.request('/course-students',token=admin)['enrollments']))
        lookups=self.request('/lookups',token=admin)
        self.assertTrue(any(c['id']==cohort['id'] for c in lookups['cohorts']))

    def test_marks_revision_and_academic_record_protection(self):
        admin=self.login('admin','Admin-password-123')
        department=self.request('/departments',{'name':'Revision department'},admin)
        session=self.request('/sessions',{'name':'Revision session'},admin)
        self.request('/students',{'student_id':'REVS','name':'Revision student','email':'revs@example.com','department_id':department['id'],'session_id':session['id']},admin)
        self.request('/teachers',{'teacher_id':'REVT','name':'Revision teacher','email':'revt@example.com','department_id':department['id']},admin)
        course_data={'course_code':'REVC','course_name':'Revision course','credit':3,'semester':1,'department_id':department['id']}
        course=self.request('/courses',course_data,admin)
        self.request('/course-students',{'student_id':'REVS','course_code':'REVC'},admin)
        self.request('/course-assignments',{'teacher_code':'REVT','course_code':'REVC','session_id':session['id']},admin)
        seed="from app.main import SessionLocal,User,hash_password; db=SessionLocal(); db.add(User(username='revision-teacher',hashed_password=hash_password('Revision-password-123'),role='teacher',reference_id='REVT',must_change_password=False)); db.commit()"
        subprocess.run([sys.executable,'-c',seed],env=self.env,cwd=ROOT,check=True)
        teacher=self.login('revision-teacher','Revision-password-123')
        path=f"/teacher-courses/REVT/REVC/marks/REVS?session_id={session['id']}"
        marks={'assignment_marks':9.99,'class_test_marks':20,'midterm_marks':40,'final_marks':80}
        self.request(path,{**marks,'assignment_marks':0.333},teacher,expected=422)
        self.request(path,{**marks,'assignment_marks':float('nan')},teacher,expected=422)
        self.request(path,{**marks,'assignment_marks':float('inf')},teacher,expected=422)
        first=self.request(path,marks,teacher)['marks']
        self.assertEqual(first['total_marks'],149.99)
        self.request(path,marks,teacher,expected=409)
        second=self.request(path,{**marks,'revision':first['revision'],'final_marks':70},teacher)['marks']
        self.request(path,{**marks,'revision':first['revision']},teacher,expected=409)
        self.request(f"/results-review/{first['id']}",{'published':True,'revision':first['revision']},admin,method='PUT',expected=409)
        published=self.request(f"/results-review/{first['id']}",{'published':True,'revision':second['revision']},admin,method='PUT')
        self.request(path,{**marks,'revision':published['revision']},teacher,expected=409)
        self.request(f"/courses/{course['id']}",{**course_data,'credit':4},admin,method='PUT',expected=409)
        self.request(f"/courses/{course['id']}",{**course_data,'semester':8,'category':'optional theory'},admin,method='PUT',expected=409)
        draft=self.request(f"/results-review/{first['id']}",{'published':False,'revision':published['revision']},admin,method='PUT')
        # Two editors saving the same revision cannot silently overwrite one another.
        from concurrent.futures import ThreadPoolExecutor
        def competing_save(final):
            req=Request(self.url+path,data=json.dumps({**marks,'revision':draft['revision'],'final_marks':final}).encode(),headers={'Authorization':'Bearer '+teacher,'Content-Type':'application/json'})
            try: response=urlopen(req)
            except HTTPError as error: response=error
            status=response.status;response.read();response.close();return status
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(competing_save,[60,65]))
        self.assertEqual(sorted(statuses),[200,409])
        future_data={**course_data,'course_code':'REVF','course_name':'Future course','semester':8}
        self.request('/courses',future_data,admin)
        config={'department_id':department['id'],'session_id':session['id'],'current_semester':7,'processing_semester':6,'automatic_core':True}
        cohort=self.request('/cohorts',config,admin)
        self.request('/course-assignments',{'teacher_code':'REVT','course_code':'REVF','session_id':session['id']},admin)
        future_path=f"/teacher-courses/REVT/REVF/marks/REVS?session_id={session['id']}"
        self.request(future_path,marks,teacher,expected=409)
        future_list=self.request(f"/teacher-courses/REVT/REVF/marks?session_id={session['id']}",token=teacher)
        self.assertFalse(future_list['entry_allowed'])
        self.request(f"/cohorts/{cohort['id']}",{**config,'current_semester':8},admin,method='PUT')
        self.request(future_path,marks,teacher)
        self.request(f"/cohorts/{cohort['id']}",config,admin,method='PUT',expected=409)
        pending_course=self.request('/courses',{**course_data,'course_code':'REVP','course_name':'Pending course'},admin)
        # Auto-enrollment adds the new fixed course without inventing marks.
        partial=self.request('/student-results/REVS?semester=1',token=admin)
        self.assertFalse(partial['semesters'][0]['complete'])
        self.assertEqual(partial['semesters'][0]['graded_courses'],1)
        student=next(s for s in self.request('/students',token=admin)['students'] if s['student_id']=='REVS')
        self.request(f"/students/{student['id']}",token=admin,method='DELETE',expected=409)
        self.request('/accounts',{'username':'another-revt','role':'teacher','reference_id':'REVT'},admin,expected=409)

    def test_optional_course_limits_and_safe_removal(self):
        admin=self.login('admin','Admin-password-123')
        department=self.request('/departments',{'name':'Elective department'},admin)
        session=self.request('/sessions',{'name':'Elective session'},admin)
        for number in [1,2]:
            self.request('/students',{'student_id':f'ELS{number}','name':'Elective student','email':f'els{number}@example.com','department_id':department['id'],'session_id':session['id']},admin)
        for code,category in [('EL1','optional theory'),('EL2','optional theory'),('ELL','optional lab'),('ELCORE','core')]:
            self.request('/courses',{'course_code':code,'course_name':code,'credit':3,'semester':8,'department_id':department['id'],'category':category},admin)
        payload={'department_id':department['id'],'session_id':session['id'],'semester':8,'course_codes':['EL1','EL2'],'preview':False}
        self.request('/semester-enrollments',payload,admin,expected=400)
        self.assertEqual(self.request('/semester-enrollments',{**payload,'course_codes':['EL1','ELL']},admin)['created'],4)
        self.request('/course-students',{'student_id':'ELS1','course_code':'EL2'},admin,expected=409)
        self.request('/semester-enrollments',{**payload,'course_codes':['EL2']},admin,expected=409)
        remove={**payload,'course_codes':['EL1'],'preview':True}
        self.assertEqual(self.request('/semester-enrollments/remove-optional',remove,admin)['removed'],0)
        self.assertEqual(self.request('/semester-enrollments/remove-optional',{**remove,'preview':False},admin)['removed'],2)
        self.assertEqual(self.request('/semester-enrollments',{**payload,'course_codes':['EL2']},admin)['created'],2)
        self.request('/semester-enrollments/remove-optional',{**remove,'course_codes':['ELCORE'],'preview':False},admin,expected=400)
        # A saved result protects optional enrollments from bulk removal.
        seed="from app.main import SessionLocal,Enrollment,Marks; from sqlalchemy import select; db=SessionLocal(); e=db.scalar(select(Enrollment).where(Enrollment.student_id=='ELS1',Enrollment.course_code=='EL2')); db.add(Marks(enrollment_id=e.id,assignment_marks=1,class_test_marks=2,midterm_marks=3,final_marks=4)); db.commit()"
        subprocess.run([sys.executable,'-c',seed],env=self.env,cwd=ROOT,check=True)
        self.request('/semester-enrollments/remove-optional',{**remove,'course_codes':['EL2'],'preview':False},admin,expected=409)
        self.assertEqual(self.request('/semester-enrollments',{**payload,'course_codes':['EL2'],'preview':True},admin)['already_enrolled'],2)
        self.request('/courses',{'course_code':'ELBAD','course_name':'Wrong semester elective','credit':3,'semester':7,'department_id':department['id'],'category':'optional lab'},admin,expected=422)

    def test_grade_boundaries(self):
        code="from app.main import calculate_grade; assert calculate_grade(150)==('A+',4); assert calculate_grade(120)==('A+',4); assert calculate_grade(112.5)==('A',3.75); assert calculate_grade(60)==('D',2); assert calculate_grade(59.99)==('F',0)"
        subprocess.run([sys.executable,'-c',code],env=self.env,cwd=ROOT,check=True)

if __name__=='__main__': unittest.main(verbosity=2)
