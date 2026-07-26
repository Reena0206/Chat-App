let activeRoomId = null;
let activeChatUsername = null;
let activeChatBlockedUsername = null;
let chatSocket   = null;

const _ACTIVE_CHAT_KEY = 'pingnest-active-room';

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
function normalizeChatUsername(value) {
    return String(value || "").trim().toLowerCase();
}

function setChatComposerEnabled(enabled) {
    ["messageText", "mediaFile"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.disabled = !enabled;
    });

    document.querySelectorAll("#sendMessageForm button").forEach((button) => {
        button.disabled = !enabled;
        button.classList.toggle("opacity-50", !enabled);
        button.classList.toggle("cursor-not-allowed", !enabled);
    });
}

function renderBlockedChatNotice(username, blockStatus = "you_blocked") {
    const safeUsername = escapeHtml(username || "this user");
    const theyBlockedMe = blockStatus === "blocked_by";

    return `
        <div class="chat-privacy-notice">
            <div class="chat-privacy-notice-icon">
                <i data-lucide="ban" class="w-5 h-5"></i>
            </div>
            <div class="chat-privacy-notice-body">
                <h3>${theyBlockedMe ? `You are blocked by ${safeUsername}` : `${safeUsername} is blocked`}</h3>
                <p>${theyBlockedMe ? "You cannot send messages in this chat unless they unblock you." : "You cannot send or receive messages in this chat while this user is blocked."}</p>
                ${theyBlockedMe ? "" : `
                    <button type="button" class="chat-privacy-unblock-btn" onclick="unblockActiveChatUser(this)">
                        Unblock User
                    </button>
                `}
            </div>
        </div>
    `;
}

function showBlockedChatStateForUsername(username, blockStatus = "you_blocked") {
    const normalized = normalizeChatUsername(username);
    if (!normalized || normalizeChatUsername(activeChatUsername) !== normalized) {
        return;
    }

    activeChatBlockedUsername = activeChatUsername || username;
    activeChatBlockStatus = blockStatus || "you_blocked";
    setChatComposerEnabled(false);

    if (chatSocket) {
        chatSocket.close();
        chatSocket = null;
    }

    const messages = document.getElementById("chatMessages");
    if (messages) {
        messages.innerHTML = renderBlockedChatNotice(activeChatBlockedUsername, activeChatBlockStatus);
        if (window.lucide) lucide.createIcons({ nodes: messages.querySelectorAll("[data-lucide]") });
    }
}

function clearBlockedChatStateForUsername(username) {
    const normalized = normalizeChatUsername(username);
    if (!normalized || normalizeChatUsername(activeChatBlockedUsername) !== normalized) {
        return;
    }

    activeChatBlockedUsername = null;
    activeChatBlockStatus = "";
    setChatComposerEnabled(true);
    if (activeRoomId) {
        loadMessages(activeRoomId);
        connectChatSocket(activeRoomId);
    }
}

async function unblockActiveChatUser(button = null) {
    if (!activeChatBlockedUsername || typeof unblockUserFor !== "function") {
        return;
    }

    const username = activeChatBlockedUsername;
    const unblocked = await unblockUserFor(username, button);
    if (unblocked) {
        clearBlockedChatStateForUsername(username);
    }
}


// â”€â”€â”€ Local Read-State (survives page refresh) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Solves the "badge reappears on refresh" bug that occurs when the backend
// does not create MessageReadReceipt rows (e.g. read_receipts_enabled=false).
// We persist { roomId: ISO-timestamp } in localStorage and suppress the badge
// whenever the local read-time is newer than the last message timestamp.
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const _READ_STATE_KEY = 'pingnest-local-reads';

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

    const num = Number(count) || 0;
    const text = num > 99 ? "99+" : String(num);

    badge.innerText = text;
    if (num <= 0) {
        badge.classList.add("hidden");
        badge.style.display = "none";
    } else {
        badge.classList.remove("hidden");
        badge.style.display = "inline-flex";
    }
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
                    <p class="page-subtext text-sm">No chats yet.</p>
                    <p class="page-subtext text-xs mt-1">Start a chat using the field above.</p>
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
            const isBlocked   = Boolean(room.is_blocked);
            const blockStatus = room.block_status || (isBlocked ? "you_blocked" : "");
            const initials    = (other.username || "?")[0].toUpperCase();

            // -- BADGE SUPPRESSION (instant + refresh-persistent) -----------------
            // Priority:
            //   1. Active room right now ? always 0.
            //   2. Room was locally marked read after the last message
            //      (survives page refresh even when backend uses last_seen_at
            //      instead of MessageReadReceipt rows) ? 0.
            //   3. Otherwise use the server's unread_count.
            const displayCount = (isBlocked || isActive || isLocallyRead(room)) ? 0 : room.unread_count;
            totalUnread += displayCount;

            return `
                <button class="chat-room-item ${isActive ? "active" : ""} ${isBlocked ? "chat-room-blocked" : ""}"
                        onclick="openChatRoom(${room.id}, '${other.username}', ${isBlocked}, '${blockStatus}')">
                    <div class="w-10 h-10 rounded-full bg-gradient-to-br from-brand-400 to-purple-500 flex items-center justify-center text-white font-semibold text-sm shrink-0">
                        ${initials}
                    </div>
                    <div class="flex-1 min-w-0 text-left">
                        <div class="flex items-center justify-between">
                            <span class="text-sm font-semibold truncate" style="color:var(--clr-text);">${other.username}</span>
                            ${isBlocked
                                ? `<span class="chat-room-status-pill chat-room-status-blocked">Blocked</span>`
                                : displayCount > 0
                                    ? `<span class="min-w-[20px] h-5 flex items-center justify-center bg-brand-600 text-white text-[10px] font-bold rounded-full px-1.5 shrink-0">${displayCount}</span>`
                                    : ""}
                        </div>
                        <p class="text-xs truncate mt-0.5" style="color:var(--clr-muted);">${isBlocked ? (blockStatus === "blocked_by" ? `You are blocked by ${other.username}` : "You blocked this user") : lastText}</p>
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
                        await openChatRoom(savedRoom.id, savedChat.username || other.username || 'Chat', Boolean(savedRoom.is_blocked), savedRoom.block_status || "");
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
async function openChatRoom(roomId, username, isBlocked = false, blockStatus = "") {
    activeRoomId = roomId;
    activeChatUsername = username;
    activeChatBlockedUsername = null;
    activeChatBlockStatus = "";
    setChatComposerEnabled(true);
    saveActiveChat(roomId, username);

    document.getElementById("activeChatTitle").innerText = username;
    document.getElementById("typingStatus").innerText    = "";

    if (isBlocked || (typeof getBlockedPrivacyEntry === "function" && getBlockedPrivacyEntry(username))) {
        showBlockedChatStateForUsername(username, blockStatus || "you_blocked");
        return;
    }

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
                   <p class="page-subtext text-sm">No messages yet. Say hello! ðŸ‘‹</p>
               </div>`;

        container.scrollTop = container.scrollHeight;

        if (window.lucide) lucide.createIcons({ nodes: container.querySelectorAll('[data-lucide]') });
    } catch (error) {
        container.innerHTML = `<p class="text-rose-400 text-sm p-4">Failed to load messages.</p>`;
    }
}

// â”€â”€â”€ Render a single message bubble â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function formatAudioTime(seconds) {
    if (!seconds || isNaN(seconds)) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

const PLAY_SVG = `<svg class="w-4 h-4 text-white fill-current" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>`;
const PAUSE_SVG = `<svg class="w-4 h-4 text-white fill-current" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;
const CHECK_SVG = `<svg class="w-3 h-3 text-white/80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 7 17l-5-5"/><path d="m22 10-7.5 7.5L13 16"/></svg>`;

window.activeAudio = null;
window.activePlayBtn = null;

function toggleAudioPlay(audioId, btnId, progressId, timeId) {
    let audio = document.getElementById(audioId);
    const btn = document.getElementById(btnId);
    const progress = document.getElementById(progressId);
    const timeDisplay = document.getElementById(timeId);

    if (!audio) return;

    if (window.activeAudio && window.activeAudio !== audio) {
        window.activeAudio.pause();
        if (window.activePlayBtn) window.activePlayBtn.innerHTML = PLAY_SVG;
    }

    if (audio.paused) {
        if (audio.readyState === 0) {
            audio.load();
        }

        const promise = audio.play();
        if (promise !== undefined) {
            promise.then(() => {
                window.activeAudio = audio;
                window.activePlayBtn = btn;
                btn.innerHTML = PAUSE_SVG;
            }).catch(err => {
                console.log("Standard audio play fallback triggered:", err);
                const audioUrl = audio.src || audio.getAttribute("src");
                if (audioUrl) {
                    const fallbackAudio = new Audio(audioUrl);
                    fallbackAudio.play().then(() => {
                        window.activeAudio = fallbackAudio;
                        window.activePlayBtn = btn;
                        btn.innerHTML = PAUSE_SVG;

                        fallbackAudio.ontimeupdate = () => {
                            if (fallbackAudio.duration) {
                                const pct = (fallbackAudio.currentTime / fallbackAudio.duration) * 100;
                                if (progress) progress.style.width = `${pct}%`;
                                if (timeDisplay) timeDisplay.textContent = formatAudioTime(fallbackAudio.currentTime);
                            }
                        };

                        fallbackAudio.onended = () => {
                            if (btn) btn.innerHTML = PLAY_SVG;
                            if (progress) progress.style.width = '0%';
                        };
                    }).catch(e => showToast("Could not play audio file.", "warning"));
                }
            });
        }
    } else {
        audio.pause();
        btn.innerHTML = PLAY_SVG;
    }

    audio.ontimeupdate = () => {
        if (audio.duration && !isNaN(audio.duration)) {
            const pct = (audio.currentTime / audio.duration) * 100;
            if (progress) progress.style.width = `${pct}%`;
            if (timeDisplay) timeDisplay.textContent = formatAudioTime(audio.currentTime);
        }
    };

    audio.onended = () => {
        if (btn) btn.innerHTML = PLAY_SVG;
        if (progress) progress.style.width = '0%';
        if (timeDisplay) timeDisplay.textContent = formatAudioTime(audio.duration || 0);
    };
}

function scrubAudio(event, audioId, progressId) {
    const audio = document.getElementById(audioId);
    const progress = document.getElementById(progressId);
    if (!audio || !audio.duration) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const pos = (event.clientX - rect.left) / rect.width;
    audio.currentTime = pos * audio.duration;
    if (progress) progress.style.width = `${pos * 100}%`;
}

function renderMessage(message) {
    const currentUser = getCurrentUser();
    const isOwn       = message.sender && message.sender.id === currentUser.id;
    const timeStr     = message.created_at ? new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    const hasText     = message.text && message.text.trim().length > 0;
    const mediaFiles  = message.media_files || [];

    // If message is text-only:
    if (!mediaFiles.length) {
        const bubbleStyle = isOwn
            ? "chat-bubble-outgoing px-4 py-2.5 max-w-md"
            : "chat-bubble-incoming px-4 py-2.5 max-w-md";

        return `
            <div class="flex flex-col ${isOwn ? "items-end" : "items-start"} my-1.5 space-y-1">
                ${!isOwn && message.sender ? `<span class="chat-sender-label">${message.sender.username}</span>` : ""}
                <div class="${bubbleStyle}">
                    <p class="text-sm whitespace-pre-wrap break-words leading-relaxed">${escapeHtml(message.text)}</p>
                    <div class="flex items-center justify-end gap-1 mt-1 text-[10px] opacity-75">
                        <span>${timeStr}</span>
                        ${isOwn ? CHECK_SVG : ""}
                    </div>
                </div>
            </div>
        `;
    }

    // Process Media Items:
    const mediaItemsHtml = mediaFiles.map((media, idx) => {
        const uniqueId = `media_${message.id}_${idx}`;

        if (media.media_type === "image") {
            return `
                <div class="chat-media-frame relative rounded-2xl overflow-hidden group max-w-sm shadow-lg">
                    <a href="${media.file_url}" target="_blank" class="block">
                        <img src="${media.file_url}" alt="Attachment" class="w-full max-h-80 object-cover transition-transform duration-300 group-hover:scale-105" loading="lazy">
                    </a>
                    ${!hasText ? `
                        <div class="absolute bottom-0 inset-x-0 p-2 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center justify-end gap-1 text-[10px] text-white/90">
                            <span>${timeStr}</span>
                            ${isOwn ? CHECK_SVG : ""}
                        </div>
                    ` : ""}
                </div>
            `;
        }

        if (media.media_type === "video") {
            const videoName = media.original_name || "Video attachment";

            return `
                <div class="chat-video-card max-w-sm shadow-lg">
                    <div class="chat-video-header">
                        <div class="chat-video-icon">
                            <i data-lucide="film" class="w-3.5 h-3.5"></i>
                        </div>
                        <div class="min-w-0">
                            <p class="chat-video-title" title="${escapeHtml(videoName)}">${escapeHtml(videoName)}</p>
                            <p class="chat-video-subtitle">Video</p>
                        </div>
                    </div>
                    <div class="chat-video-shell">
                        <video controls preload="metadata" class="chat-video-player">
                            <source src="${media.file_url}">
                        </video>
                    </div>
                    ${!hasText ? `
                        <div class="chat-media-meta flex items-center justify-end gap-1 px-3 py-1.5 text-[10px]">
                            <span>${timeStr}</span>
                            ${isOwn ? CHECK_SVG : ""}
                        </div>
                    ` : ""}
                </div>
            `;
        }

        if (media.media_type === "voice") {
            const audioId = `audio_${uniqueId}`;
            const btnId = `playbtn_${uniqueId}`;
            const progressId = `progress_${uniqueId}`;
            const timeId = `time_${uniqueId}`;
            const durationSecs = media.duration_seconds || 0;
            const cardBg = isOwn
                ? "chat-bubble-outgoing"
                : "chat-bubble-incoming";

            return `
                <div class="p-3 my-1 ${cardBg} w-64 shadow-md">
                    <audio id="${audioId}" src="${media.file_url}" preload="auto" class="hidden"></audio>
                    <div class="flex items-center gap-3">
                        <button type="button" id="${btnId}" onclick="toggleAudioPlay('${audioId}', '${btnId}', '${progressId}', '${timeId}')"
                                class="chat-audio-play w-9 h-9 rounded-full active:scale-95 transition-all flex items-center justify-center shrink-0 shadow">
                            ${PLAY_SVG}
                        </button>
                        <div class="flex-1 min-w-0">
                            <div class="chat-audio-track w-full h-1.5 rounded-full overflow-hidden cursor-pointer" onclick="scrubAudio(event, '${audioId}', '${progressId}')">
                                <div id="${progressId}" class="chat-audio-progress h-full transition-all duration-75" style="width: 0%;"></div>
                            </div>
                            <div class="flex items-center justify-between text-[10px] opacity-80 mt-1.5 font-medium">
                                <span id="${timeId}">${formatAudioTime(durationSecs)}</span>
                                <div class="flex items-center gap-1">
                                    <span>${timeStr}</span>
                                    ${isOwn ? CHECK_SVG : ""}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        // Document / File / Other
        const fileName = media.original_name || 'Attached file';
        const sizeStr  = formatBytes(media.file_size);
        const ext      = (fileName.split('.').pop() || 'FILE').toUpperCase();
        const cardBg   = isOwn
            ? "chat-bubble-outgoing"
            : "chat-bubble-incoming";

        return `
            <div class="p-3 my-1 ${cardBg} max-w-xs shadow-md">
                <div class="flex items-center gap-3">
                    <div class="chat-file-icon w-10 h-10 rounded-xl font-bold text-[10px] flex items-center justify-center shrink-0 tracking-wider">
                        ${ext.substring(0, 4)}
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs font-semibold truncate" title="${fileName}">${fileName}</p>
                        <span class="text-[10px] opacity-80 block mt-0.5">${sizeStr}</span>
                    </div>
                    <a href="${media.file_url}" download target="_blank" title="Download File"
                       class="chat-file-download w-8 h-8 rounded-lg flex items-center justify-center transition-colors shrink-0">
                        <svg class="w-4 h-4 stroke-2 fill-none" viewBox="0 0 24 24" stroke="currentColor"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    </a>
                </div>
                ${!hasText ? `
                    <div class="flex items-center justify-end gap-1 mt-1.5 text-[10px] opacity-75">
                        <span>${timeStr}</span>
                        ${isOwn ? CHECK_SVG : ""}
                    </div>
                ` : ""}
            </div>
        `;
    }).join("");

    if (!hasText) {
        return `
            <div class="flex flex-col ${isOwn ? "items-end" : "items-start"} my-1.5 space-y-1">
                ${!isOwn && message.sender ? `<span class="chat-sender-label">${message.sender.username}</span>` : ""}
                ${mediaItemsHtml}
            </div>
        `;
    }

    const textBubbleStyle = isOwn
        ? "chat-bubble-outgoing px-4 py-2.5 max-w-md"
        : "chat-bubble-incoming px-4 py-2.5 max-w-md";

    return `
        <div class="flex flex-col ${isOwn ? "items-end" : "items-start"} my-1.5 space-y-1">
            ${!isOwn && message.sender ? `<span class="chat-sender-label">${message.sender.username}</span>` : ""}
            ${mediaItemsHtml}
            <div class="${textBubbleStyle}">
                <p class="text-sm whitespace-pre-wrap break-words leading-relaxed">${escapeHtml(message.text)}</p>
                <div class="flex items-center justify-end gap-1 mt-1 text-[10px] opacity-75">
                    <span>${timeStr}</span>
                    ${isOwn ? `<i data-lucide="check-check" class="w-3 h-3 text-brand-200"></i>` : ""}
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
                status.innerText = data.is_typing ? `${data.user.username} is typing...` : "";
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

    if (activeChatBlockedUsername) {
        showToast("Unblock this user before sending messages.", "warning");
        return;
    }

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

// ─── Live Voice Recording (Web MediaRecorder API) ────────────────────────────
let mediaRecorder = null;
let audioChunks = [];
let recordingStartTime = 0;
let recordingInterval = null;

async function toggleVoiceRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        stopAndSendVoiceRecording();
    } else {
        startVoiceRecording();
    }
}

async function startVoiceRecording() {
    if (activeChatBlockedUsername) {
        showToast("Unblock this user before sending messages.", "warning");
        return;
    }

    if (!activeRoomId) {
        showToast("Please select a chat room first.", "warning");
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.start();
        recordingStartTime = Date.now();

        const bar = document.getElementById("voiceRecordingBar");
        const timer = document.getElementById("recordingTimer");
        const micBtn = document.getElementById("micRecordBtn");

        if (bar) {
            bar.classList.remove("hidden");
            bar.style.display = "flex";
        }
        if (micBtn) {
            micBtn.classList.add("bg-rose-600", "text-white", "animate-pulse");
        }

        recordingInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
            const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const secs = String(elapsed % 60).padStart(2, '0');
            if (timer) timer.textContent = `Recording ${mins}:${secs}`;
        }, 1000);

    } catch (err) {
        showToast("Microphone access denied or not supported by browser.", "danger");
    }
}

function cancelVoiceRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.onstop = null;
        mediaRecorder.stop();
        if (mediaRecorder.stream) {
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
    }
    resetRecordingUI();
}

function stopAndSendVoiceRecording() {
    if (!mediaRecorder || mediaRecorder.state === "inactive") return;

    const durationSecs = Math.max(1, Math.round((Date.now() - recordingStartTime) / 1000));

    mediaRecorder.onstop = async () => {
        if (mediaRecorder.stream) {
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }

        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        const audioFile = new File([audioBlob], `voice_${Date.now()}.webm`, { type: "audio/webm" });

        resetRecordingUI();

        const formData = new FormData();
        formData.append("media_type", "voice");
        formData.append("file", audioFile);
        formData.append("duration_seconds", durationSecs);

        try {
            await apiRequest(`/chat-rooms/${activeRoomId}/messages/media/`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${getAccessToken()}` },
                body: formData,
            });
            showToast("Voice note sent!", "success");
            loadMessages(activeRoomId);
            loadChatRooms();
        } catch (err) {
            showToast(formatApiError(err), "danger");
        }
    };

    mediaRecorder.stop();
}

function resetRecordingUI() {
    if (recordingInterval) {
        clearInterval(recordingInterval);
        recordingInterval = null;
    }
    const bar = document.getElementById("voiceRecordingBar");
    const micBtn = document.getElementById("micRecordBtn");
    if (bar) {
        bar.classList.add("hidden");
        bar.style.display = "none";
    }
    if (micBtn) {
        micBtn.classList.remove("bg-rose-600", "text-white", "animate-pulse");
    }
}

// ─── Unified Attachment & Message Sender ─────────────────────────────────────
let selectedMediaFile = null;
let selectedMediaType = "document";

function onFileSelected(input) {
    const file = input.files[0];
    if (!file) {
        clearSelectedFile();
        return;
    }
    selectedMediaFile = file;
    const ext = file.name.split('.').pop().toLowerCase();
    const videoExts = ['mp4', 'webm', 'mov', 'm4v', 'mkv', 'avi'];
    const voiceExts = ['mp3', 'wav', 'm4a', 'ogg', 'aac'];
    const imageExts = ['jpg', 'jpeg', 'png', 'webp', 'gif'];

    let icon = "📄";
    if (videoExts.includes(ext)) {
        selectedMediaType = "video";
        icon = "🎥";
    } else if (voiceExts.includes(ext) || file.type.startsWith("audio/")) {
        selectedMediaType = "voice";
        icon = "🎙️";
    } else if (imageExts.includes(ext) || file.type.startsWith("image/")) {
        selectedMediaType = "image";
        icon = "🖼️";
    } else {
        selectedMediaType = "document";
        icon = "📄";
    }

    const chip = document.getElementById("filePreviewChip");
    const chipIcon = document.getElementById("chipFileIcon");
    const chipName = document.getElementById("chipFileName");
    const chipSize = document.getElementById("chipFileSize");

    if (chip) {
        chip.classList.remove("hidden");
        chip.style.display = "flex";
    }
    if (chipIcon) chipIcon.textContent = icon;
    if (chipName) chipName.textContent = file.name;
    if (chipSize) chipSize.textContent = `(${formatBytes(file.size)})`;
}

function clearSelectedFile() {
    selectedMediaFile = null;
    selectedMediaType = "document";
    const fileInput = document.getElementById("mediaFile");
    if (fileInput) fileInput.value = "";
    const chip = document.getElementById("filePreviewChip");
    if (chip) {
        chip.classList.add("hidden");
        chip.style.display = "none";
    }
}

async function handleUnifiedSend(event) {
    event.preventDefault();
    if (activeChatBlockedUsername) {
        showToast("Unblock this user before sending messages.", "warning");
        return;
    }

    if (!activeRoomId) {
        showToast("Please select a chat room first.", "warning");
        return;
    }

    const textInput = document.getElementById("messageText");
    const textVal = textInput ? textInput.value.trim() : "";

    // If a file is attached, post to media endpoint (with text caption if provided):
    if (selectedMediaFile) {
        const formData = new FormData();
        formData.append("media_type", selectedMediaType);
        formData.append("file", selectedMediaFile);
        if (textVal) {
            formData.append("text", textVal);
        }

        try {
            await apiRequest(`/chat-rooms/${activeRoomId}/messages/media/`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${getAccessToken()}` },
                body: formData,
            });

            if (textInput) textInput.value = "";
            clearSelectedFile();
            showToast("Attachment sent!", "success");
            loadMessages(activeRoomId);
            loadChatRooms();
        } catch (err) {
            showToast(formatApiError(err), "danger");
        }
        return;
    }

    // Otherwise send text message:
    if (!textVal) return;

    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({
            type: "message.send",
            text: textVal,
        }));
        if (textInput) textInput.value = "";
    } else {
        try {
            await apiRequest(`/chat-rooms/${activeRoomId}/messages/text/`, {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({ text: textVal }),
            });
            if (textInput) textInput.value = "";
            loadMessages(activeRoomId);
            loadChatRooms();
        } catch (err) {
            showToast(formatApiError(err), "danger");
        }
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


