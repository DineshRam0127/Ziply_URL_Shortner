"""
tests/test_shortener.py — pytest test suite for Ziply v3 (Phase 4: JWT auth).

All tests use an isolated temporary SQLite file database so they:
  * Run without interfering with the development database (ziply.db).
  * Don't require Docker or a database server.
  * Clean up automatically after each test via the tmp_path fixture.

Test coverage:
  Phase 1 (original):
    1. Valid URL → short code + stored mapping.
    2. Two successive calls produce different (unique) codes.
    3. Known short code redirects (307) to original URL.
    4. Unknown code returns HTTP 404.
    5. Invalid / non-http(s) URL is rejected (422).
    6. Simulated code collision is handled safely via retry.

  Phase 2 (new):
    7.  Custom alias is stored and used as the short code.
    8.  Duplicate alias returns HTTP 409.
    9.  Expired link returns HTTP 410 (not 307).
    10. Non-expired link still redirects correctly.
    11. Click is recorded on each redirect.
    12. Dashboard counts reflect links and clicks.
    13. DELETE removes a link (204) and 404 afterwards.
    14. PATCH edits a link's expiry.
    15. QR endpoint returns PNG content.
    16. Analytics endpoint returns click trends.

  Phase 3 — Bulk CSV:
    17. Valid CSV upload.
    18. CSV header row auto-skipped.
    19. Invalid URL rows → per-row 422.
    20. Duplicate alias in CSV → per-row 409.
    21. Empty CSV → zero successful rows.
    22. CSV over 500-row limit → 413.

  Phase 4 — Authentication:
    23. Register creates a new user and returns a JWT.
    24. Duplicate username returns 409.
    25. Login with valid creds returns a JWT.
    26. Login with wrong password returns 401.
    27. /api/auth/me returns the logged-in user's info.
    28. Unauthenticated POST /api/shorten returns 401.
    29. Authenticated user can only see their own links.
    30. User cannot delete another user's link (403).
"""

import os
import pytest

# Set a placeholder DB_PATH before importing app modules.
os.environ.setdefault("DB_PATH", "test_ziply_placeholder.db")

from fastapi.testclient import TestClient  # noqa: E402

import database       # noqa: E402
import shortener      # noqa: E402
from main import app  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """
    Create a fresh temporary SQLite file before each test and remove it
    (via tmp_path cleanup) after. Sets DB_PATH so all modules pick it up.
    """
    db_file = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_file
    database.init_db(db_file)
    yield db_file
    # tmp_path is cleaned up automatically by pytest


@pytest.fixture()
def client(fresh_db):
    """Return a raw TestClient (no auth headers)."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _register_and_get_token(client, username="testuser", password="testpass1") -> str:
    """Helper: register a user and return the JWT access_token."""
    resp = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth_client(client):
    """
    Return (client, auth_headers) where auth_headers is a dict with the
    Bearer token for a freshly-registered test user.
    """
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


# ── Helper: shortens URL with auth headers ────────────────────────────────────

def shorten(client, url, headers, **kwargs):
    body = {"url": url, **kwargs}
    return client.post("/api/shorten", json=body, headers=headers)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — Core shortening
# ══════════════════════════════════════════════════════════════════════════════

def test_shorten_valid_url_returns_short_code(auth_client):
    """A valid HTTPS URL should produce a 201 response with a short_url and code."""
    c, h = auth_client
    response = shorten(c, "https://www.metricstream.com/products/grc-software", h)
    assert response.status_code == 201, response.text
    body = response.json()
    assert "short_url" in body
    assert "code" in body
    code = body["code"]
    assert len(code) == 6
    assert code.isalnum()


def test_two_requests_produce_different_codes(auth_client):
    """Two successive POST /api/shorten calls must return distinct codes."""
    c, h = auth_client
    r1 = shorten(c, "https://example.com/first", h)
    r2 = shorten(c, "https://example.com/second", h)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["code"] != r2.json()["code"]


def test_known_code_redirects_to_original_url(auth_client):
    """GET /{code} for a known code should redirect (307) to the original URL."""
    c, h = auth_client
    original = "https://www.metricstream.com/blog"
    post_resp = shorten(c, original, h)
    assert post_resp.status_code == 201
    code = post_resp.json()["code"]

    get_resp = c.get(f"/{code}", follow_redirects=False)
    assert get_resp.status_code == 307
    assert get_resp.headers["location"] == original


def test_unknown_code_returns_404(client):
    """GET /{code} for a non-existent code must return HTTP 404."""
    response = client.get("/XXXXXX", follow_redirects=False)
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body


def test_invalid_url_is_rejected(auth_client):
    """POST /api/shorten with a URL that lacks http(s):// must be rejected (422)."""
    c, h = auth_client
    bad_urls = [
        "ftp://example.com/file",
        "not-a-url-at-all",
        "javascript:alert(1)",
        "",
    ]
    for bad in bad_urls:
        resp = shorten(c, bad, h)
        assert resp.status_code == 422, (
            f"Expected 422 for '{bad}', got {resp.status_code}: {resp.text}"
        )


def test_collision_is_handled_safely(fresh_db, monkeypatch):
    """
    When the first generated code already exists, create_short_code must retry.
    """
    db_path = fresh_db

    # First register a user to get a token
    with TestClient(app, raise_server_exceptions=True) as c:
        token = _register_and_get_token(c)
        headers = {"Authorization": f"Bearer {token}"}

        with database.get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO urls (code, original) VALUES (?, ?)",
                ("TAKEN1", "https://already-exists.com"),
            )

        call_count = {"n": 0}
        original_generate = shortener.generate_code

        def fake_generate():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "TAKEN1"
            return original_generate()

        monkeypatch.setattr(shortener, "generate_code", fake_generate)

        resp = c.post(
            "/api/shorten",
            json={"url": "https://collision-test.com/page"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        code = resp.json()["code"]
        assert code != "TAKEN1"
        assert len(code) == 6
        assert call_count["n"] >= 2

        stored = shortener.get_original_url(code, db_path=db_path)
        assert stored == "https://collision-test.com/page"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — Custom alias, expiry, clicks, analytics
# ══════════════════════════════════════════════════════════════════════════════

def test_custom_alias_is_used_as_code(auth_client):
    """POST /api/shorten with alias='my-test' should store and return 'my-test'."""
    c, h = auth_client
    resp = shorten(c, "https://example.com/alias-test", h, alias="my-test")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == "my-test"
    assert body["short_url"].endswith("/my-test")


def test_duplicate_alias_returns_409(auth_client):
    """A second request with the same alias must return 409 Conflict."""
    c, h = auth_client
    shorten(c, "https://first.com", h, alias="same")
    resp2 = shorten(c, "https://second.com", h, alias="same")
    assert resp2.status_code == 409, resp2.text


def test_expired_link_returns_410(fresh_db):
    """A link with expires_at in the past should return 410 (HTML expired page), not 307."""
    from datetime import datetime, timezone, timedelta

    db_path = fresh_db
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with database.get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO urls (code, original, expires_at) VALUES (?, ?, ?)",
            ("xprd01", "https://expired.example.com", past),
        )

    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.get("/xprd01", follow_redirects=False)
    assert resp.status_code == 410, resp.text
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Link Expired" in resp.text or "410" in resp.text


def test_future_expiry_still_redirects(auth_client):
    """A link with a future expiry date should redirect normally (307)."""
    c, h = auth_client
    resp = shorten(c, "https://future.example.com", h, expires_days=30)
    assert resp.status_code == 201
    code = resp.json()["code"]
    get_resp = c.get(f"/{code}", follow_redirects=False)
    assert get_resp.status_code == 307


def test_click_recorded_on_redirect(auth_client, fresh_db):
    """Each redirect should insert one row into the clicks table."""
    c, h = auth_client
    resp = shorten(c, "https://click-test.com", h)
    code = resp.json()["code"]

    c.get(f"/{code}", follow_redirects=False)
    c.get(f"/{code}", follow_redirects=False)

    count = shortener.get_click_count(code, db_path=fresh_db)
    assert count == 2


def test_dashboard_counts_are_accurate(auth_client):
    """GET /api/dashboard should reflect the number of links and clicks for the authed user."""
    c, h = auth_client
    r = c.get("/api/dashboard", headers=h)
    assert r.status_code == 200
    start = r.json()
    assert start["total_links"] == 0
    assert start["total_clicks"] == 0

    shorten(c, "https://count-test-1.com", h)
    r2 = shorten(c, "https://count-test-2.com", h)
    code2 = r2.json()["code"]

    c.get(f"/{code2}", follow_redirects=False)

    r3 = c.get("/api/dashboard", headers=h)
    assert r3.json()["total_links"] == 2
    assert r3.json()["total_clicks"] == 1


def test_delete_link_removes_it(auth_client):
    """DELETE /api/links/{code} should remove the link; 404 redirect afterwards."""
    c, h = auth_client
    resp = shorten(c, "https://delete-me.com", h)
    code = resp.json()["code"]

    del_resp = c.delete(f"/api/links/{code}", headers=h)
    assert del_resp.status_code == 204

    get_resp = c.get(f"/{code}", follow_redirects=False)
    assert get_resp.status_code == 404


def test_patch_updates_expiry(auth_client, fresh_db):
    """PATCH /api/links/{code} with expires_days=0 should clear the expiry."""
    c, h = auth_client
    resp = shorten(c, "https://edit-me.com", h, expires_days=5)
    code = resp.json()["code"]

    patch_resp = c.patch(
        f"/api/links/{code}",
        json={"expires_days": 0},
        headers=h,
    )
    assert patch_resp.status_code == 200

    get_resp = c.get(f"/{code}", follow_redirects=False)
    assert get_resp.status_code == 307


def test_qr_endpoint_returns_png(auth_client):
    """GET /api/links/{code}/qr should return image/png (no auth required)."""
    c, h = auth_client
    resp = shorten(c, "https://qr-test.com", h)
    code = resp.json()["code"]

    qr_resp = c.get(f"/api/links/{code}/qr")  # QR is public
    assert qr_resp.status_code == 200
    assert qr_resp.headers["content-type"] == "image/png"
    assert len(qr_resp.content) > 100


def test_analytics_returns_click_trends(auth_client):
    """GET /api/links/{code}/analytics should include click_trends after redirects."""
    c, h = auth_client
    resp = shorten(c, "https://analytics-test.com", h)
    code = resp.json()["code"]

    c.get(f"/{code}", follow_redirects=False)
    c.get(f"/{code}", follow_redirects=False)

    a = c.get(f"/api/links/{code}/analytics", headers=h)
    assert a.status_code == 200
    data = a.json()
    assert data["total_clicks"] == 2
    assert len(data["click_trends"]) == 2
    assert data["click_trends"][-1]["cumulative"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3 — Bulk CSV shortening
# ══════════════════════════════════════════════════════════════════════════════

def test_bulk_csv_valid_rows(auth_client):
    """
    POST /api/bulk with a valid 3-row CSV should return 207 with per-row status 201.
    """
    c, h = auth_client
    csv_content = (
        "https://bulk-test-1.com\n"
        "https://bulk-test-2.com,bulk-alias\n"
        "https://bulk-test-3.com,bulk-alias-exp,30\n"
    ).encode()

    resp = c.post(
        "/api/bulk",
        files={"file": ("links.csv", csv_content, "text/csv")},
        headers=h,
    )
    assert resp.status_code == 207, resp.text
    results = resp.json()
    assert len(results) == 3
    for r in results:
        assert r["status"] == 201, f"Row {r['row']} failed: {r}"
        assert "code" in r
        assert r["short_url"].startswith("http")

    alias_row = next(r for r in results if r["row"] == 2)
    assert alias_row["code"] == "bulk-alias"


def test_bulk_csv_header_row_skipped(auth_client):
    """If the first row is 'url' (case-insensitive), it should be skipped."""
    c, h = auth_client
    csv_content = (
        "url,alias,expires_days\n"
        "https://headertest.com,,\n"
    ).encode()

    resp = c.post(
        "/api/bulk",
        files={"file": ("links.csv", csv_content, "text/csv")},
        headers=h,
    )
    assert resp.status_code == 207, resp.text
    results = resp.json()
    assert len(results) == 1
    assert results[0]["status"] == 201


def test_bulk_csv_invalid_rows(auth_client):
    """Invalid URL rows should return per-row 422; valid rows still succeed."""
    c, h = auth_client
    csv_content = (
        "https://valid-bulk.com\n"
        "ftp://not-allowed.com\n"
        "not-a-url-at-all\n"
        "https://valid-bulk-2.com\n"
    ).encode()

    resp = c.post(
        "/api/bulk",
        files={"file": ("mixed.csv", csv_content, "text/csv")},
        headers=h,
    )
    assert resp.status_code == 207, resp.text
    results = resp.json()
    assert len(results) == 4

    statuses = {r["row"]: r["status"] for r in results}
    assert statuses[1] == 201
    assert statuses[2] == 422
    assert statuses[3] == 422
    assert statuses[4] == 201


def test_bulk_csv_duplicate_alias_returns_409(auth_client):
    """Duplicate alias in bulk upload should return row status 409."""
    c, h = auth_client
    csv_content = (
        "https://first-bulk.com,shared-alias\n"
        "https://second-bulk.com,shared-alias\n"
    ).encode()

    resp = c.post(
        "/api/bulk",
        files={"file": ("dup.csv", csv_content, "text/csv")},
        headers=h,
    )
    assert resp.status_code == 207, resp.text
    results = resp.json()
    assert len(results) == 2
    assert results[0]["status"] == 201
    assert results[1]["status"] == 409


def test_bulk_csv_empty_file(auth_client):
    """An empty CSV file (after header skip) returns 207 with zero rows."""
    c, h = auth_client
    csv_content = b"\n\n"
    resp = c.post(
        "/api/bulk",
        files={"file": ("empty.csv", csv_content, "text/csv")},
        headers=h,
    )
    assert resp.status_code == 207, resp.text
    results = resp.json()
    for r in results:
        assert r["status"] == 400


def test_bulk_csv_exceeds_row_limit(auth_client):
    """A CSV with more than 500 rows should return HTTP 413."""
    c, h = auth_client
    rows = "\n".join(f"https://limit-test-{i}.com" for i in range(501))
    resp = c.post(
        "/api/bulk",
        files={"file": ("big.csv", rows.encode(), "text/csv")},
        headers=h,
    )
    assert resp.status_code == 413, resp.text


# ══════════════════════════════════════════════════════════════════════════════
# Phase 4 — Authentication & Ownership
# ══════════════════════════════════════════════════════════════════════════════

# ── Test 23: Register returns JWT ────────────────────────────────────────────

def test_register_returns_jwt(client):
    """POST /api/auth/register should create user and return access_token."""
    resp = client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "secure123"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


# ── Test 24: Duplicate username → 409 ────────────────────────────────────────

def test_register_duplicate_username_returns_409(client):
    """Registering with an already-taken username must return 409."""
    client.post("/api/auth/register", json={"username": "dupeuser", "password": "pass123"})
    resp2 = client.post("/api/auth/register", json={"username": "dupeuser", "password": "otherpass"})
    assert resp2.status_code == 409, resp2.text


# ── Test 25: Login with valid creds returns JWT ───────────────────────────────

def test_login_valid_credentials_returns_jwt(client):
    """POST /api/auth/login with correct creds should return access_token."""
    client.post("/api/auth/register", json={"username": "loginuser", "password": "mypassword"})
    resp = client.post("/api/auth/login", json={"username": "loginuser", "password": "mypassword"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body


# ── Test 26: Wrong password → 401 ────────────────────────────────────────────

def test_login_wrong_password_returns_401(client):
    """POST /api/auth/login with wrong password must return 401."""
    client.post("/api/auth/register", json={"username": "secureuser", "password": "correctpass"})
    resp = client.post("/api/auth/login", json={"username": "secureuser", "password": "wrongpass"})
    assert resp.status_code == 401, resp.text


# ── Test 27: /api/auth/me returns user info ───────────────────────────────────

def test_me_returns_user_info(client):
    """GET /api/auth/me with a valid token should return username and id."""
    token = _register_and_get_token(client, "meuser", "mepass1")
    resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"] == "meuser"
    assert "id" in body
    assert "created_at" in body


# ── Test 28: Unauthenticated shorten → 401 ───────────────────────────────────

def test_unauthenticated_shorten_returns_401(client):
    """POST /api/shorten without a Bearer token must return 401."""
    resp = client.post("/api/shorten", json={"url": "https://noauth.com"})
    assert resp.status_code == 401, resp.text


# ── Test 29: User sees only their own links ───────────────────────────────────

def test_user_sees_only_own_links(client):
    """Each user's GET /api/links should only return links they created."""
    token_a = _register_and_get_token(client, "userA", "passA123")
    token_b = _register_and_get_token(client, "userB", "passB123")

    ha = {"Authorization": f"Bearer {token_a}"}
    hb = {"Authorization": f"Bearer {token_b}"}

    # User A creates 2 links
    client.post("/api/shorten", json={"url": "https://a-link-1.com"}, headers=ha)
    client.post("/api/shorten", json={"url": "https://a-link-2.com"}, headers=ha)

    # User B creates 1 link
    client.post("/api/shorten", json={"url": "https://b-link-1.com"}, headers=hb)

    links_a = client.get("/api/links", headers=ha).json()
    links_b = client.get("/api/links", headers=hb).json()

    assert len(links_a) == 2
    assert len(links_b) == 1
    # User B's link should not appear in User A's list
    codes_a = {l["code"] for l in links_a}
    codes_b = {l["code"] for l in links_b}
    assert codes_a.isdisjoint(codes_b)


# ── Test 30: User cannot delete another user's link ──────────────────────────

def test_user_cannot_delete_other_users_link(client):
    """DELETE /api/links/{code} for a link owned by another user must return 403."""
    token_a = _register_and_get_token(client, "ownerA", "ownerPass1")
    token_b = _register_and_get_token(client, "attackerB", "attackPass1")

    ha = {"Authorization": f"Bearer {token_a}"}
    hb = {"Authorization": f"Bearer {token_b}"}

    # User A creates a link
    resp = client.post("/api/shorten", json={"url": "https://owners-link.com"}, headers=ha)
    code = resp.json()["code"]

    # User B tries to delete it
    del_resp = client.delete(f"/api/links/{code}", headers=hb)
    assert del_resp.status_code == 403, del_resp.text

    # Link still exists
    redirect_resp = client.get(f"/{code}", follow_redirects=False)
    assert redirect_resp.status_code == 307
