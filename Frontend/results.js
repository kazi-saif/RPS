
const API_URL = "http://127.0.0.1:8000";

// HTML Elements
const departmentSelect = document.getElementById("departmentSelect");
const sessionSelect = document.getElementById("sessionSelect");
const semesterSelect = document.getElementById("resultSemesterSelect");
const studentIdInput = document.getElementById("resultStudentId");
const loadResultsBtn = document.getElementById("loadResultsBtn");
const resultMessage = document.getElementById("resultMessage");

const studentName = document.getElementById("resultStudentName");
const studentCode = document.getElementById("resultStudentCode");
const cgpaElement = document.getElementById("resultCgpa");
const semesterGpa = document.getElementById("semesterGpa");
const resultTableBody = document.getElementById("resultTableBody");


// Clear previous results
function clearResults() {
    studentName.textContent = "—";
    studentCode.textContent = "Student ID: —";
    cgpaElement.textContent = "—";
    semesterGpa.textContent = "—";

    resultTableBody.innerHTML = `
        <tr>
            <td colspan="10" class="px-4 py-10 text-center text-slate-500">
                No results loaded.
            </td>
        </tr>
    `;
}


// Load student results
async function loadStudentResults() {

    const studentId = studentIdInput.value.trim();
    const departmentId = departmentSelect.value;
    const sessionId = sessionSelect.value;
    const semester = semesterSelect.value;

    if (!departmentId || !sessionId || !semester || !studentId) {
        resultMessage.textContent =
            "Please select department, session, semester and enter Student ID.";
        resultMessage.className = "mt-3 text-sm text-red-600";
        return;
    }

    loadResultsBtn.disabled = true;
    loadResultsBtn.textContent = "Loading...";
    resultMessage.textContent = "Loading student results...";
    resultMessage.className = "mt-3 text-sm text-blue-600";

    clearResults();

    try {

        const url =
            `${API_URL}/student-results/${encodeURIComponent(studentId)}` +
            `?department_id=${encodeURIComponent(departmentId)}` +
            `&session_id=${encodeURIComponent(sessionId)}` +
            `&semester=${encodeURIComponent(semester)}`;

        const response = await fetch(url);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Could not load student results.");
        }

        // Student information
        studentName.textContent = data.student.name;
        studentCode.textContent = `Student ID: ${data.student.student_id}`;

        cgpaElement.textContent =
            data.cgpa !== null && data.cgpa !== undefined
                ? Number(data.cgpa).toFixed(2)
                : "N/A";

        // Selected semester result
        const semesterData = data.semesters?.[0];

        if (!semesterData || !semesterData.courses) {

            semesterGpa.textContent = "N/A";

            resultTableBody.innerHTML = `
                <tr>
                    <td colspan="10" class="px-4 py-10 text-center text-slate-500">
                        No courses found in Semester ${semester}.
                    </td>
                </tr>
            `;

            resultMessage.textContent =
                "Student found, but no results available for this semester.";
            resultMessage.className = "mt-3 text-sm text-orange-600";

            return;
        }

        // Semester GPA
        semesterGpa.textContent =
            semesterData.gpa !== null && semesterData.gpa !== undefined
                ? Number(semesterData.gpa).toFixed(2)
                : "N/A";

        // Course results
        if (semesterData.courses.length === 0) {

            resultTableBody.innerHTML = `
                <tr>
                    <td colspan="10" class="px-4 py-10 text-center text-slate-500">
                        No courses found in this semester.
                    </td>
                </tr>
            `;

        } else {

            resultTableBody.innerHTML = semesterData.courses.map(course => {

                const values = [
                    course.course_code,
                    course.course_name,
                    course.credit,
                    course.assignment_marks ?? "—",
                    course.class_test_marks ?? "—",
                    course.midterm_marks ?? "—",
                    course.final_marks ?? "—",
                    course.total_marks ?? "—",
                    course.grade ?? "Pending",
                    course.grade_point !== null && course.grade_point !== undefined
                        ? Number(course.grade_point).toFixed(2)
                        : "—"
                ];

                return `
                    <tr class="border-t hover:bg-slate-50">
                        ${values.map(value => `
                            <td class="px-4 py-4 whitespace-nowrap">
                                ${escapeHTML(value)}
                            </td>
                        `).join("")}
                    </tr>
                `;

            }).join("");
        }

        resultMessage.textContent = "Results loaded successfully.";
        resultMessage.className = "mt-3 text-sm text-green-600";

    } catch (error) {

        console.error(error);
        clearResults();

        resultMessage.textContent = error.message;
        resultMessage.className = "mt-3 text-sm text-red-600";

    } finally {

        loadResultsBtn.disabled = false;
        loadResultsBtn.textContent = "View Results";

    }
}


// Escape HTML
function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => {
        const characters = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        };

        return characters[character];
    });
}


// Event listeners
loadResultsBtn.addEventListener("click", loadStudentResults);

studentIdInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
        loadStudentResults();
    }
});
