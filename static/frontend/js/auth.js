document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");

    if (loginForm) {
        loginForm.addEventListener("submit", loginUser);
    }

    if (registerForm) {
        registerForm.addEventListener("submit", registerUser);
    }
});

async function loginUser(event) {
    event.preventDefault();

    const payload = {
        identifier: document.getElementById("identifier").value,
        password: document.getElementById("password").value,
    };

    try {
        const data = await apiRequest("/auth/login/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        setTokens(data.access, data.refresh);
        setCurrentUser(data.user);

        window.location.href = "/dashboard/chat/";
    } catch (error) {
        showAlert("loginAlert", formatApiError(error));
    }
}

async function registerUser(event) {
    event.preventDefault();

    const payload = {
        name: document.getElementById("name").value,
        username: document.getElementById("username").value,
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
        password2: document.getElementById("password2").value,
    };

    try {
        await apiRequest("/auth/register/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        showAlert(
            "registerAlert",
            "Account created successfully. Please login.",
            "success"
        );

        setTimeout(() => {
            window.location.href = "/login/";
        }, 900);
    } catch (error) {
        showAlert("registerAlert", formatApiError(error));
    }
}

async function logoutUser() {
    const refresh = getRefreshToken();

    try {
        if (refresh) {
            await apiRequest("/auth/logout/", {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    refresh: refresh,
                }),
            });
        }
    } catch (error) {
        console.warn(error);
    }

    localStorage.removeItem("pingnest-active-room");
    clearTokens();
    window.location.href = "/login/";
}
