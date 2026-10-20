"""
routes/shorten.py — POST /api/shorten

Validates the incoming URL, creates a unique short code (or uses the
caller-supplied alias), records optional expiry, attaches the authed
user_id (Phase 4), and returns the full short URL together with metadata.
"""

import os

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

import shortener
from models import ShortenRequest, ShortenResponse
from routes.auth import require_auth

router = APIRouter()


@router.post("/api/shorten", response_model=ShortenResponse, status_code=201)
async def shorten_url(
    body: ShortenRequest,
    request: Request,
    user_id: int = Depends(require_auth),
) -> ShortenResponse:
    """
    Accept a URL (and optional alias / expiry), generate a unique short code,
    persist it under the authenticated user, and return the short URL with metadata.

    - **url**: A valid HTTP or HTTPS URL.
    - **alias** *(optional)*: A custom 1–30 character alphanumeric slug.
    - **expires_days** *(optional)*: Number of days until the link expires.

    Returns a JSON object with ``short_url``, ``code``, ``original_url``,
    ``created_at``, ``click_count``, ``expires_at``, and ``qr_url``.
    """
    db_path = os.environ.get("DB_PATH")  # None → uses the module default

    try:
        code = shortener.create_short_code(
            body.url,
            alias=body.alias,
            expires_days=body.expires_days,
            user_id=user_id,
            db_path=db_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Build the absolute short URL from the incoming request's base URL.
    base_url = str(request.base_url).rstrip("/")
    short_url = f"{base_url}/{code}"
    qr_url = f"{base_url}/api/links/{code}/qr"

    # Fetch the stored row to return accurate metadata
    links = shortener.list_links(db_path=db_path)
    row = next((lk for lk in links if lk["code"] == code), None)

    return ShortenResponse(
        short_url=short_url,
        code=code,
        original_url=body.url,
        created_at=row["created_at"] if row else "",
        click_count=0,
        expires_at=row["expires_at"] if row else None,
        qr_url=qr_url,
    )
