# Result Processing System

A local academic portal built with FastAPI, SQLAlchemy, SQLite, and plain HTML/CSS/JavaScript. Admins manage the academic records, teachers enter marks, and students view their own published results. The frontend and API run from the same address; no separate frontend server is needed.

## Start here

You need Python 3.10 or newer with pip and venv. On Linux/macOS, open a terminal in this project folder and run:

```bash
./start.sh
```

The first run installs missing dependencies, initializes the database, and asks you to choose a password for the `admin` account. Use 12–128 characters. Password entry is hidden while you type. Keep this password private.

Open **http://127.0.0.1:8001** and sign in as `admin` with your chosen password. Leave the terminal running. Press Ctrl+C in that terminal to stop the server. Run `./start.sh` again whenever you want to use the project.

If port 8001 is already in use, stop the previous RPS server or run `RPS_PORT=8002 ./start.sh` and open port 8002 instead.

## Your first complete result

1. Add a department, for example Computer Science.
2. Add an academic session, for example 2026–2027.
3. Add a teacher and a student. Codes such as `T001` and `S001` must be unique. Students also need a session.
4. Add a course, for example `CSE101`, with its department, semester (1–8), and credits.
5. Under **Accounts**, choose Teacher or Student, select the person by their name/code, and save. The username is suggested from their code and can be changed before saving. Copy the temporary passwords immediately and share each one privately with its owner. Passwords are not available again; an admin can reset them.
6. Open **Teacher assignment**, choose the department, session, and semester, and assign the teacher to the course. Select the courses this batch takes and enroll the batch. For one student, use **Enrollments** instead. All must belong to the same department.
7. Sign out and sign in as the teacher. Change the temporary password, then sign in again. Choose the assigned course, enter all four marks, and save each row.
8. Sign in as admin. Under **Publish results**, review and publish the saved marks.
9. Sign in as the student, change the temporary password, and sign in again. **My results** shows only that student’s published marks and CGPA.

Use separate browser profiles or sign out between roles. Login tokens are stored for the current browser tab session and expire after one hour. Changing or resetting a password invalidates existing logins. Account credentials appear only immediately after creation/reset; refresh or leave the page to clear them.

## Rules and limitations

The current project uses the grading rules from the original code:

| Assessment | Maximum |
|---|---:|
| Assignment | 10 |
| Class test | 20 |
| Midterm | 40 |
| Final | 80 |
| Total | 150 |

Grades use `(total / 150) × 100`:

| Minimum percentage | Grade | Grade point |
|---|---|---:|
| 80 | A+ | 4.00 |
| 75 | A | 3.75 |
| 70 | A− | 3.50 |
| 65 | B+ | 3.25 |
| 60 | B | 3.00 |
| 55 | B− | 2.75 |
| 50 | C+ | 2.50 |
| 45 | C | 2.25 |
| 40 | D | 2.00 |
| Below 40 | F | 0.00 |

GPA and CGPA are credit-weighted. Published failed courses count as zero grade points. Pending/unpublished courses are excluded from student GPA and CGPA. Admin result previews include all saved marks. Semester filters do not limit the overall CGPA calculation.

There is one result per student/course, with no repeat-attempt or retake policy. Teachers cannot edit published marks; an admin must unpublish first. The same course and session can have multiple assigned teachers, each of whom can edit its draft marks for that session. Course codes are immutable. Linked records cannot be deleted, and enrollments with saved marks are protected from deletion.

**Confirm the grading policy with your institution before entering real academic records.** This version is intended for a local project demonstration. Public hosting, multi-campus policies, retakes, audit history, import/export, and institutional production approval are outside this version.

## Existing data

Your original `.env` and any database it references are not used or modified. This version deliberately uses a separate database at `Backend/rps.sqlite3`. Existing PostgreSQL data is not automatically imported. Do not point the new app at the old database: its schema is different.

Do not delete `Backend/rps.sqlite3` if it contains records you need. The locally generated `Backend/.jwt-secret` signs login tokens and is excluded from Git. Database files and backups are also excluded from Git.

## Back up your work

From the project folder:

```bash
cd Backend
.venv/bin/python manage.py backup
```

Backups are saved inside `Backend/backups/`. Copy important backups to a safe location. To restore, stop the server, retain a copy of the current database, then copy your chosen backup over `Backend/rps.sqlite3` and restart. A backup contains private records and password hashes; keep it private. Restore is a manual operation to prevent accidental data replacement.

## Manual setup (including Windows)

From the `Backend` folder:

```bash
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on Linux/macOS or `.venv\Scripts\activate` in Windows Command Prompt. Then run:

```bash
python -m pip install -r requirements.txt
python manage.py init
python manage.py create-admin
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

To create another administrator from the local command line, use `python manage.py create-admin --username another-admin`. The password is entered interactively, never in the command itself.

## Tests

From the project folder:

```bash
Backend/.venv/bin/python -m unittest discover -s Backend/tests -v
node --check Frontend/app.js
node Frontend/tests/state.test.cjs
```

The automated integration tests start a temporary server and use an isolated database. They cover the admin/teacher/student journey, authentication, password changes and resets, role and ownership checks, validation, duplicate and foreign-key conflicts, publication visibility and locks, GPA, grade boundaries, and login rate limiting. They do not alter your project database. Node is needed only for the JavaScript syntax check, not to run the portal.

The API schema is at `/openapi.json`. `/health` reports server status. The local server limits sign-in attempts to 20 per account per minute and 100 per client per minute. It binds to your computer only by default; public deployment needs HTTPS, managed secrets, a shared rate limiter, database migrations, an audit trail, and a separate deployment review.

## Add many students or teachers at once

Open **Students** or **Teachers** as admin and choose **Import CSV**. Download the template, edit it in Excel or another spreadsheet app, and export as **CSV UTF-8**. Select the batch’s department (and session for students), choose the CSV file, and click **Preview CSV**. Review the preview, then click **Import records** to save.

Student columns: `student_id,name,email`. Teacher columns: `teacher_id,name,email`. Keep that exact header order. Use a separate file for each department/session combination. Each file supports up to 1,000 people and must be smaller than 1 MB. The sample template row is only an example: replace it with your own records before importing. Names containing commas must be quoted, which spreadsheet CSV export handles automatically.

All rows are validated before saving. Invalid rows, duplicate codes/emails, or existing records block the entire batch, so no partial import is left behind. Import adds personal records only; create login accounts under Accounts afterward. Existing records are never overwritten.

## Plan courses by department, session, and semester

Admins can open **Teacher assignment**, choose a department, academic session, and semester, then click **Load semester**. The page lists the matching courses, eligible teachers, and number of enrolled students.

- **Assign** links a teacher to that course for the selected session. A teacher can teach the same course in multiple sessions; each session appears separately in their course selector. Multiple teachers may share an offering.
- **Enroll batch in selected courses** previews the number of new enrollments, then asks for confirmation. It enrolls all students of the selected department/session in the selected semester’s courses and skips existing enrollments. It does not create marks or login accounts.
- Core courses are preselected. Optional theory and lab courses are not; choose the options actually taken by this batch. For individual elective choices, use the single-student Enrollments form.
- Teachers can see and edit marks only for sessions they are assigned to. A student’s session cannot change while enrollments exist. Course semester changes are blocked while assignments or enrollments exist.

The existing local database upgrades automatically when the server starts or `manage.py init` runs. Existing student enrollments inherit their student’s session. A legacy database with teacher assignments that have no session must be explicitly mapped before upgrading; the app stops with an explanation rather than guessing which session those assignments belong to. Back up first with `manage.py backup`.

## Fixed curriculum and result-processing semester

**Batch settings** stores the current semester, the semester whose results are being processed, and whether fixed core enrollments are automatic. Enabling automatic enrollment adds every core course in the department’s static curriculum to every student of that session, including Semester 8’s fixed core courses. Semester 8 optional courses are never chosen automatically. Future-semester enrollments remain pending until actual marks are saved and published.

Automatic enrollment also runs when a new student is registered or imported, when a core course is added, when batch settings change, and on server startup. Repeating it skips existing enrollments and preserves marks. Fixed core enrollments cannot be manually removed while automatic enrollment is enabled.

For the prepared **CSE / 2021–2022** batch, the current semester is **7**, and the result-processing semester is **6**. Teacher assignment and result review initially select this batch and Semester 6. A student’s result page defaults to their own batch’s processing semester; teachers initially open an assigned course in a processing semester when one is available. Other semesters remain selectable.

Teacher assignments remain an admin decision. In Teacher assignment, choose a teacher using both their code and full name beside the course’s code and title. No teacher assignments, marks, or published results are invented by the fixed-curriculum setup.

The Teacher assignment page displays a separate card for each course, with the teacher selector and Assign teacher button directly underneath. Batch settings uses a single form for the current and result-processing semesters.


## Review and save safeguards

- Teacher marks entry uses searchable student cards. Enter all four assessment values and save each student separately. Unsaved changes require confirmation before leaving or switching courses.
- A stale marks save is rejected if another teacher edited the record. Admin publication is rejected if marks changed after review. Refresh and review the latest values instead of overwriting them.
- Published results remain locked. Future-semester marks are blocked until the batch reaches that semester. A batch cannot move backwards past saved results.
- Marks accept up to two decimal places. GPA uses decimal arithmetic, includes published failed courses, and excludes pending courses. A semester with pending courses is clearly marked **Incomplete**.
- Course credits cannot change after saved marks exist, and course type cannot change after enrollment, protecting existing calculations and fixed-course membership.
- Each student can take at most one optional theory course and one optional lab in Semester 8. Use **Remove optional enrollment from batch** before changing an elective. Removal is blocked if any selected enrollment has saved marks.
- A mistakenly registered student with no login account or saved marks can be deleted together with empty enrollments. Students with saved results remain protected.
- Account creation offers a name/code selector and excludes people who already have accounts. Duplicate accounts for the same teacher/student are also blocked in the database.

The automated suite now contains nine integration tests and six frontend state tests. A separate synthetic browser review verified teacher marks entry, admin publication, and student results: two equal-credit courses with GP 4.00 and 3.00 produced GPA/CGPA 3.50. The browser fixture is separate from the real project database.
