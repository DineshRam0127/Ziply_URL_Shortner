"""
routes/links.py — Link management and analytics API.

All endpoints that mutate or list links are now authenticated (Phase 4):
  * GET  /api/dashboard         — scoped summary (total links + clicks for the authed user).
  * GET  /api/links             — list links owned by the authed user.
  * DELETE /api/links/{code}    — delete a link (only if owned by authed user).
  * PATCH  /api/links/{code}    — edit alias/expiry (only if owned by authed user).
  * GET  /api/links/{code}/analytics — click analytics (owner-checked).
  * GET  /api/links/{code}/qr       — PNG QR code (public — no auth required).
"""

import io
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, JSONResponse

import shortener
import database
from models import (
    DashboardSummary,
    LinkRow,
    AnalyticsData,
    ClickPoint,
    RecentVisit,
)
from routes.auth import require_auth, get_current_user_id

router = APIRouter()


# ── Helper: check ownership ───────────────────────────────────────────────────

def _assert_owner(code: str, user_id: int, db_path: str | None) -> None:
    """Raise 403 if the authed user does not own the given code."""
    with database.get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT user_id FROM urls WHERE code = ?", (code,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Short code '{code}' not found.")
    if row["user_id"] != user_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify this link.",
        )


# ── Dashboard summary ─────────────────────────────────────────────────────────

@router.get("/api/dashboard", response_model=DashboardSummary, tags=["links"])
async def dashboard_summary(
    user_id: int = Depends(require_auth),
) -> DashboardSummary:
    """Return total link count and total click count scoped to the authed user."""
    db_path = os.environ.get("DB_PATH")
    summary = shortener.get_dashboard_summary(user_id=user_id, db_path=db_path)
    return DashboardSummary(**summary)


# ── List links ────────────────────────────────────────────────────────────────

@router.get("/api/links", response_model=list[LinkRow], tags=["links"])
async def list_links(
    request: Request,
    user_id: int = Depends(require_auth),
) -> list[LinkRow]:
    """Return all shortened links owned by the authed user."""
    db_path = os.environ.get("DB_PATH")
    base_url = str(request.base_url).rstrip("/")
    rows = shortener.list_links(user_id=user_id, db_path=db_path)
    result = []
    for row in rows:
        code = row["code"]
        result.append(
            LinkRow(
                code=code,
                original_url=row["original"],
                short_url=f"{base_url}/{code}",
                click_count=row["click_count"],
                created_at=row["created_at"],
                expires_at=row.get("expires_at"),
                qr_url=f"{base_url}/api/links/{code}/qr",
            )
        )
    return result


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/api/links/{code}", status_code=204, tags=["links"])
async def delete_link(
    code: str,
    user_id: int = Depends(require_auth),
) -> Response:
    """Delete a short link and all its click history (owner only)."""
    db_path = os.environ.get("DB_PATH")
    _assert_owner(code, user_id, db_path)
    shortener.delete_link(code, db_path=db_path)
    return Response(status_code=204)


# ── Edit ──────────────────────────────────────────────────────────────────────

@router.patch("/api/links/{code}", tags=["links"])
async def edit_link(
    code: str,
    body: dict,
    user_id: int = Depends(require_auth),
) -> JSONResponse:
    """
    Update the alias and/or expiry for an existing link (owner only).

    Body (all fields optional):
        alias        — new custom alias, or empty string to clear
        expires_days — new TTL from today, or 0 to make permanent
    """
    db_path = os.environ.get("DB_PATH")
    _assert_owner(code, user_id, db_path)

    new_alias = body.get("alias")
    expires_days = body.get("expires_days")

    if expires_days is not None:
        try:
            expires_days = int(expires_days)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="expires_days must be an integer.")

    try:
        updated = shortener.update_link(
            code,
            new_alias=new_alias,
            expires_days=expires_days,
            db_path=db_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=404, detail=f"Short code '{code}' not found.")

    return JSONResponse({"status": "updated"})


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/api/links/{code}/analytics", response_model=AnalyticsData, tags=["analytics"])
async def link_analytics(
    code: str,
    user_id: int = Depends(require_auth),
) -> AnalyticsData:
    """Return click trends and recent visits for a single short link (owner only)."""
    db_path = os.environ.get("DB_PATH")
    _assert_owner(code, user_id, db_path)
    data = shortener.get_analytics(code, db_path=db_path)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Short code '{code}' not found.")

    return AnalyticsData(
        code=data["code"],
        original_url=data["original_url"],
        total_clicks=data["total_clicks"],
        last_visited=data["last_visited"],
        click_trends=[ClickPoint(**p) for p in data["click_trends"]],
        recent_visits=[RecentVisit(**v) for v in data["recent_visits"]],
    )


# ── QR code (public) ──────────────────────────────────────────────────────────

@router.get("/api/links/{code}/qr", tags=["links"])
async def qr_code(code: str, request: Request) -> Response:
    """Generate and return a PNG QR code image for the short link (public endpoint)."""
    import qrcode  # lazy import — only needed here

    db_path = os.environ.get("DB_PATH")

    # Verify the code exists (even if expired, QR is still valid to return)
    with database.get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT code FROM urls WHERE code = ?", (code,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Short code '{code}' not found.")

    base_url = str(request.base_url).rstrip("/")
    short_url = f"{base_url}/{code}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(short_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
