# PingNest

PingNest is a full-stack real-time social messaging platform built with Django, Django REST Framework, Django Channels, and a responsive Tailwind CSS frontend. It supports private one-to-one chat, connection requests, media messaging, unread badges, real-time notifications, light/dark themes, and privacy controls such as block, unblock, restrict, and unrestrict.

This project is designed as a polished portfolio application that demonstrates backend API design, WebSocket communication, authentication, frontend state management, and user-focused privacy workflows.

## Highlights

- Real-time one-to-one messaging with Django Channels and WebSockets
- JWT authentication with automatic access-token refresh handling
- Connection request workflow: send, receive, accept, reject, and manage connections
- Image, video, document, and voice-note messaging
- Live unread badges for Chat and Notifications in the sidebar
- Real-time notifications for chat and connection activity
- User profiles with bio, profile picture, account visibility, last-seen visibility, and read receipt settings
- Privacy controls for blocking and restricting users
- Direction-aware blocked chat states:
  - If you blocked a user, you can unblock them from the chat or Privacy page
  - If another user blocked you, the chat shows that you are blocked without exposing an unblock action
- Blocked chats remain visible in the chat list with a clear Blocked status
- Responsive dashboard UI with mobile sidebar navigation
- Light and dark theme support with persistent theme preference
- Theme-aware message bubbles, media cards, file previews, and composer controls

## Tech Stack

| Layer | Tools |
|---|---|
| Backend | Django 5, Django REST Framework |
| Realtime | Django Channels, WebSockets, ASGI |
| Authentication | SimpleJWT |
| Database | MySQL |
| Frontend | Django Templates, Tailwind CSS CDN, Vanilla JavaScript |
| UI | CSS variables, Lucide icons, responsive layouts |
| Media | Django file uploads for profile pictures and chat attachments |

## Core Features

### Authentication

PingNest uses JWT authentication with access and refresh tokens. The frontend API wrapper automatically retries requests after refreshing expired access tokens, which keeps active sessions smooth without repeatedly sending users back to login.

### Chat

Users can open one-to-one rooms with accepted connections, send text messages, share files, record voice notes, and view media messages directly in the chat timeline. WebSockets power instant delivery and room updates.

### Unread Badges

Unread counts update in the sidebar for both Chat and Notifications. Counts hide when zero and show a capped `99+` value when needed.

### Connections

Users can discover suggested profiles, send connection requests, and manage incoming requests. Chat access is limited to accepted connections.

### Privacy

The Privacy section gives users control over blocked and restricted accounts. Blocking removes the active connection and prevents messaging, while keeping the chat visible with a disabled, explanatory state.

### Theming

The UI supports light and dark modes with CSS custom properties. Theme preference is stored in localStorage and applied before paint to reduce theme flashing.

## Project Structure

```text
instagram_chat/
|-- apps/
|   |-- accounts/       # Custom user model, auth APIs, registration
|   |-- chats/          # Chat rooms, messages, media, WebSocket consumers
|   |-- connections/    # Connections, requests, blocks, restrictions
|   |-- core/           # Shared app utilities
|   |-- frontend/       # Template-rendering views and frontend routes
|   |-- notifications/  # Notification APIs and WebSocket consumers
|   `-- profiles/       # Profile, visibility, and read receipt settings
|-- config/             # Django settings, URLs, ASGI, WSGI
|-- static/frontend/
|   |-- css/style.css   # Theme variables and custom UI styles
|   `-- js/             # API, auth, chat, dashboard, and theme scripts
|-- templates/frontend/ # Base, login, register, dashboard templates
|-- media/              # Uploaded user and chat media
|-- manage.py
`-- requirements.txt
```

## Local Setup

### Prerequisites

- Python 3.10+
- MySQL Server
- Redis is optional for local development, but recommended for production Channels deployments

### 1. Clone the repository

```bash
git clone <your-repository-url>
```

### 2. Create and activate a virtual environment

Windows:

```bash
python -m venv venv
.\venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

Update `.env` with your local values:

```ini
SECRET_KEY=your-secure-secret-key
DEBUG=True
DB_NAME=pingnest_db
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
REDIS_URL=redis://127.0.0.1:6379/1
```

Important: `DEBUG` must be `True` or `False` because Django casts it as a boolean.

### 5. Create the database

```sql
CREATE DATABASE pingnest_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Start the development server

```bash
python manage.py runserver
```

Open the app at:

```text
http://127.0.0.1:8000/
```

## API Overview

| Endpoint | Method | Description |
|---|---:|---|
| `/api/v1/auth/register/` | POST | Create a new account |
| `/api/v1/auth/login/` | POST | Log in and receive JWT tokens |
| `/api/v1/auth/token/refresh/` | POST | Refresh access token |
| `/api/v1/profiles/me/` | GET/PATCH | View or update your profile |
| `/api/v1/profiles/` | GET | Browse public profiles |
| `/api/v1/connections/` | GET | List accepted connections |
| `/api/v1/connection-requests/send/` | POST | Send a connection request |
| `/api/v1/connection-requests/incoming/` | GET | View incoming connection requests |
| `/api/v1/chat-rooms/` | GET | List chat rooms, including blocked chats |
| `/api/v1/chat-rooms/one-to-one/` | POST | Create or open a one-to-one room |
| `/api/v1/chat-rooms/<id>/messages/` | GET | Load room messages |
| `/api/v1/chat-rooms/<id>/messages/send/` | POST | Send a text message |
| `/api/v1/chat-rooms/<id>/messages/media/` | POST | Send media or voice notes |
| `/api/v1/notifications/` | GET | List notifications |
| `/api/v1/blocks/` | GET | List blocked users |
| `/api/v1/blocks/block/` | POST | Block a user |
| `/api/v1/blocks/unblock/` | POST | Unblock a user |
| `/api/v1/restrictions/` | GET | List restricted users |
| `/api/v1/restrictions/restrict/` | POST | Restrict a user |
| `/api/v1/restrictions/unrestrict/` | POST | Unrestrict a user |

## WebSocket Routes

| Route | Purpose |
|---|---|
| `/ws/chat/rooms/<room_id>/?token=<access_token>` | Real-time room messages, typing, and read events |
| `/ws/chat/updates/?token=<access_token>` | Chat list and unread-count updates |
| `/ws/notifications/?token=<access_token>` | Real-time notification events |

## Portfolio Notes

PingNest demonstrates:

- REST API design with authenticated endpoints
- WebSocket consumers for real-time features
- A token refresh queue for smoother JWT sessions
- Privacy-aware chat behavior and moderation workflows
- Theme-aware frontend design using CSS custom properties
- Practical JavaScript state management without a heavy frontend framework
- Responsive UI patterns for desktop and mobile

## Future Improvements

- Group chats
- Message reactions and replies
- Search within chat history
- Push notifications
- Deployment with Docker, Daphne, Redis, and Nginx
- Automated frontend and backend test coverage

## Author

Built by Reena as a full-stack Django real-time messaging project.