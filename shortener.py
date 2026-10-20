"""
shortener.py — Core business logic for Ziply.

Responsibilities:
  * Generate a random 6-character alphanumeric short code.
  * Save the (code, original_url) mapping to SQLite, retrying on collision.
  * Support optional custom alias and expiry (in days).
  * Look up an original URL by its short code (returning None for expired links).
  * Record each successful redirect as a click event.
  * Provide list, delete, edit, analytics, and dashboard summary helpers.
"""

import secrets
import string
import sqlite3
from datetime import datetime, timedelta, timezone

import database

# Characters used to build short codes: A-Z, a-z, 0-9 (62 options)
_ALPHABET: str = string.ascii_letters + string.digits
CODE_LENGTH: int = 6
MAX_RETRIES: int = 5


# ── Code generation ───────────────────────────────────────────────────────────

def generate_code() -> str:
    """Return a cryptographically random 6-character alphanumeric string."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))


# ── Create ────────────────────────────────────────────────────────────────────

def create_short_code(
    original_url: str,
    *,
    alias: str | None = None,
    expires_days: int | None = None,
    user_id: int | None = None,
    db_path: str | None = None,
) -> str:
    """
    Generate a unique short code (or use the requested alias) for *original_url*
    and persist it.

    Args:
        original_url:  The validated HTTP/HTTPS URL to shorten.
        alias:         Optional custom short code (validated by models.py).
        expires_days:  Optional TTL in days from now.
        user_id:       Optional owning user ID (Phase 4).
        db_path:       Optional path to the SQLite file (used by tests).

    Returns:
        The unique short code that was stored.

    Raises:
        ValueError:    If the requested alias is already taken.
        RuntimeError:  If MAX_RETRIES collisions occur for auto-generated codes.
    """
    expires_at: str | None = None
    if expires_days is not None:
        dt = datetime.now(timezone.utc) + timedelta(days=expires_days)
        expires_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    if alias:
        # Use the caller-supplied alias directly
        try:
            with database.get_connection(db_path) as conn:
                conn.execute(
                    "INSERT INTO urls (code, original, alias, expires_at, user_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (alias, original_url, alias, expires_at, user_id),
                )
            return alias
        except sqlite3.IntegrityError:
            raise ValueError(f"The alias '{alias}' is already taken. Please choose another.")

    # Auto-generate a unique code
    for attempt in range(1, MAX_RETRIES + 1):
        code = generate_code()
        try:
            with database.get_connection(db_path) as conn:
                conn.execute(
                    "INSERT INTO urls (code, original, alias, expires_at, user_id) "
                    "VALUES (?, ?, NULL, ?, ?)",
                    (code, original_url, expires_at, user_id),
                )
            return code  # success — code is now in the database
        except sqlite3.IntegrityError:
            # PRIMARY KEY collision — try again
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Could not generate a unique short code after "
                    f"{MAX_RETRIES} attempts. Please try again."
                )

    # Should never be reached, but satisfies type checkers.
    raise RuntimeError("Unexpected error in create_short_code.")  # pragma: no cover


# ── Lookup (with expiry check) ────────────────────────────────────────────────

def get_original_url(code: str, db_path: str | None = None) -> str | None:
    """
    Return the original URL for *code*, or None if:
    * the code does not exist, or
    * the link has expired.

    Args:
        code:     The short code to look up.
        db_path:  Optional path to the SQLite file (used by tests).

    Returns:
        The original URL string, or None.
    """
    with database.get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT original, expires_at FROM urls WHERE code = ?", (code,)
        ).fetchone()

    if row is None:
        return None

    expires_at: str | None = row["expires_at"]
    if expires_at:
        expiry_dt = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        if datetime.now(timezone.utc) > expiry_dt:
            return None  # expired

    return row["original"]


def is_expired(code: str, db_path: str | None = None) -> bool:
    """Return True if the code exists but has passed its expiry datetime."""
    with database.get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT expires_at FROM urls WHERE code = ?", (code,)
        ).fetchone()
    if row is None:
        return False
    expires_at = row["expires_at"]
    if not expires_at:
        return False
    expiry_dt = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    return datetime.now(timezone.utc) > expiry_dt


# ── Click recording ───────────────────────────────────────────────────────────

def record_click(code: str, db_path: str | None = None) -> None:
    """Insert a click event for *code* with the current UTC timestamp."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with database.get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO clicks (code, visited_at) VALUES (?, ?)",
            (code, now),
        )


# ── Click count helper ────────────────────────────────────────────────────────

def get_click_count(code: str, db_path: str | None = None) -> int:
    """Return the total number of recorded clicks for *code*."""
    with database.get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM clicks WHERE code = ?", (code,)
        ).fetchone()
    return row["cnt"] if row else 0


# ── List links ────────────────────────────────────────────────────────────────

def list_links(user_id: int | None = None, db_path: str | None = None) -> list[dict]:
    """
    Return all links (optionally filtered by user_id) joined with their
    click counts, ordered newest first.

    Returns a list of dicts with keys:
        code, original, created_at, expires_at, user_id, click_count
    """
    with database.get_connection(db_path) as conn:
        if user_id is not None:
            rows = conn.execute(
                """
                SELECT u.code, u.original, u.created_at, u.expires_at, u.user_id,
                       COUNT(c.id) AS click_count
                  FROM urls u
                  LEFT JOIN clicks c ON c.code = u.code
                 WHERE u.user_id = ?
                 GROUP BY u.code
                 ORDER BY u.created_at DESC
                """,
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT u.code, u.original, u.created_at, u.expires_at, u.user_id,
                       COUNT(c.id) AS click_count
                  FROM urls u
                  LEFT JOIN clicks c ON c.code = u.code
                 GROUP BY u.code
                 ORDER BY u.created_at DESC
                """
            ).fetchall()
    return [dict(r) for r in rows]


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_link(code: str, db_path: str | None = None) -> bool:
    """
    Delete the link (and its clicks via CASCADE) identified by *code*.

    Returns True if a row was deleted, False if the code did not exist.
    """
    with database.get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM urls WHERE code = ?", (code,))
    return cursor.rowcount > 0


# ── Edit ──────────────────────────────────────────────────────────────────────

def update_link(
    code: str,
    *,
    new_alias: str | None = None,
    expires_days: int | None = None,
    db_path: str | None = None,
) -> bool:
    """
    Update the alias and/or expiry for an existing link.

    Pass expires_days=0 to clear the expiry (make the link permanent).
    Returns True if updated, False if the code did not exist.

    Raises:
        ValueError: If the new alias is already taken by a different code.
    """
    expires_at: str | None = None
    set_expiry = expires_days is not None

    if set_expiry:
        if expires_days == 0:
            expires_at = None
        else:
            dt = datetime.now(timezone.utc) + timedelta(days=expires_days)
            expires_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        with database.get_connection(db_path) as conn:
            if new_alias is not None and set_expiry:
                cursor = conn.execute(
                    "UPDATE urls SET alias = ?, expires_at = ? WHERE code = ?",
                    (new_alias or None, expires_at, code),
                )
            elif new_alias is not None:
                cursor = conn.execute(
                    "UPDATE urls SET alias = ? WHERE code = ?",
                    (new_alias or None, code),
                )
            elif set_expiry:
                cursor = conn.execute(
                    "UPDATE urls SET expires_at = ? WHERE code = ?",
                    (expires_at, code),
                )
            else:
                return False  # nothing to update
    except sqlite3.IntegrityError:
        raise ValueError(f"The alias '{new_alias}' is already taken.")

    return cursor.rowcount > 0


# ── Dashboard summary ─────────────────────────────────────────────────────────

def get_dashboard_summary(
    user_id: int | None = None, db_path: str | None = None
) -> dict:
    """
    Return {"total_links": int, "total_clicks": int} for the dashboard card.
    """
    with database.get_connection(db_path) as conn:
        if user_id is not None:
            link_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM urls WHERE user_id = ?", (user_id,)
            ).fetchone()
            click_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM clicks c "
                "JOIN urls u ON u.code = c.code WHERE u.user_id = ?",
                (user_id,),
            ).fetchone()
        else:
            link_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM urls"
            ).fetchone()
            click_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM clicks"
            ).fetchone()

    return {
        "total_links": link_row["cnt"] if link_row else 0,
        "total_clicks": click_row["cnt"] if click_row else 0,
    }


# ── Analytics ─────────────────────────────────────────────────────────────────

def get_analytics(code: str, db_path: str | None = None) -> dict | None:
    """
    Return full analytics for *code*:
    {
        "code": str,
        "original_url": str,
        "total_clicks": int,
        "last_visited": str | None,
        "click_trends": [{"timestamp": str, "cumulative": int}, ...],
        "recent_visits": [{"visitor_number": int, "visited_at": str}, ...]
    }
    Returns None if the code does not exist.
    """
    with database.get_connection(db_path) as conn:
        url_row = conn.execute(
            "SELECT original, created_at FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if url_row is None:
            return None

        click_rows = conn.execute(
            "SELECT visited_at FROM clicks WHERE code = ? ORDER BY visited_at ASC",
            (code,),
        ).fetchall()

    visits = [r["visited_at"] for r in click_rows]
    total = len(visits)
    last_visited = visits[-1] if visits else None

    # Build cumulative click trend points
    trends = [
        {"timestamp": ts, "cumulative": i + 1}
        for i, ts in enumerate(visits)
    ]

    # Recent visits (last 20, newest first)
    recent = [
        {"visitor_number": total - i, "visited_at": ts}
        for i, ts in enumerate(reversed(visits[:20]))
    ]

    return {
        "code": code,
        "original_url": url_row["original"],
        "total_clicks": total,
        "last_visited": last_visited,
        "click_trends": trends,
        "recent_visits": recent,
    }
