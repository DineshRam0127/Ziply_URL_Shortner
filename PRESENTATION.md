# Ziply — Demonstration Script

## Setup (30 seconds)

```bash
cd "c:\Users\dines\OneDrive\Desktop\METRIC STREAM\ziply"
pip install -r requirements.txt
uvicorn main:app --reload
```

Open **http://localhost:8000**

---

## Live Demo Script

### 1. Dashboard Overview

> **"This is the Ziply dashboard — matching the Katomaran reference design exactly."**

- Dark navy header with `Ziply.` wordmark and `SHORTEN · TRACK · ANALYZE` tagline
- Light/Dark toggle button (top right) — click to demonstrate dark mode
- **My Dashboard** card shows live link and click counts
- **Create Short URL** card below it

---

### 2. Shorten a URL

> **"Let me create a short link with a custom alias."**

1. In **DESTINATION URL** paste: `https://www.metricstream.com/solutions/grc`
2. In **CUSTOM ALIAS** type: `metricstream`
3. In **EXPIRES AFTER** type: `30`
4. Click **+ Shorten URL**
5. Success toast appears; Dashboard counts update to 1 link

---

### 3. My Links Table

> **"The link appears instantly in the My Links table."**

- **Original URL** column shows truncated URL
- **SHORT LINK** shows `↗ metricstream` — click to test the redirect (307)
- **CLICKS** badge shows live count (starts at 0, updates after redirect)
- **QR CODE** thumbnail auto-loaded
- **ACTIONS**: Copy, Edit, Delete, Analytics buttons

Demo Copy:
> Click **📋 Copy** → toast says "Copied to clipboard!"

Demo Edit:
> Click **✏ Edit** → modal opens → change expiry to 60 → Save → success toast

---

### 4. Analytics Page

> **"Each link has a full analytics page."**

1. Click **📊 Analytics** on any row
2. URL navigates to `/analytics/metricstream`

Point out:
- **ZIPLY ANALYTICS** orange pill badge
- **Analytics Dashboard** heading + **Back to Dashboard** button
- Three summary cards: Total Clicks (orange), Short Code, Last Visited
- **Click Trends** chart — live orange dots, hover tooltip shows "N Clicks"
- **Recent Visits** list — "Visitor #1" + timestamp + "● Active" badge

> **"All data is real — read live from SQLite."**

---

### 5. Search & Filter

> **"The search box filters links in real time."**

1. Create a second link: `https://github.com/` → alias `github`
2. Type `git` in the search box → only the GitHub link shows
3. Clear search → both links visible

---

### 6. Delete

> **"Deleting a link removes it and its click history instantly."**

1. Click **🗑 Delete** on the github link
2. Confirm dialog → link disappears; dashboard count decrements

---

### 7. Expiry Enforcement

```bash
# Simulate expiry via curl:
curl -X PATCH http://localhost:8000/api/links/metricstream \
  -H "Content-Type: application/json" \
  -d '{"expires_days": 0}'
```

> Now visit `/metricstream` in the browser → **410 Gone** (not a 404, not a redirect)

---

### 8. Dark Mode

Click the **🌙 Dark** button in the header:
- Background shifts to deep navy
- Cards become dark surfaces
- Chart updates to dark-mode colours
- Preference saved in `localStorage` — persists on page refresh

---

### 9. API (for developers)

Open `http://localhost:8000/docs` — Swagger UI with all endpoints documented:

| Endpoint | Description |
|---|---|
| `POST /api/shorten` | Create short link |
| `GET /api/links` | List all links |
| `DELETE /api/links/{code}` | Delete a link |
| `PATCH /api/links/{code}` | Edit alias/expiry |
| `GET /api/links/{code}/analytics` | Click analytics |
| `GET /api/links/{code}/qr` | QR code PNG |
| `GET /api/dashboard` | Summary counts |

---

### 10. Test Suite

```bash
python -m pytest tests/ -v
```

```
16 passed in 1.26s
```

Tests cover: shortening, unique codes, redirect (307), 404, 422 validation, collision retry, custom alias, duplicate alias (409), expired link (410), future expiry, click recording, dashboard counts, delete (204), PATCH expiry, QR PNG, analytics trends.

---

## Summary

| Requirement | Delivered |
|---|---|
| Reference-matched UI (navy header, white cards, violet buttons) | ✅ |
| Dashboard summary card with real counts | ✅ |
| Create Short URL card (alias + expiry) | ✅ |
| My Links table with QR, Copy, Edit, Delete, Analytics | ✅ |
| Analytics page with Chart.js trends + recent visits | ✅ |
| Dark mode toggle | ✅ |
| Expiry enforcement (410 Gone) | ✅ |
| Click recording on every redirect | ✅ |
| QR code generation (PNG) | ✅ |
| Custom alias with collision detection (409) | ✅ |
| All original tests pass + 10 new tests | ✅ (16/16) |
| Authentication (JWT) | 🔜 Phase 4 |
| Bulk CSV | 🔜 Phase 3 |
