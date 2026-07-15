const API_BASE_URL = "/api/v1";

function getAccessToken() {
    return localStorage.getItem("accessToken");
}

function getRefreshToken() {
    return localStorage.getItem("refreshToken");
}

function setTokens(access, refresh) {
    if (access) {
        localStorage.setItem("accessToken", access);
    }

    if (refresh) {
        localStorage.setItem("refreshToken", refresh);
    }
}

function clearTokens() {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("currentUser");
}

function getCurrentUser() {
    const user = localStorage.getItem("currentUser");

    if (!user) {
        return null;
    }

    return JSON.parse(user);
}

function setCurrentUser(user) {
    localStorage.setItem("currentUser", JSON.stringify(user));
}

function getAuthHeaders() {
    return {
        "Authorization": `Bearer ${getAccessToken()}`,
        "Content-Type": "application/json",
    };
}

let isRefreshing = false;
let refreshSubscribers = [];

function subscribeTokenRefresh(cb) {
    refreshSubscribers.push(cb);
}

function onRefreshed(token) {
    refreshSubscribers.forEach((cb) => cb(token));
    refreshSubscribers = [];
}

function onRefreshError(err) {
    refreshSubscribers.forEach((cb) => cb(null, err));
    refreshSubscribers = [];
}

async function apiRequest(url, options = {}) {
    // Ensure we send the most current token if Authorization header is set
    if (options.headers && options.headers["Authorization"]) {
        options.headers["Authorization"] = `Bearer ${getAccessToken()}`;
    }

    const response = await fetch(`${API_BASE_URL}${url}`, options);

    // Try token refresh on 401 Unauthorized
    if (response.status === 401 && !url.includes("/auth/login/") && !url.includes("/auth/token/refresh/")) {
        if (isRefreshing) {
            return new Promise((resolve, reject) => {
                subscribeTokenRefresh((token, err) => {
                    if (err) {
                        reject(err);
                    } else {
                        if (options.headers) {
                            options.headers["Authorization"] = `Bearer ${token}`;
                        }
                        resolve(apiRequest(url, options));
                    }
                });
            });
        }

        isRefreshing = true;

        try {
            const refreshToken = getRefreshToken();
            if (!refreshToken) {
                throw new Error("No refresh token available");
            }

            const refreshResponse = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ refresh: refreshToken }),
            });

            if (!refreshResponse.ok) {
                throw new Error("Refresh token expired or invalid");
            }

            const refreshData = await refreshResponse.json();
            setTokens(refreshData.access, refreshData.refresh);
            isRefreshing = false;
            onRefreshed(refreshData.access);

            if (options.headers) {
                options.headers["Authorization"] = `Bearer ${refreshData.access}`;
            }
            return await apiRequest(url, options);

        } catch (error) {
            isRefreshing = false;
            onRefreshError(error);
            clearTokens();
            window.location.href = "/login/";
            throw error;
        }
    }

    let data = null;

    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (!response.ok) {
        throw data || {
            detail: "Something went wrong."
        };
    }

    return data;
}

function showAlert(targetId, message, type = "danger") {
    const target = document.getElementById(targetId);

    if (!target) {
        return;
    }

    // Map Bootstrap type names to our Tailwind alert classes
    const iconMap = {
        danger:  'alert-triangle',
        success: 'check-circle',
        warning: 'alert-circle',
        info:    'info',
    };
    const classMap = {
        danger:  'app-alert-danger',
        success: 'app-alert-success',
        warning: 'app-alert-warning',
        info:    'app-alert-info',
    };
    const icon  = iconMap[type]  || 'alert-triangle';
    const cls   = classMap[type] || 'app-alert-danger';

    target.innerHTML = `
        <div class="app-alert ${cls}" role="alert">
            <i data-lucide="${icon}" style="width:16px;height:16px;flex-shrink:0;margin-top:2px;"></i>
            <span>${message}</span>
            <button type="button" onclick="this.parentElement.remove()"
                    style="margin-left:auto;flex-shrink:0;opacity:0.6;cursor:pointer;background:none;border:none;color:inherit;font-size:1rem;line-height:1;">
                &times;
            </button>
        </div>
    `;

    // Re-render Lucide icons in the new markup
    if (window.lucide) {
        lucide.createIcons({ nodes: target.querySelectorAll('[data-lucide]') });
    }
}

function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) {
        return;
    }

    const iconMap = {
        danger:  "alert-triangle",
        success: "check-circle",
        warning: "alert-circle",
        info:    "message-square",
    };
    const classMap = {
        danger:  "app-toast-danger",
        success: "app-toast-success",
        warning: "app-toast-warning",
        info:    "app-toast-info",
    };

    const toast = document.createElement("div");
    toast.className = `app-toast ${classMap[type] || classMap.info}`;
    toast.innerHTML = `
        <div class="app-toast-icon">
            <i data-lucide="${iconMap[type] || iconMap.info}" class="w-4 h-4"></i>
        </div>
        <div class="app-toast-body">
            <p class="app-toast-title">ChatApp</p>
            <p class="app-toast-message"></p>
        </div>
    `;

    toast.querySelector(".app-toast-message").textContent = message;
    container.appendChild(toast);

    if (window.lucide) {
        lucide.createIcons({ nodes: toast.querySelectorAll('[data-lucide]') });
    }

    requestAnimationFrame(() => {
        toast.classList.add("app-toast-visible");
    });

    setTimeout(() => {
        toast.classList.remove("app-toast-visible");
        setTimeout(() => toast.remove(), 180);
    }, 3500);
}

function formatApiError(error) {
    if (!error) {
        return "Something went wrong.";
    }

    if (error.detail) {
        return error.detail;
    }

    if (error.non_field_errors) {
        return error.non_field_errors.join(", ");
    }

    const messages = [];

    Object.keys(error).forEach((key) => {
        if (Array.isArray(error[key])) {
            messages.push(`${key}: ${error[key].join(", ")}`);
        } else {
            messages.push(`${key}: ${error[key]}`);
        }
    });

    return messages.join("<br>") || "Something went wrong.";
}