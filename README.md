# Calendai — AI Calendar Assistant

A full-stack, fully offline AI-powered calendar assistant. Chat naturally to schedule events, query your agenda, and get smart reminders — all without any external API bills.

```
Frontend  React 18 + Vite  →  http://localhost:5173
Backend   FastAPI           →  http://localhost:8000
LLM       Ollama (local)    →  http://localhost:11434
Database  SQLite            →  scheduler.db
```

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Prerequisites](#prerequisites)
5. [Installation](#installation)
6. [Running the App](#running-the-app)
7. [Configuration](#configuration)
8. [API Reference](#api-reference)
9. [Voice Input](#voice-input)
10. [Google Calendar Sync](#google-calendar-sync)
11. [Agentic Background Jobs](#agentic-background-jobs)
12. [Switching LLM Models](#switching-llm-models)
13. [Troubleshooting](#troubleshooting)
14. [Tech Stack](#tech-stack)

---

## Features

| Feature | Description |
|---|---|
| **Natural language scheduling** | "Schedule a team meeting tomorrow at 3pm" → event created |
| **Voice input** | Browser mic button → speech-to-text → auto-fill or auto-send |
| **Calendar queries** | "What do I have this week?" → AI reads your upcoming events |
| **Google Calendar sync** | Two-way: push new events to Google, pull existing ones in |
| **Smart reminders** | Background job fires 30 min before events with AI-generated context |
| **Pattern insights** | AI analyses 30 days of your events and surfaces scheduling habits |
| **Fully offline LLM** | Runs on Ollama — no OpenAI key, no quota issues, no data sent externally |
| **Conversation memory** | Multi-turn chat history stored in SQLite per conversation |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
│                                                             │
│   React (Vite)  ←──── App.jsx ─────►  Web Speech API       │
│   Tailwind CSS         Chat UI        (voice input)         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP  POST /chat
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│                                                             │
│  main.py ──► task_extractor.py ──► ollama_client.py         │
│     │               │                      │               │
│     │        event parsing             POST /api/generate  │
│     │        pattern analysis              │               │
│     ▼               ▼               ┌──────▼──────┐        │
│  database.py    agent.py            │   Ollama    │        │
│  (SQLAlchemy)                       │  (mistral)  │        │
│     │                               └─────────────┘        │
│     ▼                                                       │
│  scheduler.db                                               │
│  (SQLite)                                                   │
│     │                                                       │
│  calendar_sync.py ──────────────────► Google Calendar API   │
│                                                             │
│  APScheduler (background)                                   │
│  ├─ every  5 min → smart reminders                         │
│  └─ every 24 hrs → pattern analysis                        │
└─────────────────────────────────────────────────────────────┘
```

### Request lifecycle — `/chat`

```
User types / speaks
       │
       ▼
POST /chat  { message, conversation_id }
       │
       ├─ Save user message to DB
       ├─ Fetch recent conversation history
       ├─ If calendar query → load upcoming events from DB
       │
       ├─ extract_events_from_conversation()
       │       ├─ Build structured prompt
       │       ├─ call_local_llm()  →  Ollama
       │       ├─ safe_parse_json() (strips fences, finds JSON)
       │       └─ Fallback: rule_based_event_extract() (regex)
       │
       ├─ Save assistant reply to DB
       ├─ For each extracted event:
       │       ├─ INSERT into events table
       │       └─ create_calendar_event() → Google Calendar (optional)
       │
       └─ Return ChatResponse { assistant_message, events, conversation_id }
```

---

## Project Structure

```
smart-scheduling-agent/
│
├── backend/
│   ├── main.py              # FastAPI app, all HTTP endpoints, scheduler setup
│   ├── database.py          # SQLAlchemy models (Conversation, Message, Event)
│   ├── models.py            # Pydantic request/response schemas
│   ├── task_extractor.py    # LLM prompts: event extraction, reminders, insights
│   ├── ollama_client.py     # Ollama HTTP client, JSON parser, regex fallback
│   ├── agent.py             # Task pattern analysis, follow-up messages
│   ├── calendar_sync.py     # Google Calendar OAuth + CRUD helpers
│   ├── credentials.json     # Google OAuth client secrets (do not commit)
│   ├── token.pickle         # Cached Google OAuth token (auto-generated)
│   ├── scheduler.db         # SQLite database (auto-generated on first run)
│   └── extracttesting.py    # Quick smoke-test for event extraction
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    └── src/
        ├── main.jsx         # React entry point
        └── App.jsx          # Entire frontend: chat UI, voice hook, event cards
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | 3.11 recommended |
| Node.js | 18+ | For Vite / React |
| Ollama | Latest | [ollama.com](https://ollama.com) |
| Git | Any | |
| Chrome / Edge | Any | Required for voice input (Web Speech API) |

> Firefox does **not** support the Web Speech API. Voice input will be silently hidden on unsupported browsers.

---

## Installation

### 1 — Clone the repo

```bash
git clone https://github.com/your-username/smart-scheduling-agent.git
cd smart-scheduling-agent
```

### 2 — Backend setup

```bash
cd backend

# Create and activate a virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn sqlalchemy pydantic python-dotenv \
            requests apscheduler google-auth google-auth-oauthlib \
            google-api-python-client
```

> If you previously used OpenAI you can safely remove it: `pip uninstall openai`

### 3 — Frontend setup

```bash
cd ../frontend
npm install
```

### 4 — Install and start Ollama

```bash
# Install Ollama
# Linux / WSL:
curl -fsSL https://ollama.com/install.sh | sh

# macOS:
brew install ollama

# Pull a model (one-time ~4 GB download)
ollama pull mistral       # recommended — fast, reliable JSON output
# OR
ollama pull llama3        # larger, more capable

# Start the Ollama server (keep this terminal open)
ollama serve
```

---

## Running the App

You need **three terminals** running simultaneously.

**Terminal 1 — Ollama**
```bash
ollama serve
```

**Terminal 2 — Backend**
```bash
cd backend
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

python main.py
```

Expected output:
```
🚀 Starting AI Calendar Assistant Backend...
📍 Backend will be available at: http://localhost:8000
📚 API docs available at: http://localhost:8000/docs
✅ Agentic AI monitoring started!
```

**Terminal 3 — Frontend**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in Chrome or Edge.

---

## Configuration

### Environment variables

Create a `.env` file in the `backend/` folder:

```env
# Optional — only needed if you re-enable OpenAI for any reason
# OPENAI_API_KEY=sk-...

# SQLite database path (default: ./scheduler.db)
# DATABASE_URL=sqlite:///./scheduler.db
```

### Changing the LLM model

Edit the top of `backend/ollama_client.py`:

```python
OLLAMA_MODEL    = "mistral"   # change to "llama3", "phi3", "gemma3", etc.
REQUEST_TIMEOUT = 90          # increase if your hardware is slow
```

Any model you have pulled with `ollama pull <name>` will work.

### Available models (recommended)

| Model | Size | Best for |
|---|---|---|
| `mistral` | 4.1 GB | Speed + JSON reliability ✅ |
| `llama3` | 4.7 GB | More conversational responses |
| `phi3` | 2.3 GB | Low-memory machines |
| `gemma3` | 5.2 GB | Balanced quality |

---

## API Reference

Interactive docs available at **http://localhost:8000/docs** when the backend is running.

### POST `/chat`

Main chat endpoint. Processes a message, extracts events, and returns a response.

**Request**
```json
{
  "message": "Schedule a design review on Friday at 2pm",
  "conversation_id": null
}
```

**Response**
```json
{
  "message": { "id": 1, "role": "user", "content": "...", "timestamp": "..." },
  "assistant_message": { "id": 2, "role": "assistant", "content": "Done! ...", "timestamp": "..." },
  "events": [
    {
      "id": 1,
      "title": "Design Review",
      "start_time": "2025-07-04T14:00:00",
      "end_time": "2025-07-04T15:00:00",
      "location": null,
      "status": "confirmed",
      "calendar_event_id": "abc123xyz",
      "created_at": "..."
    }
  ],
  "conversation_id": 1
}
```

### Other endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/events` | All upcoming events |
| GET | `/events/{id}` | Single event |
| PUT | `/events/{id}` | Update an event |
| DELETE | `/events/{id}` | Delete an event |
| GET | `/events/insights` | AI pattern analysis |
| GET | `/conversations` | All conversations |
| GET | `/conversations/{id}` | Single conversation with messages |
| DELETE | `/conversations/{id}` | Delete conversation |
| POST | `/sync-calendar` | Pull events from Google Calendar |
| POST | `/chat/voice` | Voice chat (audio file upload) |

---

## Voice Input

Voice input is handled entirely in the browser using the **Web Speech API** — no server round-trip for transcription.

### How it works

1. Click the **microphone button** in the chat input area.
2. Speak your message. The transcript appears in the input field in real time.
3. Click the button again (or wait for the API to auto-stop) to finish.
4. Either press **Enter** to send, or enable **Auto-send** in the sidebar to send automatically when you stop speaking.

### Auto-send toggle

Found in the left sidebar. When enabled, the recognized text is sent to the backend 300ms after speech ends (the delay lets the input field visually update first).

### Browser support

| Browser | Voice input |
|---|---|
| Chrome | ✅ Full support |
| Edge | ✅ Full support |
| Safari | ✅ Partial (iOS 14.5+) |
| Firefox | ❌ Not supported |

The mic button is **silently hidden** on unsupported browsers — nothing breaks.

### Error messages

| Error | What it means |
|---|---|
| "Microphone access denied" | Click the lock icon in the address bar and allow microphone access |
| "No speech detected" | Background noise may have triggered it — try again |
| "No microphone found" | Check your system audio settings |

---

## Google Calendar Sync

Calendar sync is **optional**. The app works fully without it.

### Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com).
2. Create a project → enable the **Google Calendar API**.
3. Create **OAuth 2.0 credentials** (Desktop app type).
4. Download the JSON and save it as `backend/credentials.json`.

### First run

On the first request that touches Google Calendar, a browser window will open asking you to authorise the app. After you approve, a `token.pickle` file is saved so you won't be asked again.

### What syncs

| Action | Direction |
|---|---|
| New event created via chat | Local DB → Google Calendar |
| Event updated via `PUT /events/{id}` | Local DB → Google Calendar |
| Event deleted via `DELETE /events/{id}` | Local DB → Google Calendar |
| `POST /sync-calendar` | Google Calendar → Local DB (import only) |

> If `credentials.json` is missing, all calendar sync calls are silently skipped — events still save to the local SQLite database.

---

## Agentic Background Jobs

Two background tasks run automatically when the backend starts (powered by APScheduler).

### Smart reminders — every 5 minutes

Queries for events starting in the next 30 minutes. For each one, the LLM generates a personalised reminder based on:
- Event title, location, and description
- The user's average event scheduling time (context)

Reminders are currently printed to the terminal. To send them via email or push notification, edit `check_upcoming_events()` in `main.py`.

### Pattern analysis — every 24 hours

Loads all events from the last 30 days and asks the LLM to identify:
- Peak scheduling hours and days
- Meeting patterns (solo vs group, location preferences)
- Actionable suggestions to optimise the calendar

Results are printed to the terminal and available on demand via `GET /events/insights`.

---

## Switching LLM Models

### Pull a new model

```bash
ollama pull llama3
```

### Update the config

```python
# backend/ollama_client.py
OLLAMA_MODEL = "llama3"
```

Restart the backend. No other changes needed.

### List models you have installed

```bash
ollama list
```

---

## Troubleshooting

### `AttributeError: 'Event' object has no attribute 'get'`

This was a bug where `.get()` (dict-only) was called on SQLAlchemy ORM objects. Fixed in the latest `task_extractor.py` — make sure you're using the updated file.

### `Cannot connect to Ollama at http://localhost:11434`

Ollama is not running. Start it with:
```bash
ollama serve
```

### `DeprecationWarning: on_event is deprecated`

This is a non-breaking warning from FastAPI about `@app.on_event("startup")`. The app works correctly. To suppress it, the startup logic can be migrated to a `lifespan` context manager in a future update.

### Backend returns 500 on `/chat`

Check the terminal for the full traceback. Common causes:
- Ollama is not running (all LLM calls return `""`)
- `task_extractor.py` is the old OpenAI version
- The database schema is stale — delete `scheduler.db` and restart to recreate it

### Frontend shows "Could not reach the backend"

- Confirm the backend is running on port 8000: `http://localhost:8000/health`
- Check that CORS is not blocked — the backend allows all origins by default
- On Windows, check that Windows Firewall isn't blocking port 8000

### Voice button doesn't appear

- You must be using Chrome or Edge
- The page must be served over `http://localhost` or `https://` (not a raw IP)
- Check browser console for errors

### Google Calendar auth loop

Delete `token.pickle` and restart the backend. A new browser auth window will open.

---

## Tech Stack

**Backend**

| Package | Purpose |
|---|---|
| FastAPI | HTTP framework, routing, request validation |
| SQLAlchemy | ORM for SQLite |
| Pydantic | Request/response schema validation |
| APScheduler | Background jobs (reminders, analysis) |
| Requests | HTTP calls to Ollama |
| google-auth / google-api-python-client | Google Calendar OAuth + API |
| python-dotenv | `.env` file loading |
| Uvicorn | ASGI server |

**Frontend**

| Package | Purpose |
|---|---|
| React 18 | UI framework |
| Vite | Dev server + build tool |
| Tailwind CSS | Utility CSS (config in project, styles in `App.jsx`) |
| Web Speech API | Browser-native voice input — no extra package |

**Infrastructure**

| Tool | Purpose |
|---|---|

| Ollama | Local LLM runtime |
| Mistral / Llama 3 | Language model (your choice) |
| SQLite | Zero-config local database |

---

## Licence

MIT — free to use, modify, and distribute.
