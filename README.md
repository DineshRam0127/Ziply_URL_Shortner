# Ziply — URL Shortener v2

A fast, clean URL shortener with click analytics and a full dashboard UI.
Built with **FastAPI** + **SQLite** on the backend and **vanilla HTML/CSS/JS** on the frontend.

---

## Features

| Feature | Status |
|---|---|
| URL shortening (6-char auto code) | ✅ |
| Custom alias (e.g. `/my-brand`) | ✅ |
| Optional expiry (days) | ✅ |
| Click tracking on every redirect | ✅ |
| Dashboard summary (links + clicks) | ✅ |
| My Links table with search | ✅ |
| Copy / Edit / Delete actions | ✅ |
| Analytics page (chart + recent visits) | ✅ |
| QR code per link | ✅ |
| Dark mode toggle | ✅ |
| Expired link → 410 Gone | ✅ |
| 404 for unknown codes | ✅ |
| Authentication (JWT) | 🔜 Phase 4 |
| Bulk CSV shortening | 🔜 Phase 3 |

---

## Quick Start

### 1. Clone / navigate to the project

```bash
cd "c:\Users\dines\OneDrive\Desktop\METRIC STREAM\ziply"
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the server

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000** in your browser.

---

## Project Structure

```
ziply/
├── main.py               # FastAPI app entry point
├── database.py           # SQLite init + connection helper
├── models.py             # Pydantic request/response models
├── shortener.py          # Core business logic
├── requirements.txt
├── ziply.db              # SQLite database (auto-created)
│
├── routes/
│   ├── shorten.py        # POST /api/shorten
│   ├── redirect.py       # GET /{code}  (307 / 410 / 404)
│   └── links.py          # GET /api/links, DELETE, PATCH, analytics, QR
│
├── static/
│   ├── index.html        # Dashboard SPA
│   ├── analytics.html    # Analytics page
│   ├── style.css         # Katomaran reference design
│   ├── app.js            # Dashboard logic
│   └── analytics.js      # Analytics page logic
│
└── tests/
    └── test_shortener.py # 16 pytest tests (all passing)
```

---

## API Reference

### Health
```
GET /api/health
→ { "status": "ok" }
```

### Shorten a URL
```
POST /api/shorten
Content-Type: application/json

{
  "url": "https://example.com/very/long/url",
  "alias": "my-brand",        // optional, 1-30 alphanumeric chars
  "expires_days": 30          // optional, positive integer
}

→ 201 {
  "short_url": "http://localhost:8000/my-brand",
  "code": "my-brand",
  "original_url": "https://example.com/very/long/url",
  "created_at": "2026-10-20 11:31:58",
  "click_count": 0,
  "expires_at": "2026-11-19T11:31:58Z",
  "qr_url": "http://localhost:8000/api/links/my-brand/qr"
}
```

**Errors:**
- `422` — Invalid URL or alias format
- `409` — Alias already taken

### Redirect
```
GET /{code}
→ 307  Redirect to original URL  (click recorded)
→ 410  Link has expired
→ 404  Code not found
```

### Dashboard Summary
```
GET /api/dashboard
→ { "total_links": 7, "total_clicks": 12 }
```

### List Links
```
GET /api/links
→ [{ "code", "original_url", "short_url", "click_count", "created_at", "expires_at", "qr_url" }, ...]
```

### Delete Link
```
DELETE /api/links/{code}
→ 204 No Content
→ 404 Not found
```

### Edit Link
```
PATCH /api/links/{code}
{ "alias": "new-alias", "expires_days": 0 }
→ 200 { "status": "updated" }
→ 409 Alias taken
→ 404 Not found
```

### Analytics
```
GET /api/links/{code}/analytics
→ {
    "code": "my-brand",
    "original_url": "...",
    "total_clicks": 5,
    "last_visited": "2026-10-20T11:32:04Z",
    "click_trends": [{ "timestamp": "...", "cumulative": 1 }, ...],
    "recent_visits": [{ "visitor_number": 5, "visited_at": "..." }, ...]
  }
```

### QR Code
```
GET /api/links/{code}/qr
→ image/png
```

---

## Database Schema

```sql
CREATE TABLE urls (
    code        TEXT PRIMARY KEY,
    original    TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    alias       TEXT,               -- custom slug (nullable)
    expires_at  TEXT,               -- ISO datetime or NULL
    user_id     INTEGER             -- owner FK (Phase 4)
);

CREATE TABLE clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL REFERENCES urls(code) ON DELETE CASCADE,
    visited_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Expected: **16 passed** in ~1-2 seconds.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `ziply.db` | Path to SQLite database file |

---

## Roadmap

- **Phase 3**: Bulk CSV shortening, link editing in table
- **Phase 4**: JWT authentication, user registration/login, per-user link isolation
