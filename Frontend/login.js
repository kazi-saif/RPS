const API_URL = "http://127.0.0.1:8000";

const loginForm = document.getElementById("loginForm");
const loginMessage = document.getElementById("loginMessage");
const loginButton = document.getElementById("loginButton");

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    loginMessage.textContent = "";
    loginButton.disabled = true;
    loginButton.textContent = "Signing in...";

    try {
        const formData = new URLSearchParams();
        formData.append("username", username);
        formData.append("password", password);

        const response = await fetch(`${API_URL}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Login failed.");
        }

        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("username", data.username);
        localStorage.setItem("role", data.role);

        if (data.role === "admin") {
            window.location.href = "index.html";
        } else if (data.role === "teacher") {
            window.location.href = "teacher-marks.html";
        } else if (data.role === "student") {
            window.location.href = "results.html";
        } else {
            throw new Error("Unknown user role.");
        }

    } catch (error) {
        console.error(error);
        loginMessage.textContent = error.message;

        loginButton.disabled = false;
        loginButton.textContent = "Sign In";
    }
});