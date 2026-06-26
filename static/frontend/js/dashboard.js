document.addEventListener("DOMContentLoaded", () => {
    if (!getAccessToken()) {
        window.location.href = "/login/";
        return;
    }

    loadMyProfile();
    loadIncomingRequests();
    loadConnections();
    loadChatRooms();
    loadNotifications();
    loadBlockedUsers();
    loadRestrictedUsers();
    connectNotificationSocket();

    // ── Load suggestions when dashboard opens ──────────────────────────────
    loadSuggestedUsers();

    const profileForm     = document.getElementById("profileForm");
    const sendRequestForm = document.getElementById("sendRequestForm");
    const startChatForm   = document.getElementById("startChatForm");

    if (profileForm) {
        profileForm.addEventListener("submit", updateProfile);
    }

    if (sendRequestForm) {
        sendRequestForm.addEventListener("submit", sendConnectionRequest);
    }

    if (startChatForm) {
        startChatForm.addEventListener("submit", startOneToOneChat);
    }
});

// ─── Section switching ────────────────────────────────────────────────────────
function showSection(sectionId, button) {
    document.querySelectorAll(".content-section").forEach((section) => {
        section.classList.add("hidden");
    });

    const target = document.getElementById(sectionId);
    if (target) {
        target.classList.remove("hidden");
    }

    document.querySelectorAll(".nav-item").forEach((item) => {
        item.classList.remove("active");
    });

    if (button) {
        button.classList.add("active");
    }

    // Close mobile sidebar after navigation
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");
    if (sidebar && sidebar.classList.contains("translate-x-0")) {
        sidebar.classList.add("-translate-x-full");
        if (overlay) overlay.classList.add("hidden");
    }
}

// ─── Profile ─────────────────────────────────────────────────────────────────
async function loadMyProfile() {
    try {
        const profile = await apiRequest("/profiles/me/", {
            method: "GET",
            headers: getAuthHeaders(),
        });

        document.getElementById("profileBio").value             = profile.bio || "";
        document.getElementById("accountVisibility").value      = profile.account_visibility || "public";
        document.getElementById("lastSeenVisibility").value     = profile.last_seen_visibility || "connections";
        document.getElementById("readReceiptsEnabled").checked  = Boolean(profile.read_receipts_enabled);

        if (profile.profile_picture_url) {
            document.getElementById("profileImage").src = profile.profile_picture_url;
        }
    } catch (error) {
        showAlert("profileAlert", formatApiError(error));
    }
}

async function updateProfile(event) {
    event.preventDefault();

    const formData = new FormData();
    formData.append("bio",                   document.getElementById("profileBio").value);
    formData.append("account_visibility",    document.getElementById("accountVisibility").value);
    formData.append("last_seen_visibility",  document.getElementById("lastSeenVisibility").value);
    formData.append("read_receipts_enabled", document.getElementById("readReceiptsEnabled").checked ? "true" : "false");

    const profilePicture = document.getElementById("profilePicture").files[0];
    if (profilePicture) {
        formData.append("profile_picture", profilePicture);
    }

    try {
        await apiRequest("/profiles/me/", {
            method: "PATCH",
            headers: { "Authorization": `Bearer ${getAccessToken()}` },
            body: formData,
        });

        showAlert("profileAlert", "Profile updated successfully.", "success");
        loadMyProfile();
    } catch (error) {
        showAlert("profileAlert", "Profile update failed.");
    }
}

// ─── Connections ──────────────────────────────────────────────────────────────
async function sendConnectionRequest(event) {
    event.preventDefault();

    const username = document.getElementById("requestUsername").value;

    try {
        await apiRequest("/connection-requests/send/", {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ username: username }),
        });

        showAlert("profileAlert", "Connection request sent.", "success");
        document.getElementById("requestUsername").value = "";
        loadSuggestedUsers();
    } catch (error) {
        showAlert("profileAlert", formatApiError(error));
    }
}

async function loadIncomingRequests() {
    const container = document.getElementById("incomingRequestsList");
    if (!container) return;

    try {
        const requests = await apiRequest("/connection-requests/incoming/", {
            method: "GET",
            headers: getAuthHeaders(),
        });

        if (!requests.length) {
            container.innerHTML = `
                <p class="page-subtext text-sm text-center py-4">No incoming requests.</p>
            `;
            return;
        }

        container.innerHTML = requests.map((request) => `
            <div class="request-item">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-full bg-gradient-to-br from-brand-400 to-purple-500 flex items-center justify-center shrink-0">
                        <i data-lucide="user" style="width:16px;height:16px;color:white;"></i>
                    </div>
                    <div>
                        <div class="text-sm font-semibold page-heading">${request.from_user.username}</div>
                        <div class="text-xs page-subtext">${request.from_user.name || ""}</div>
                    </div>
                </div>
                <div class="flex gap-2">
                    <button onclick="acceptRequest(${request.id})"
                            class="px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 active:scale-[0.97] transition-all duration-200 flex items-center gap-1">
                        <i data-lucide="check" style="width:12px;height:12px;"></i> Accept
                    </button>
                    <button onclick="rejectRequest(${request.id})"
                            class="px-3 py-1.5 rounded-lg text-xs font-semibold text-rose-500 border border-rose-500/40 hover:bg-rose-500/10 active:scale-[0.97] transition-all duration-200 flex items-center gap-1">
                        <i data-lucide="x" style="width:12px;height:12px;"></i> Reject
                    </button>
                </div>
            </div>
        `).join("");

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
    } catch (error) {
        container.innerHTML = `<p class="text-rose-500 text-sm">Failed to load requests.</p>`;
    }
}

async function acceptRequest(requestId) {
    try {
        await apiRequest(`/connection-requests/${requestId}/accept/`, {
            method: "POST",
            headers: getAuthHeaders(),
        });
        loadIncomingRequests();
        loadConnections();
        loadSuggestedUsers();
    } catch (error) {
        alert(formatApiError(error));
    }
}

async function rejectRequest(requestId) {
    try {
        await apiRequest(`/connection-requests/${requestId}/reject/`, {
            method: "POST",
            headers: getAuthHeaders(),
        });
        loadIncomingRequests();
    } catch (error) {
        alert(formatApiError(error));
    }
}

async function loadConnections() {
    const container = document.getElementById("connectionsList");
    if (!container) return;

    try {
        const data = await apiRequest("/connections/", {
            method: "GET",
            headers: getAuthHeaders(),
        });

        const connections = data.results || data;

        if (!connections.length) {
            container.innerHTML = `
                <p class="page-subtext text-sm text-center py-4">No connections yet.</p>
            `;
            return;
        }

        container.innerHTML = connections.map((connection) => `
            <div class="connection-item">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-full bg-gradient-to-br from-purple-400 to-brand-500 flex items-center justify-center shrink-0">
                        <i data-lucide="user" style="width:16px;height:16px;color:white;"></i>
                    </div>
                    <div>
                        <div class="text-sm font-semibold page-heading">${connection.connected_user.username}</div>
                        <div class="text-xs page-subtext">${connection.connected_user.name || ""}</div>
                    </div>
                </div>
                <button onclick="openChatWithUsername('${connection.connected_user.username}')"
                        class="px-3 py-1.5 rounded-lg text-xs font-semibold border active:scale-[0.97] transition-all duration-200 flex items-center gap-1"
                        style="color:var(--clr-brand-light);border-color:rgba(99,102,241,0.4);"
                        onmouseover="this.style.background=getComputedStyle(document.documentElement).getPropertyValue('--clr-brand-bg');"
                        onmouseout="this.style.background='';">
                    <i data-lucide="message-square" style="width:12px;height:12px;"></i> Chat
                </button>
            </div>
        `).join("");

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
    } catch (error) {
        container.innerHTML = `<p class="text-rose-500 text-sm">Failed to load connections.</p>`;
    }
}

// ─── Suggested Users ──────────────────────────────────────────────────────────
// Strategy:
//   1. GET /api/v1/profiles/         → all public profiles
//   2. GET /api/v1/connections/      → already connected user IDs
//   3. GET /api/v1/connection-requests/outgoing/ → pending sent request user IDs
//   Filter out: self, already connected, pending request sent.
//   The profiles API already excludes blocked users server-side.
// ─────────────────────────────────────────────────────────────────────────────
async function loadSuggestedUsers() {
    const container = document.getElementById("suggestedUsersList");
    if (!container) return;

    // Show skeleton while loading
    container.innerHTML = _buildSkeletons(4);

    try {
        const currentUser = getCurrentUser();

        // Fetch in parallel for speed
        const [profilesData, connectionsData, outgoingData] = await Promise.all([
            apiRequest("/profiles/",                         { method: "GET", headers: getAuthHeaders() }),
            apiRequest("/connections/",                      { method: "GET", headers: getAuthHeaders() }),
            apiRequest("/connection-requests/outgoing/",     { method: "GET", headers: getAuthHeaders() }),
        ]);

        const profiles     = profilesData.results    || profilesData;
        const connections  = connectionsData.results  || connectionsData;
        const outgoing     = outgoingData.results     || outgoingData;

        // Build exclusion sets
        const connectedIds = new Set(
            connections.map((c) => c.connected_user?.id).filter(Boolean)
        );
        const pendingIds = new Set(
            outgoing.map((r) => r.to_user?.id).filter(Boolean)
        );

        // Filter suggestions
        const suggestions = profiles.filter((p) => {
            if (!p.id) return false;
            if (p.id === currentUser.id) return false;           // not self
            if (connectedIds.has(p.id))  return false;           // not already connected
            if (pendingIds.has(p.id))    return false;           // not pending
            return true;
        }).slice(0, 8); // show max 8 cards

        if (!suggestions.length) {
            container.innerHTML = `
                <div class="flex flex-col items-center justify-center py-8 text-center">
                    <div class="w-12 h-12 rounded-2xl flex items-center justify-center mb-3"
                         style="background:var(--clr-brand-bg);">
                        <i data-lucide="users" style="width:22px;height:22px;color:var(--clr-brand-light);"></i>
                    </div>
                    <p class="text-sm font-medium page-heading">You're all caught up!</p>
                    <p class="text-xs page-subtext mt-1">No new people to suggest right now.</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
            return;
        }

        container.innerHTML = `
            <div class="suggested-grid">
                ${suggestions.map((profile) => _buildSuggestionCard(profile)).join("")}
            </div>
        `;

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });

    } catch (error) {
        container.innerHTML = `<p class="text-rose-500 text-sm py-3">Failed to load suggestions.</p>`;
    }
}

function _buildSkeletons(count) {
    return `<div class="suggested-grid">
        ${'<div class="suggestion-skeleton"></div>'.repeat(count)}
    </div>`;
}

function _buildSuggestionCard(profile) {
    const initials = (profile.name || profile.username || "?")[0].toUpperCase();
    const avatarBg = profile.profile_picture_url
        ? `url('${profile.profile_picture_url}')`
        : null;

    const avatarHtml = avatarBg
        ? `<div class="suggestion-avatar" style="background-image:${avatarBg};background-size:cover;background-position:center;"></div>`
        : `<div class="suggestion-avatar suggestion-avatar-initials">${initials}</div>`;

    const visibilityBadge = profile.is_private
        ? `<span class="suggestion-badge suggestion-badge-private">
               <i data-lucide="lock" style="width:9px;height:9px;"></i> Private
           </span>`
        : `<span class="suggestion-badge suggestion-badge-public">
               <i data-lucide="globe" style="width:9px;height:9px;"></i> Public
           </span>`;

    const nameDisplay = profile.name
        ? `<p class="text-sm font-semibold page-heading truncate">${profile.name}</p>
           <p class="text-xs page-subtext truncate">@${profile.username}</p>`
        : `<p class="text-sm font-semibold page-heading truncate">@${profile.username}</p>
           <p class="text-xs page-subtext truncate">&nbsp;</p>`;

    return `
        <div class="suggestion-card" id="suggestion-card-${profile.id}">
            ${avatarHtml}
            <div class="mt-3 mb-1 text-center px-2 w-full">
                ${nameDisplay}
            </div>
            <div class="mb-3">${visibilityBadge}</div>
            <button id="suggest-btn-${profile.id}"
                    onclick="sendSuggestedRequest('${profile.username}', ${profile.id}, this)"
                    class="suggestion-btn">
                <i data-lucide="user-plus" style="width:12px;height:12px;"></i>
                Connect
            </button>
        </div>
    `;
}

async function sendSuggestedRequest(username, userId, btn) {
    // Optimistically disable the button
    btn.disabled = true;
    btn.classList.add("suggestion-btn-sent");
    btn.innerHTML = `<i data-lucide="check" style="width:12px;height:12px;"></i> Sent`;
    if (window.lucide) lucide.createIcons({ nodes: [btn] });

    try {
        await apiRequest("/connection-requests/send/", {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ username: username }),
        });

        // Fade out the card smoothly after a short delay
        setTimeout(() => {
            const card = document.getElementById(`suggestion-card-${userId}`);
            if (card) {
                card.style.transition = "opacity 0.4s ease, transform 0.4s ease";
                card.style.opacity    = "0";
                card.style.transform  = "scale(0.9)";
                setTimeout(() => card.remove(), 400);
            }
        }, 800);

    } catch (error) {
        // Revert button if the API call failed
        btn.disabled = false;
        btn.classList.remove("suggestion-btn-sent");
        btn.innerHTML = `<i data-lucide="user-plus" style="width:12px;height:12px;"></i> Connect`;
        if (window.lucide) lucide.createIcons({ nodes: [btn] });
        alert(formatApiError(error));
    }
}

// ─── Notifications ───────────────────────────────────────────────────────────
async function loadNotifications() {
    const container = document.getElementById("notificationsList");
    if (!container) return;

    try {
        const data = await apiRequest("/notifications/", {
            method: "GET",
            headers: getAuthHeaders(),
        });

        const notifications = data.results || data;

        const countData = await apiRequest("/notifications/unread-count/", {
            method: "GET",
            headers: getAuthHeaders(),
        });

        const count = countData.unread_count || 0;

        const badge        = document.getElementById("notificationBadge");
        const sidebarBadge = document.getElementById("sidebarBadge");

        if (badge) {
            badge.innerText = count;
            badge.classList.toggle("hidden", count === 0);
        }
        if (sidebarBadge) {
            sidebarBadge.innerText = count;
            sidebarBadge.classList.toggle("hidden", count === 0);
        }

        if (!notifications.length) {
            container.innerHTML = `
                <div class="notification-card text-center py-8">
                    <i data-lucide="bell-off" style="width:32px;height:32px;color:var(--clr-faint);margin:0 auto 0.75rem;display:block;"></i>
                    <p class="page-subtext text-sm">No notifications yet.</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
            return;
        }

        container.innerHTML = notifications.map((notification) => `
            <div class="notification-card ${notification.is_read ? "" : "notification-unread"}">
                <div class="flex items-start justify-between gap-3">
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                             style="background:${notification.is_read ? "var(--clr-surface2)" : "var(--clr-brand-bg)"};">
                            <i data-lucide="bell" style="width:14px;height:14px;color:${notification.is_read ? "var(--clr-faint)" : "var(--clr-brand-light)"};"></i>
                        </div>
                        <div>
                            <p class="text-sm font-semibold page-heading">${notification.title}</p>
                            <p class="text-xs page-subtext mt-0.5">${notification.body}</p>
                        </div>
                    </div>
                    ${notification.is_read
                        ? `<span class="text-xs page-subtext font-medium shrink-0">Read</span>`
                        : `<button onclick="markNotificationRead(${notification.id})"
                                   class="text-xs border px-2.5 py-1 rounded-lg active:scale-[0.97] transition-all duration-200 shrink-0"
                                   style="color:var(--clr-brand-light);border-color:rgba(99,102,241,0.4);"
                                   onmouseover="this.style.background=getComputedStyle(document.documentElement).getPropertyValue('--clr-brand-bg');"
                                   onmouseout="this.style.background='';">
                               Mark Read
                           </button>`
                    }
                </div>
            </div>
        `).join("");

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
    } catch (error) {
        container.innerHTML = `<p class="text-rose-500 text-sm">Failed to load notifications.</p>`;
    }
}

async function markNotificationRead(notificationId) {
    await apiRequest(`/notifications/${notificationId}/mark-read/`, {
        method: "POST",
        headers: getAuthHeaders(),
    });
    loadNotifications();
}

async function markAllNotificationsRead() {
    await apiRequest("/notifications/mark-all-read/", {
        method: "POST",
        headers: getAuthHeaders(),
    });
    loadNotifications();
}

// ─── Privacy actions ──────────────────────────────────────────────────────────
async function blockUser()      { await userPrivacyAction("/blocks/block/"); }
async function unblockUser()    { await userPrivacyAction("/blocks/unblock/"); loadBlockedUsers(); }
async function restrictUser()   { await userPrivacyAction("/restrictions/restrict/"); }
async function unrestrictUser() { await userPrivacyAction("/restrictions/unrestrict/"); loadRestrictedUsers(); }

async function userPrivacyAction(endpoint) {
    const username = document.getElementById("privacyUsername").value;
    if (!username) { alert("Enter username."); return; }

    try {
        const data = await apiRequest(endpoint, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ username: username }),
        });
        alert(data.message || "Action completed.");
        loadBlockedUsers();
        loadRestrictedUsers();
        loadConnections();
        loadChatRooms();
        loadSuggestedUsers();
    } catch (error) {
        alert(formatApiError(error));
    }
}

async function loadBlockedUsers() {
    const container = document.getElementById("blockedUsersList");
    if (!container) return;

    try {
        const data  = await apiRequest("/blocks/", { method: "GET", headers: getAuthHeaders() });
        const blocks = data.results || data;

        if (!blocks.length) {
            container.innerHTML = `<p class="page-subtext text-sm text-center py-4">No blocked users.</p>`;
            return;
        }

        container.innerHTML = blocks.map((block) => `
            <div class="privacy-item">
                <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                     style="background:rgba(239,68,68,0.12);">
                    <i data-lucide="user-x" style="width:14px;height:14px;color:#f87171;"></i>
                </div>
                <span class="text-sm page-heading">${block.blocked.username}</span>
            </div>
        `).join("");

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
    } catch (error) {
        container.innerHTML = `<p class="text-rose-500 text-sm">Failed to load blocked users.</p>`;
    }
}

async function loadRestrictedUsers() {
    const container = document.getElementById("restrictedUsersList");
    if (!container) return;

    try {
        const data         = await apiRequest("/restrictions/", { method: "GET", headers: getAuthHeaders() });
        const restrictions = data.results || data;

        if (!restrictions.length) {
            container.innerHTML = `<p class="page-subtext text-sm text-center py-4">No restricted users.</p>`;
            return;
        }

        container.innerHTML = restrictions.map((item) => `
            <div class="privacy-item">
                <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                     style="background:rgba(245,158,11,0.12);">
                    <i data-lucide="eye-off" style="width:14px;height:14px;color:#fbbf24;"></i>
                </div>
                <span class="text-sm page-heading">${item.restricted_user.username}</span>
            </div>
        `).join("");

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
    } catch (error) {
        container.innerHTML = `<p class="text-rose-500 text-sm">Failed to load restricted users.</p>`;
    }
}

// ─── Notification WebSocket ───────────────────────────────────────────────────
let notificationSocket = null;

function connectNotificationSocket() {
    const token = getAccessToken();
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    notificationSocket = new WebSocket(`${protocol}://${window.location.host}/ws/notifications/?token=${token}`);

    notificationSocket.onmessage = function (event) {
        const data = JSON.parse(event.data);

        if (data.type === "notification.new") {
            loadNotifications();
        }

        if (data.type === "notifications.connected") {
            const count        = data.unread_count || 0;
            const badge        = document.getElementById("notificationBadge");
            const sidebarBadge = document.getElementById("sidebarBadge");

            if (badge) {
                badge.innerText = count;
                badge.classList.toggle("hidden", count === 0);
            }
            if (sidebarBadge) {
                sidebarBadge.innerText = count;
                sidebarBadge.classList.toggle("hidden", count === 0);
            }
        }
    };

    notificationSocket.onclose = function () {
        setTimeout(connectNotificationSocket, 3000);
    };
}