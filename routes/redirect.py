"""
routes/redirect.py — GET /{code}

Looks up the short code in the database:
  * 307 Temporary Redirect  → code exists and has not expired.
  * 410 Gone (HTML)         → code exists but has expired (friendly branded page).
  * 404 Not Found           → code has never existed.

Records a click event on every successful redirect.
"""

import os
import textwrap

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

import shortener

router = APIRouter()

# ── Friendly 410 HTML page ───────────────────────────────────────────────────

_EXPIRED_HTML = textwrap.dedent("""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Link Expired — Ziply</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', system-ui, sans-serif;
      background: #eef0f7;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }}
    .card {{
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
      padding: 3rem 2.5rem;
      max-width: 480px;
      width: 100%;
      text-align: center;
    }}
    .icon {{ font-size: 4rem; margin-bottom: 1.2rem; }}
    .badge {{
      display: inline-block;
      background: rgba(239,68,68,0.10);
      color: #ef4444;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      padding: 0.28rem 0.8rem;
      border-radius: 999px;
      margin-bottom: 1.2rem;
    }}
    h1 {{ font-size: 1.8rem; font-weight: 800; color: #1a2035; margin-bottom: 0.6rem; }}
    p  {{ color: #6b7280; line-height: 1.7; margin-bottom: 0.4rem; }}
    .code {{ font-family: monospace; color: #1a2035; font-weight: 600; }}
    .btn {{
      display: inline-block;
      margin-top: 2rem;
      background: #6c63ff;
      color: #fff;
      font-size: 0.92rem;
      font-weight: 600;
      padding: 0.75rem 2rem;
      border-radius: 8px;
      text-decoration: none;
      transition: background 0.15s;
    }}
    .btn:hover {{ background: #5a52e8; }}
    .brand {{
      margin-top: 2rem;
      font-size: 0.82rem;
      color: #9ca3af;
    }}
    .brand strong {{ color: #6c63ff; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">⏰</div>
    <span class="badge">410 GONE</span>
    <h1>Link Expired</h1>
    <p>The short link <span class="code">/{code}</span> has expired<br />and is no longer active.</p>
    <p style="margin-top:0.5rem">It was set to self-destruct after a certain date.<br />Please ask the sender for an updated link.</p>
    <a href="/" class="btn">⚡ Create a New Short Link</a>
    <div class="brand">Powered by <strong>Ziply.</strong> — Shorten · Track · Analyze</div>
  </div>
</body>
</html>
""")


@router.get("/{code}")
async def redirect_to_original(code: str) -> RedirectResponse:
    """
    Redirect the caller to the original URL associated with *code*.

    - Returns **307 Temporary Redirect** when the code exists and is active.
    - Returns **410 Gone** (HTML page) when the link has expired.
    - Returns **404 Not Found** when the code does not exist.

    HTTP 307 (rather than 301) is intentional: the browser does not cache
    the redirect permanently, which avoids stale redirects during development
    and makes it easy to reuse codes in future versions.
    """
    db_path = os.environ.get("DB_PATH")  # None → uses the module default

    # Check expiry separately so we can return 410 vs 404
    if shortener.is_expired(code, db_path=db_path):
        return HTMLResponse(
            content=_EXPIRED_HTML.format(code=code),
            status_code=410,
        )

    original_url = shortener.get_original_url(code, db_path=db_path)
    if original_url is None:
        raise HTTPException(
            status_code=404,
            detail=f"Short code '{code}' not found. "
                   "It may never have existed or may have been removed.",
        )

    # Record the visit
    shortener.record_click(code, db_path=db_path)

    return RedirectResponse(url=original_url, status_code=307)
