
// =====================================
// STUDENT RESULT MANAGEMENT
// =====================================

const API_URL = "http://127.0.0.1:8000";

// HTML Elements
const studentIdInput = document.getElementById("resultStudentId");
const loadResultsBtn = document.getElementById("loadResultsBtn");
const resultMessage = document.getElementById("resultMessage");

const studentName = document.getElementById("resultStudentName");
const studentCode = document.getElementById("resultStudentCode");
const cgpaElement = document.getElementById("resultCgpa");

const semesterSelect = document.getElementById("resultSemesterSelect");
const semesterGpa = document.getElementById("semesterGpa");

const resultTableBody = document.getElementById("resultTableBody");

// Store loaded result data
let studentResults = [];


// =====================================
// LOAD STUDENT RESULTS FROM BACKEND
// =====================================

async function loadStudentResults() {

    const studentId = studentIdInput.value.trim();

    if (!studentId) {
        resultMessage.textContent = "Please enter a Student ID.";
        return;
    }

    try {

        loadResultsBtn.disabled = true;
        loadResultsBtn.textContent = "Loading...";
        resultMessage.textContent = "Loading student results...";

        const response = await fetch(
            `${API_URL}/student-results/${encodeURIComponent(studentId)}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Could not load student results.");
        }

        // Save result data
        studentResults = data.semesters;

        // Display student information
        studentName.textContent = data.student.name;
        studentCode.textContent = `Student ID: ${data.student.student_id}`;

        cgpaElement.textContent =
            data.cgpa !== null ? Number(data.cgpa).toFixed(2) : "N/A";

        // Load semester dropdown
        semesterSelect.innerHTML = "";

        if (studentResults.length === 0) {

            semesterSelect.add(new Option("No semester results found", ""));
            semesterSelect.disabled = true;

            semesterGpa.textContent = "N/A";

            resultTableBody.innerHTML = `
                <tr>
                    <td colspan="10" class="px-4 py-10 text-center text-slate-500">
                        No enrolled courses found for this student.
                    </td>
                </tr>
            `;

            resultMessage.textContent = "Student found, but no course results are available.";
            return;
        }

        studentResults.forEach(semester => {

            const option = new Option(
                `Semester ${semester.semester}`,
                semester.semester
            );

            semesterSelect.add(option);

        });

        semesterSelect.disabled = false;

        // Show first semester automatically
        semesterSelect.value = String(studentResults[0].semester);

        displaySemesterResults();

        resultMessage.textContent = "Student results loaded successfully.";

    } catch (error) {

        console.error(error);

        resultMessage.textContent = error.message;

        studentName.textContent = "—";
        studentCode.textContent = "Student ID: —";
        cgpaElement.textContent = "—";
        semesterGpa.textContent = "—";

        semesterSelect.innerHTML =
            '<option value="">No results available</option>';

        semesterSelect.disabled = true;

        resultTableBody.innerHTML = `
            <tr>
                <td colspan="10" class="px-4 py-10 text-center text-red-500">
                    ${error.message}
                </td>
            </tr>
        `;

    } finally {

        loadResultsBtn.disabled = false;
        loadResultsBtn.textContent = "View Results";

    }
}


// =====================================
// DISPLAY SELECTED SEMESTER RESULTS
// =====================================

function displaySemesterResults() {

    const selectedSemester = Number(semesterSelect.value);

    const semesterData = studentResults.find(
        semester => semester.semester === selectedSemester
    );

    if (!semesterData) {
        return;
    }

    // Display semester GPA
    semesterGpa.textContent =
        semesterData.gpa !== null
            ? Number(semesterData.gpa).toFixed(2)
            : "N/A";

    // Clear old table rows
    resultTableBody.innerHTML = "";

    // Check course availability
    if (semesterData.courses.length === 0) {

        resultTableBody.innerHTML = `
            <tr>
                <td colspan="10" class="px-4 py-10 text-center text-slate-500">
                    No courses found in this semester.
                </td>
            </tr>
        `;

        return;
    }

    // Display each course
    semesterData.courses.forEach(course => {

        const row = document.createElement("tr");

        row.className = "border-t hover:bg-slate-50";

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
            course.grade_point !== null
                ? Number(course.grade_point).toFixed(2)
                : "—"
        ];

        values.forEach(value => {

            const cell = document.createElement("td");

            cell.className = "px-4 py-4 whitespace-nowrap";

            cell.textContent = value;

            row.appendChild(cell);

        });

        resultTableBody.appendChild(row);

    });

}


// =====================================
// EVENT LISTENERS
// =====================================

loadResultsBtn.addEventListener("click", loadStudentResults);

semesterSelect.addEventListener("change", displaySemesterResults);

// Press Enter to search
studentIdInput.addEventListener("keydown", event => {

    if (event.key === "Enter") {
        loadStudentResults();
    }

});
