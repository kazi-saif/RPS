
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
