# 📸 ChatApp — Instagram-Style Django Chat Application

A modern, responsive, and elegant Instagram-style real-time chat application built with **Django 5**, **Django REST Framework**, and **Django Channels**. The application features a fully responsive, premium Tailwind CSS frontend with seamless Light/Dark mode transitions, real-time message delivery, and robust JWT authentication.

---

## ✨ Features

### 1. Modern UI/UX (Tailwind CSS)
* **Dual Theming:** Instant transition between professional Dark Mode (default) and Light Mode. Saved in `localStorage` and configured with a head-load flash-prevention script.
* **Premium Styling:** Built with smooth gradients, cards with modern blur effects (glassmorphism), custom hover states, micro-animations, and Lucide icons.
* **Responsive Layout:** Mobile-friendly app shell with a collapsable drawer sidebar.

### 2. Real-Time Chat & Channels
* **WebSockets Integration:** Instant messaging using Django Channels and Redis/In-Memory channel layers.
* **Typing Indicators:** Real-time feedback when the chat partner is typing.
* **Media Messaging:** Upload and render images, videos, and voice recordings directly within message bubbles.
* **Smart Badge System:** Unread count indicators that automatically clear on read, with a persistent client-side caching mechanism (`chatapp-local-reads`) to sync receipts.

### 3. Connections & Suggestions
* **People You May Know:** Parallel, cached query engine to suggest connections based on public profiles, excluding already connected or pending connections.
* **Connection Requests:** Send, receive, accept, or reject connection requests in real-time.
* **Search & Filter:** Find users directly and open messaging channels instantly.

### 4. Privacy & Moderation
* **User Control:** Block or restrict users to moderate chat interactions and protect feed visibility.
* **Read Receipts Switch:** Enable/disable read receipts dynamically from the profile page.

### 5. Advanced Security & Auth
* **JWT Authentication:** SimpleJWT integration with access tokens and refresh tokens.
* **Concurrences-Safe Auto-Refresh:** Queueing middleware intercepts concurrent `401 Unauthorized` requests, executes a single refresh token query, updates tokens, and retries all pending requests seamlessly.

---

## 🛠️ Tech Stack

* **Backend:** Django 5.x, Django REST Framework (DRF), Python 3
* **Real-time:** Django Channels, WebSockets, Daphne
* **Database:** MySQL
* **Cache / WebSocket broker:** Redis (optional, falls back to InMemory layer)
* **Authentication:** djangorestframework-simplejwt (JWT)
* **Frontend:** Django Templates, Tailwind CSS CDN (v3), Vanilla JS, Lucide Icons, Custom CSS variables

---

## 📁 Project Structure

```text
instagram_chat/
├── apps/
│   ├── accounts/      # Custom User models, registration, auth APIs
│   ├── chats/         # Chat rooms, messaging, WS consumers, JWT middleware
│   ├── connections/   # Connection requests, connection services
│   ├── core/          # Shared utilities and core configs
│   ├── frontend/      # Django views serving the frontend templates
│   ├── notifications/ # Real-time activities, WS consumers, notification list
│   └── profiles/      # User bio, visibility settings, profiles list APIs
├── config/            # Django main configurations (settings, urls, routing)
├── static/
│   └── frontend/
│       ├── css/       # style.css (theme mappings & animations)
│       └── js/        # api.js (auth refresh), auth.js, chat.js, dashboard.js, theme.js
├── templates/
│   └── frontend/      # base.html, login.html, register.html, dashboard.html
├── media/             # User uploads (profile pictures, chat attachments)
├── staticfiles/       # Collected static files (for production/serving)
├── .env.example       # Schema for environment variables
├── .gitignore         # File exclusions for Git
├── manage.py          # Django entry CLI
└── requirements.txt   # Python dependency list
```

---

## 🚀 Installation & Local Setup

### Prerequisites
* Python 3.10+
* MySQL Server
* Redis Server (optional, but recommended for Channels production setup)

### Step 1: Clone and Configure Environment
1. Clone this repository to your local workspace.
2. Duplicate `.env.example` to create a `.env` file in the project root:
   ```bash
   cp .env.example .env
   ```
3. Update your database and environment settings in `.env`:
   ```ini
   SECRET_KEY='your-secure-secret-key'
   DEBUG=True
   DB_NAME='instagram_chat_db'
   DB_USER='root'
   DB_PASSWORD='your_mysql_password'
   DB_HOST='127.0.0.1'
   DB_PORT='3306'
   REDIS_URL='redis://127.0.0.1:6379/1' # Leave blank to fall back to InMemory layer
   ```

### Step 2: Virtual Environment & Dependencies
1. Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Step 3: Database setup
1. Open your MySQL client and create the database:
   ```sql
   CREATE DATABASE instagram_chat_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. Run database migrations:
   ```bash
   python manage.py migrate
   ```

### Step 4: Run Static Assets & Start Server
1. Collect static files:
   ```bash
   python manage.py collectstatic --noinput
   ```
2. Launch the ASGI development server:
   ```bash
   python manage.py runserver
   ```
3. Visit the application in your browser at `http://127.0.0.1:8000/`.

---

## 🔌 API Summary Reference

| Endpoint | Method | Authentication | Description |
|---|---|---|---|
| `/api/v1/auth/login/` | `POST` | None | Log in user and receive access & refresh tokens |
| `/api/v1/auth/register/` | `POST` | None | Register a new user |
| `/api/v1/auth/token/refresh/` | `POST` | None | Refresh an expired access token |
| `/api/v1/profiles/me/` | `GET`/`PATCH` | Bearer Token | View and update your profile bio, privacy settings |
| `/api/v1/profiles/` | `GET` | Bearer Token | View list of public profiles |
| `/api/v1/connections/` | `GET` | Bearer Token | View your active connections |
| `/api/v1/connection-requests/send/` | `POST` | Bearer Token | Send a connection request by username |
| `/api/v1/chat-rooms/` | `GET` | Bearer Token | List all available chat rooms for active user |
| `/api/v1/chat-rooms/one-to-one/` | `POST` | Bearer Token | Initialize or retrieve a chat room with a user |
| `/api/v1/chat-rooms/<id>/messages/` | `GET` | Bearer Token | Load chat message history |
| `/api/v1/chat-rooms/<id>/messages/media/` | `POST` | Bearer Token | Upload image/video/voice message |
| `/api/v1/notifications/` | `GET` | Bearer Token | View list of notifications |

---

## 🎨 Dual Theme Customization

Themes are controlled via CSS variables in [style.css](file:///c:/Users/Reena/Desktop/chat_app/instagram_chat/static/frontend/css/style.css). Key surface custom properties are:
- `--clr-bg`: Main page background color
- `--clr-surface`: Cards, navbar, and sidebar backgrounds
- `--clr-border`: Thin borders for UI structure
- `--clr-text`: Primary body text color
- `--clr-brand-bg`: Highlights and glow accents

To toggle themes, import `theme.js` in your template and call `toggleTheme()`.

---

## 🔒 JWT Auto-Refresh Queue Mechanism

When an access token expires, API requests will fail with a `401 Unauthorized` status. The wrapper `apiRequest()` in [api.js](file:///c:/Users/Reena/Desktop/chat_app/instagram_chat/static/frontend/js/api.js) resolves this with the following logic:
```text
1. API Fetch → returns 401 Unauthorized
2. Is token refresh already in progress?
   ├── YES: Create new Promise and push callback to "refreshSubscribers" queue.
   └── NO: Set isRefreshing = true, request POST /auth/token/refresh/
3. Refresh succeeds:
   ├── Store new accessToken and refreshToken in localStorage.
   ├── Set isRefreshing = false.
   ├── Resolve all queued requests in "refreshSubscribers" with new token.
   └── Retry original request.
4. Refresh fails (e.g. Refresh token also expired):
   ├── Clear all tokens and session data.
   └── Redirect user to "/login/".
```
This is fully transparent and guarantees that users are not kicked to the login screen during active session interactions.
