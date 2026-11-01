
const API_URL = "http://127.0.0.1:8000";

const tableBody = document.getElementById("studentTableBody");
const totalStudents = document.getElementById("totalStudents");
const message = document.getElementById("message");
const searchInput = document.getElementById("searchInput");

const modal = document.getElementById("studentModal");
const form = document.getElementById("studentForm");
const formMessage = document.getElementById("formMessage");

const addButton = document.getElementById("addStudentBtn");
const cancelButton = document.getElementById("cancelStudentBtn");

async function loadStudents() {
    try {
        const response = await fetch(`${API_URL}/students`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        const students = data.students;

        totalStudents.textContent = students.length;
        tableBody.innerHTML = "";

        students.forEach(student => {
            const row = document.createElement("tr");
            row.className = "border-t hover:bg-slate-50";

            [student.id, student.student_id, student.name, student.email]
                .forEach(value => {
                    const cell = document.createElement("td");
                    cell.className = "px-6 py-4";
                    cell.textContent = value ?? "";
                    row.appendChild(cell);
                });

            const actions = document.createElement("td");
            actions.className = "px-6 py-4 whitespace-nowrap";

            const editButton = document.createElement("button");
            editButton.textContent = "Edit";
            editButton.className = "mr-3 text-blue-600";
            editButton.onclick = () => editStudent(student);

            const deleteButton = document.createElement("button");
            deleteButton.textContent = "Delete";
            deleteButton.className = "text-red-600";
            deleteButton.onclick = () => deleteStudent(student.student_id);

            actions.append(editButton, deleteButton);
            row.appendChild(actions);
            tableBody.appendChild(row);
        });

        filterStudents();
        message.textContent = "Student data loaded successfully.";

    } catch (error) {
        console.error(error);
        message.textContent =
            "Could not load students. Check backend and CORS.";
    }
}


// Open the Add Student modal
addButton.addEventListener("click", () => {
    form.reset();
    formMessage.textContent = "";

    modal.classList.remove("hidden");
    modal.classList.add("flex");
});

// Close the modal
cancelButton.addEventListener("click", () => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
});



function filterStudents() {
    const term = searchInput.value.toLowerCase();

    tableBody.querySelectorAll("tr").forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(term)
            ? ""
            : "none";
    });
}

searchInput.addEventListener("input", filterStudents);

addButton.addEventListener("click", () => {
    form.reset();
    formMessage.textContent = "";
    modal.classList.remove("hidden");
    modal.classList.add("flex");
});

cancelButton.addEventListener("click", closeModal);

function closeModal() {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    form.reset();
    formMessage.textContent = "";
}

form.addEventListener("submit", async event => {
    event.preventDefault();

    const student = {
        student_id: document.getElementById("studentId").value.trim(),
        name: document.getElementById("studentName").value.trim(),
        email: document.getElementById("studentEmail").value.trim()
    };

    try {
        const response = await fetch(`${API_URL}/students`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(student)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || `HTTP ${response.status}`);
        }

        closeModal();
        await loadStudents();
        message.textContent = "Student registered successfully.";

    } catch (error) {
        formMessage.textContent = error.message;
    }
});

async function editStudent(student) {
    const name = prompt("Enter new name:", student.name);
    if (name === null) return;

    const email = prompt("Enter new email:", student.email);
    if (email === null) return;

    try {
        const response = await fetch(
            `${API_URL}/students/${encodeURIComponent(student.student_id)}`,
            {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: name.trim(),
                    email: email.trim()
                })
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || `HTTP ${response.status}`);
        }

        await loadStudents();
        message.textContent = "Student updated successfully.";

    } catch (error) {
        alert(`Update failed: ${error.message}`);
    }
}

async function deleteStudent(studentId) {
    if (!confirm(`Delete student ${studentId}?`)) return;

    try {
        const response = await fetch(
            `${API_URL}/students/${encodeURIComponent(studentId)}`,
            { method: "DELETE" }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || `HTTP ${response.status}`);
        }

        await loadStudents();
        message.textContent = "Student deleted successfully.";

    } catch (error) {
        alert(`Delete failed: ${error.message}`);
    }
}

loadStudents();




// ================================
// TEACHER MARKS MANAGEMENT
// ================================

const teacherCodeInput = document.getElementById("teacherCode");
const loadCoursesBtn = document.getElementById("loadTeacherCoursesBtn");
const courseSelect = document.getElementById("marksCourseSelect");
const marksTableBody = document.getElementById("marksTableBody");
const marksMessage = document.getElementById("marksMessage");

// Load courses assigned to a teacher
async function loadTeacherCourses() {
    const teacherCode = teacherCodeInput.value.trim();

    if (!teacherCode) {
        marksMessage.textContent = "Please enter a teacher code.";
        return;
    }

    try {
        marksMessage.textContent = "Loading courses...";

        const response = await fetch(
            `${API_URL}/teacher-courses/${encodeURIComponent(teacherCode)}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Could not load courses.");
        }

        courseSelect.innerHTML = "";

        if (data.courses.length === 0) {
            courseSelect.add(new Option("No assigned courses found", ""));
            courseSelect.disabled = true;
            marksMessage.textContent = "This teacher has no assigned courses.";
            return;
        }

        courseSelect.add(new Option("Select a course", ""));

        data.courses.forEach(course => {
            const option = new Option(
                `${course.course_code} - ${course.course_name}`,
                course.course_code
            );

            courseSelect.add(option);
        });

        courseSelect.disabled = false;
        marksMessage.textContent =
            `${data.courses.length} course(s) loaded successfully.`;

    } catch (error) {
        console.error(error);
        marksMessage.textContent = error.message;
    }
}


// Load students and their marks for selected course
async function loadCourseMarks() {
    const teacherCode = teacherCodeInput.value.trim();
    const courseCode = courseSelect.value;

    if (!teacherCode || !courseCode) {
        return;
    }

    try {
        marksMessage.textContent = "Loading student marks...";

        marksTableBody.innerHTML = "";

        const response = await fetch(
            `${API_URL}/teacher-courses/${encodeURIComponent(teacherCode)}/${encodeURIComponent(courseCode)}/marks`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Could not load marks.");
        }

        if (data.students.length === 0) {
            marksTableBody.innerHTML = `
                <tr>
                    <td colspan="10" class="px-4 py-10 text-center text-slate-500">
                        No students enrolled in this course.
                    </td>
                </tr>
            `;

            marksMessage.textContent = "No students found.";
            return;
        }

        data.students.forEach(student => {
            const row = document.createElement("tr");
            row.className = "border-t hover:bg-slate-50";

            // Student ID
            const idCell = document.createElement("td");
            idCell.className = "px-4 py-4 whitespace-nowrap";
            idCell.textContent = student.student_id;

            // Student name
            const nameCell = document.createElement("td");
            nameCell.className = "px-4 py-4 whitespace-nowrap";
            nameCell.textContent = student.name;

            // Marks input fields
            const assignmentInput = createMarksInput(
                student.assignment_marks, 10
            );

            const classTestInput = createMarksInput(
                student.class_test_marks, 20
            );

            const midtermInput = createMarksInput(
                student.midterm_marks, 40
            );

            const finalInput = createMarksInput(
                student.final_marks, 80
            );

            const assignmentCell = createInputCell(assignmentInput);
            const classTestCell = createInputCell(classTestInput);
            const midtermCell = createInputCell(midtermInput);
            const finalCell = createInputCell(finalInput);

            // Total, Grade and GP
            const totalCell = document.createElement("td");
            totalCell.className = "px-4 py-4 font-semibold";
            totalCell.textContent = student.total_marks ?? "—";

            const gradeCell = document.createElement("td");
            gradeCell.className = "px-4 py-4 font-semibold";
            gradeCell.textContent = student.grade ?? "—";

            const gpCell = document.createElement("td");
            gpCell.className = "px-4 py-4";
            gpCell.textContent = student.grade_point ?? "—";

            // Save button
            const actionCell = document.createElement("td");
            actionCell.className = "px-4 py-4";

            const saveButton = document.createElement("button");
            saveButton.textContent = "Save";
            saveButton.className =
                "rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700";

            saveButton.addEventListener("click", () => {
                saveStudentMarks(
                    student.student_id,
                    assignmentInput,
                    classTestInput,
                    midtermInput,
                    finalInput,
                    saveButton
                );
            });

            actionCell.appendChild(saveButton);

            row.append(
                idCell,
                nameCell,
                assignmentCell,
                classTestCell,
                midtermCell,
                finalCell,
                totalCell,
                gradeCell,
                gpCell,
                actionCell
            );

            marksTableBody.appendChild(row);
        });

        marksMessage.textContent =
            `${data.students.length} student(s) loaded successfully.`;

    } catch (error) {
        console.error(error);
        marksMessage.textContent = error.message;
    }
}


// Create a marks input
function createMarksInput(value, max) {
    const input = document.createElement("input");

    input.type = "number";
    input.min = "0";
    input.max = String(max);
    input.step = "0.01";
    input.value = value ?? 0;

    input.className =
        "w-24 rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-blue-500";

    return input;
}


// Create table cell for an input
function createInputCell(input) {
    const cell = document.createElement("td");
    cell.className = "px-4 py-4";
    cell.appendChild(input);
    return cell;
}


// Save or update student marks
async function saveStudentMarks(
    studentId,
    assignmentInput,
    classTestInput,
    midtermInput,
    finalInput,
    saveButton
) {
    const teacherCode = teacherCodeInput.value.trim();
    const courseCode = courseSelect.value;

    const marks = {
        assignment_marks: Number(assignmentInput.value),
        class_test_marks: Number(classTestInput.value),
        midterm_marks: Number(midtermInput.value),
        final_marks: Number(finalInput.value)
    };

    // Frontend validation
    if (
        marks.assignment_marks < 0 || marks.assignment_marks > 10 ||
        marks.class_test_marks < 0 || marks.class_test_marks > 20 ||
        marks.midterm_marks < 0 || marks.midterm_marks > 40 ||
        marks.final_marks < 0 || marks.final_marks > 80 ||
        Object.values(marks).some(value => !Number.isFinite(value))
    ) {
        alert("Please enter valid marks within the allowed limits.");
        return;
    }

    try {
        saveButton.disabled = true;
        saveButton.textContent = "Saving...";

        const response = await fetch(
            `${API_URL}/teacher-courses/${encodeURIComponent(teacherCode)}/${encodeURIComponent(courseCode)}/marks/${encodeURIComponent(studentId)}`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(marks)
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Could not save marks.");
        }

        marksMessage.textContent =
            `Marks saved successfully for ${studentId}.`;

        // Refresh table to show calculated total, grade and GP
        await loadCourseMarks();

    } catch (error) {
        console.error(error);
        alert(`Save failed: ${error.message}`);

        saveButton.disabled = false;
        saveButton.textContent = "Save";
    }
}


// Button and dropdown events
loadCoursesBtn.addEventListener("click", loadTeacherCourses);

courseSelect.addEventListener("change", loadCourseMarks);
