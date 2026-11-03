
const API_URL = "http://127.0.0.1:8000";

// HTML Elements
const teacherCodeInput = document.getElementById("teacherCode");
const loadCoursesBtn = document.getElementById("loadTeacherCoursesBtn");
const courseSelect = document.getElementById("marksCourseSelect");
const marksTableBody = document.getElementById("marksTableBody");
const marksMessage = document.getElementById("marksMessage");


// Load assigned courses
async function loadTeacherCourses() {
    const teacherCode = teacherCodeInput.value.trim();

    if (!teacherCode) {
        marksMessage.textContent = "Please enter teacher code.";
        return;
    }

    marksMessage.textContent = "Loading your courses...";

    try {
        const response = await fetch(
            `${API_URL}/teacher-courses/${encodeURIComponent(teacherCode)}`,
            {
                headers: {
                    "Authorization": `Bearer ${localStorage.getItem("access_token")}`
                }
            }
        );
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load courses.");
        }

        courseSelect.innerHTML = "";

        if (!data.courses || data.courses.length === 0) {
            courseSelect.innerHTML =
                '<option value="">No assigned courses found</option>';

            courseSelect.disabled = true;
            marksMessage.textContent = "No courses assigned to this teacher.";
            return;
        }

        courseSelect.innerHTML =
            '<option value="">Select a course</option>';

        data.courses.forEach(course => {
            const option = document.createElement("option");

            option.value = course.course_code;

            option.textContent =
                `${course.course_code} - ${course.course_name} (Semester ${course.semester})`;

            courseSelect.appendChild(option);
        });

        courseSelect.disabled = false;

        marksTableBody.innerHTML = `
            <tr>
                <td colspan="10" class="p-10 text-center text-slate-500">
                    Select a course to load student marks.
                </td>
            </tr>
        `;

        marksMessage.textContent =
            `${data.courses.length} course(s) loaded successfully.`;

    } catch (error) {
        marksMessage.textContent = error.message;
        courseSelect.disabled = true;
    }
}


// Load students and their existing marks
async function loadCourseMarks() {
    const teacherCode = teacherCodeInput.value.trim();
    const courseCode = courseSelect.value;

    if (!teacherCode || !courseCode) {
        return;
    }

    marksMessage.textContent = "Loading student marks...";

    marksTableBody.innerHTML = `
        <tr>
            <td colspan="10" class="p-10 text-center">
                Loading...
            </td>
        </tr>
    `;

    try {
        const response = await fetch(
            `${API_URL}/teacher-courses/${encodeURIComponent(teacherCode)}/${encodeURIComponent(courseCode)}/marks`,
            {
                headers: {
                    "Authorization": `Bearer ${localStorage.getItem("access_token")}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load student marks.");
        }

        displayStudents(data.students || []);

        marksMessage.textContent =
            `${data.students.length} student(s) loaded successfully.`;

    } catch (error) {
        marksTableBody.innerHTML = `
            <tr>
                <td colspan="10" class="p-10 text-center text-red-600">
                    ${escapeHTML(error.message)}
                </td>
            </tr>
        `;

        marksMessage.textContent = error.message;
    }
}


// Display students in the table
function displayStudents(students) {

    marksTableBody.innerHTML = "";

    if (students.length === 0) {
        marksTableBody.innerHTML = `
            <tr>
                <td colspan="10" class="p-10 text-center text-slate-500">
                    No students enrolled in this course.
                </td>
            </tr>
        `;
        return;
    }

    students.forEach(student => {

        const row = document.createElement("tr");

        row.className = "border-t hover:bg-slate-50";

        const assignment = student.assignment_marks ?? "";
        const classTest = student.class_test_marks ?? "";
        const midterm = student.midterm_marks ?? "";
        const final = student.final_marks ?? "";

        const total = student.total_marks ?? "—";
        const grade = student.grade ?? "Pending";
        const gp = student.grade_point ?? "—";

        row.innerHTML = `
            <td class="p-4 font-medium">
                ${escapeHTML(student.student_id)}
            </td>

            <td class="p-4">
                ${escapeHTML(student.name)}
            </td>

            <td class="p-4">
                <input type="number" min="0" max="10" step="0.01"
                    class="marks-input"
                    data-field="assignment"
                    value="${assignment}"
                    placeholder="0-10">
            </td>

            <td class="p-4">
                <input type="number" min="0" max="20" step="0.01"
                    class="marks-input"
                    data-field="class_test"
                    value="${classTest}"
                    placeholder="0-20">
            </td>

            <td class="p-4">
                <input type="number" min="0" max="40" step="0.01"
                    class="marks-input"
                    data-field="midterm"
                    value="${midterm}"
                    placeholder="0-40">
            </td>

            <td class="p-4">
                <input type="number" min="0" max="80" step="0.01"
                    class="marks-input"
                    data-field="final"
                    value="${final}"
                    placeholder="0-80">
            </td>

            <td class="p-4 font-semibold total-cell">
                ${total}
            </td>

            <td class="p-4 grade-cell">
                ${grade}
            </td>

            <td class="p-4 gp-cell">
                ${gp}
            </td>

            <td class="p-4">
                <button
                    type="button"
                    class="save-marks-btn rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
                    data-student-id="${escapeHTML(student.student_id)}"
                >
                    Save
                </button>
            </td>
        `;

        marksTableBody.appendChild(row);
    });
}


// Save or update marks
async function saveStudentMarks(button) {

    const teacherCode = teacherCodeInput.value.trim();
    const courseCode = courseSelect.value;
    const studentId = button.dataset.studentId;

    const row = button.closest("tr");

    const inputs = row.querySelectorAll(".marks-input");

    const marks = {};

    const fieldNames = {
        assignment: "assignment_marks",
        class_test: "class_test_marks",
        midterm: "midterm_marks",
        final: "final_marks"
    };

    for (const input of inputs) {

        if (input.value.trim() === "") {
            marksMessage.textContent =
                "Please enter all four marks before saving.";
            input.focus();
            return;
        }

        const value = Number(input.value);
        const max = Number(input.max);

        if (!Number.isFinite(value) || value < 0 || value > max) {
            marksMessage.textContent =
                `Invalid marks. Maximum allowed: ${max}.`;
            input.focus();
            return;
        }

        marks[fieldNames[input.dataset.field]] = value;
    }

    button.disabled = true;
    button.textContent = "Saving...";

    try {

        const response = await fetch(
            `${API_URL}/teacher-courses/${encodeURIComponent(teacherCode)}/${encodeURIComponent(courseCode)}/marks/${encodeURIComponent(studentId)}`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${localStorage.getItem("access_token")}`
                },
                body: JSON.stringify(marks)
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to save marks.");
        }

        const saved = data.marks;

        row.querySelector(".total-cell").textContent =
            saved.total_marks;

        row.querySelector(".grade-cell").textContent =
            saved.grade;

        row.querySelector(".gp-cell").textContent =
            saved.grade_point;

        marksMessage.textContent =
            `Marks saved successfully for ${studentId}.`;

        button.textContent = "Saved";

    } catch (error) {

        marksMessage.textContent = error.message;
        button.textContent = "Save";

    } finally {
        button.disabled = false;
    }
}


// Prevent HTML injection in displayed text
function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}


// Button events
loadCoursesBtn.addEventListener("click", loadTeacherCourses);

courseSelect.addEventListener("change", loadCourseMarks);


// Save button event (event delegation)
marksTableBody.addEventListener("click", function (event) {

    const button = event.target.closest(".save-marks-btn");

    if (button) {
        saveStudentMarks(button);
    }

});
