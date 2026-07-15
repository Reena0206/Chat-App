let activeRoomId = null;
let chatSocket   = null;

const _ACTIVE_CHAT_KEY = 'chatapp-active-room';

function getSavedActiveChat() {
    try {
        return JSON.parse(localStorage.getItem(_ACTIVE_CHAT_KEY) || 'null');
    } catch {
        return null;
    }
}

function saveActiveChat(roomId, username) {
    localStorage.setItem(_ACTIVE_CHAT_KEY, JSON.stringify({
        roomId: roomId,
        username: username,
    }));
}

function clearSavedActiveChat() {
    localStorage.removeItem(_ACTIVE_CHAT_KEY);
}


// â”€â”€â”€ Local Read-State (survives page refresh) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Solves the "badge reappears on refresh" bug that occurs when the backend
// does not create MessageReadReceipt rows (e.g. read_receipts_enabled=false).
// We persist { roomId: ISO-timestamp } in localStorage and suppress the badge
// whenever the local read-time is newer than the last message timestamp.
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const _READ_STATE_KEY = 'chatapp-local-reads';

function _getReadState() {
    try { return JSON.parse(localStorage.getItem(_READ_STATE_KEY) || '{}'); }
    catch { return {}; }
}

function setLocalReadAt(roomId) {
    if (!roomId) return;
    const state = _getReadState();
    state[String(roomId)] = new Date().toISOString();
    localStorage.setItem(_READ_STATE_KEY, JSON.stringify(state));
}

function getLocalReadAt(roomId) {
    return _getReadState()[String(roomId)] || null;
}

// Returns true if the user has locally marked this room as read
// after the time of the last message (or if there is no last message).
function isLocallyRead(room) {
    const localReadAt = getLocalReadAt(room.id);
    if (!localReadAt) return false;

    const lastMsgAt = room.last_message && room.last_message.created_at;
    if (!lastMsgAt)   return true;   // no messages â†’ nothing to read

    return new Date(localReadAt) >= new Date(lastMsgAt);
}

document.addEventListener("DOMContentLoaded", () => {
    const sendMessageForm  = document.getElementById("sendMessageForm");
    const mediaMessageForm = document.getElementById("mediaMessageForm");
    const messageText      = document.getElementById("messageText");

    if (sendMessageForm) {
        sendMessageForm.addEventListener("submit", sendChatMessage);
    }

    if (mediaMessageForm) {
        mediaMessageForm.addEventListener("submit", sendMediaMessage);
    }

    if (messageText) {
        messageText.addEventListener("input", sendTypingStart);
    }
});

// â”€â”€â”€ Open / start chat â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function startOneToOneChat(event) {
    event.preventDefault();

    const username = document.getElementById("chatUsername").value;

    if (!username) {
        alert("Enter username.");
        return;
    }

    await openChatWithUsername(username);
}

async function openChatWithUsername(username) {
    try {
        const data = await apiRequest("/chat-rooms/one-to-one/", {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ username: username }),
        });

        openChatRoom(data.room.id, username);
        loadChatRooms();

        // Navigate to chat section if not already there
        showSection("chatSection", document.getElementById("nav-chat"));
    } catch (error) {
        alert(formatApiError(error));
    }
}

// --- Load chat rooms list -----------------------------------------------------
function updateChatBadge(count) {
    const badge = document.getElementById("chatBadge");

    if (typeof setChatUnreadTotal === "function") {
        setChatUnreadTotal(count);
    }

    if (!badge) {
        return;
    }

    badge.innerText = count > 99 ? "99+" : String(count);
    badge.classList.toggle("hidden", count === 0);
}

async function loadChatRooms() {
    const container = document.getElementById("chatRoomsList");

    if (!container) {
        return;
    }

    try {
        const data = await apiRequest("/chat-rooms/", {
            method: "GET",
            headers: getAuthHeaders(),
        });

        const rooms = data.results || data;

        if (!rooms.length) {
            container.innerHTML = `
                <div class="flex flex-col items-center justify-center py-10 px-4 text-center">
                    <i data-lucide="message-square" style="width:32px;height:32px;color:#374151;margin-bottom:0.75rem;"></i>
                    <p class="text-gray-600 text-sm">No chats yet.</p>
                    <p class="text-gray-600 text-xs mt-1">Start a chat using the field above.</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
            updateChatBadge(0);
            return;
        }

        let totalUnread = 0;

        container.innerHTML = rooms.map((room) => {
            const currentUser = getCurrentUser();
            const other       = room.participants.find((user) => user.id !== currentUser.id) || room.participants[0];
            const lastText    = room.last_message
                ? (room.last_message.text || room.last_message.message_type || "")
                : "No messages";
            const isActive    = room.id === activeRoomId;
            const initials    = (other.username || "?")[0].toUpperCase();

            // -- BADGE SUPPRESSION (instant + refresh-persistent) -----------------
            // Priority:
            //   1. Active room right now ? always 0.
            //   2. Room was locally marked read after the last message
            //      (survives page refresh even when backend uses last_seen_at
            //      instead of MessageReadReceipt rows) ? 0.
            //   3. Otherwise use the server's unread_count.
            const displayCount = (isActive || isLocallyRead(room)) ? 0 : room.unread_count;
            totalUnread += displayCount;

            return `
                <button class="chat-room-item ${isActive ? "active" : ""}"
                        onclick="openChatRoom(${room.id}, '${other.username}')">
                    <div class="w-10 h-10 rounded-full bg-gradient-to-br from-brand-400 to-purple-500 flex items-center justify-center text-white font-semibold text-sm shrink-0">
                        ${initials}
                    </div>
                    <div class="flex-1 min-w-0 text-left">
                        <div class="flex items-center justify-between">
                            <span class="text-sm font-semibold truncate" style="color:var(--clr-text);">${other.username}</span>
                            ${displayCount > 0
                                ? `<span class="min-w-[20px] h-5 flex items-center justify-center bg-brand-600 text-white text-[10px] font-bold rounded-full px-1.5 shrink-0">${displayCount}</span>`
                                : ""}
                        </div>
                        <p class="text-xs truncate mt-0.5" style="color:var(--clr-muted);">${lastText}</p>
                    </div>
                </button>
            `;
        }).join("");

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
        updateChatBadge(totalUnread);

        if (!activeRoomId) {
            const savedChat = getSavedActiveChat();
            if (savedChat && savedChat.roomId) {
                const savedRoom = rooms.find((room) => Number(room.id) === Number(savedChat.roomId));
                if (savedRoom) {
                    const currentUser = getCurrentUser();
                    const other = savedRoom.participants.find((user) => user.id !== currentUser.id) || savedRoom.participants[0];
                    if (other) {
                        await openChatRoom(savedRoom.id, savedChat.username || other.username || 'Chat');
                    }
                } else {
                    clearSavedActiveChat();
                }
            }
        }
    } catch (error) {
        container.innerHTML = `<div class="p-4 text-rose-400 text-sm">Failed to load chats.</div>`;
        updateChatBadge(0);
    }
}

// --- Open a chat room ---------------------------------------------------------â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function openChatRoom(roomId, username) {
    activeRoomId = roomId;
    saveActiveChat(roomId, username);

    document.getElementById("activeChatTitle").innerText = username;
    document.getElementById("typingStatus").innerText    = "";

    // Step 1 â€” stamp local read time IMMEDIATELY so the badge vanishes
    //           both now AND after any future page refresh.
    setLocalReadAt(roomId);

    // Step 2 â€” re-render room list with badge suppressed
    loadChatRooms();

    // Step 3 â€” load message history
    await loadMessages(roomId);

    // Step 4 â€” connect WebSocket
    connectChatSocket(roomId);

    // Step 5 â€” persist the read receipt on the server in the background.
    //           Even if this fails, the localStorage stamp keeps the badge
    //           hidden on refresh.
    try {
        await markMessagesRead();
    } catch (e) {
        // badge already hidden via localStorage â€” safe to ignore
    }
}

// â”€â”€â”€ Load messages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function loadMessages(roomId) {
    const container = document.getElementById("chatMessages");

    try {
        const data = await apiRequest(`/chat-rooms/${roomId}/messages/`, {
            method: "GET",
            headers: getAuthHeaders(),
        });

        const messages = data.results || data;

        container.innerHTML = messages.length
            ? messages.map(renderMessage).join("")
            : `<div class="flex items-center justify-center h-full">
                   <p class="text-gray-600 text-sm">No messages yet. Say hello! ðŸ‘‹</p>
               </div>`;

        container.scrollTop = container.scrollHeight;

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
    } catch (error) {
        container.innerHTML = `<p class="text-rose-400 text-sm p-4">Failed to load messages.</p>`;
    }
}

// â”€â”€â”€ Render a single message bubble â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderMessage(message) {
    const currentUser = getCurrentUser();
    const isOwn       = message.sender && message.sender.id === currentUser.id;

    let mediaHtml = "";

    if (message.media_files && message.media_files.length) {
        mediaHtml = message.media_files.map((media) => {
            if (media.media_type === "image") {
                return `<img src="${media.file_url}" class="media-preview">`;
            }

            if (media.media_type === "video") {
                return `<video controls class="media-preview"><source src="${media.file_url}"></video>`;
            }

            if (media.media_type === "voice") {
                return `<audio controls style="width:100%;max-width:240px;margin-top:8px;"><source src="${media.file_url}"></audio>`;
            }

            return `<a href="${media.file_url}" target="_blank" style="color:#818cf8;font-size:0.75rem;">Open file</a>`;
        }).join("");
    }

    return `
        <div style="display:flex;flex-direction:column;align-items:${isOwn ? "flex-end" : "flex-start"};">
            <div class="message-bubble ${isOwn ? "message-own" : "message-other"}">
                ${message.text ? `<div>${message.text}</div>` : ""}
                ${mediaHtml}
                <div class="message-meta" style="text-align:${isOwn ? "right" : "left"};">
                    ${message.sender ? message.sender.username : ""}
                </div>
            </div>
        </div>
    `;
}

// â”€â”€â”€ WebSocket connection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function connectChatSocket(roomId) {
    if (chatSocket) {
        chatSocket.close();
    }

    const token    = getAccessToken();
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";

    chatSocket = new WebSocket(`${protocol}://${window.location.host}/ws/chat/rooms/${roomId}/?token=${token}`);

    chatSocket.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.type === "message.new") {
            appendMessage(data.message);
            loadChatRooms();
        }

        if (data.type === "typing") {
            const status = document.getElementById("typingStatus");
            if (status) {
                status.innerText = data.is_typing ? `${data.user.username} is typingâ€¦` : "";
            }
        }

        if (data.type === "messages.read") {
            // âœ… FIX 2: Refresh room list when a read receipt is received
            // so the unread badge on the other person's side clears instantly.
            loadChatRooms();
        }

        if (data.type === "user_online" || data.type === "user_offline") {
            console.log("Presence:", data);
        }

        if (data.type === "error") {
            alert(data.detail);
        }
    };

    chatSocket.onclose = function() {
        console.log("Chat socket closed.");
    };
}

function appendMessage(message) {
    const container = document.getElementById("chatMessages");

    container.insertAdjacentHTML("beforeend", renderMessage(message));
    container.scrollTop = container.scrollHeight;

    // If the arriving message is from the OTHER user and this is the active
    // room, the user sees it instantly â†’ stamp local read time so the badge
    // stays 0 (no flash) when loadChatRooms() re-renders the list.
    const currentUser = getCurrentUser();
    const isIncoming  = message.sender && message.sender.id !== currentUser.id;
    if (isIncoming && activeRoomId) {
        setLocalReadAt(activeRoomId);
    }
}

// â”€â”€â”€ Send text message â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function sendChatMessage(event) {
    event.preventDefault();

    if (!activeRoomId || !chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        alert("Open a chat first.");
        return;
    }

    const input = document.getElementById("messageText");
    const text  = input.value.trim();

    if (!text) {
        return;
    }

    chatSocket.send(JSON.stringify({
        type: "message.send",
        text: text,
    }));

    input.value = "";
}

// â”€â”€â”€ Typing indicator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let typingTimer = null;

function sendTypingStart() {
    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    chatSocket.send(JSON.stringify({ type: "typing.start" }));

    clearTimeout(typingTimer);

    typingTimer = setTimeout(() => {
        chatSocket.send(JSON.stringify({ type: "typing.stop" }));
    }, 1000);
}

// â”€â”€â”€ Send media message â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function sendMediaMessage(event) {
    event.preventDefault();

    if (!activeRoomId) {
        alert("Open a chat first.");
        return;
    }

    const mediaType = document.getElementById("mediaType").value;
    const mediaFile = document.getElementById("mediaFile").files[0];
    const duration  = document.getElementById("mediaDuration").value;

    if (!mediaFile) {
        alert("Select a file.");
        return;
    }

    const formData = new FormData();

    formData.append("media_type", mediaType);
    formData.append("file", mediaFile);

    const caption = document.getElementById("messageText").value.trim();

    if (caption) {
        formData.append("text", caption);
    }

    if (mediaType === "voice" && duration) {
        formData.append("duration_seconds", duration);
    }

    try {
        await apiRequest(`/chat-rooms/${activeRoomId}/messages/media/`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${getAccessToken()}`,
            },
            body: formData,
        });

        document.getElementById("mediaFile").value          = "";
        document.getElementById("mediaDuration").value      = "";
        document.getElementById("messageText").value        = "";
        document.getElementById("mediaFileName").textContent = "Choose fileâ€¦";

        loadMessages(activeRoomId);
        loadChatRooms();
    } catch (error) {
        alert("Media upload failed.");
    }
}

// â”€â”€â”€ Mark messages read â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function markMessagesRead() {
    if (!activeRoomId) {
        return;
    }

    try {
        await apiRequest(`/chat-rooms/${activeRoomId}/messages/mark-read/`, {
            method: "POST",
            headers: getAuthHeaders(),
        });

        // Stamp localStorage again now that the server confirmed the read,
        // ensuring the timestamp is at least as fresh as the server response.
        setLocalReadAt(activeRoomId);

        if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.send(JSON.stringify({ type: "message.read" }));
        }

        loadChatRooms();
    } catch (error) {
        alert(formatApiError(error));
    }
}


