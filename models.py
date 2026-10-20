"""
models.py — Pydantic request and response models for Ziply.

Keeping models in one place makes it easy to update the API shape
without touching route handlers.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


# ── Validators ────────────────────────────────────────────────────────────────

_ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{1,30}$")


# ── Shorten ───────────────────────────────────────────────────────────────────

class ShortenRequest(BaseModel):
    """Body expected by POST /api/shorten."""

    url: str
    alias: str | None = None
    expires_days: int | None = None

    @field_validator("url")
    @classmethod
    def must_be_http_or_https(cls, value: str) -> str:
        """
        Reject URLs that do not start with http:// or https://.
        Pydantic's HttpUrl already validates the structure; this validator
        adds an explicit scheme check so the error message is clear.
        """
        stripped = value.strip()
        if not (stripped.startswith("http://") or stripped.startswith("https://")):
            raise ValueError(
                "URL must begin with http:// or https://. "
                "Other schemes (ftp, mailto, etc.) are not accepted."
            )
        # Basic sanity: must have something after the scheme
        if len(stripped) < 10:
            raise ValueError("URL is too short to be valid.")
        return stripped

    @field_validator("alias")
    @classmethod
    def alias_must_be_alphanumeric(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if not _ALIAS_RE.match(stripped):
            raise ValueError(
                "Custom alias must be 1–30 characters and contain only "
                "letters, digits, hyphens (-) or underscores (_)."
            )
        return stripped

    @field_validator("expires_days")
    @classmethod
    def expires_days_must_be_positive(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 1:
            raise ValueError("Expiry must be at least 1 day.")
        if value > 3650:
            raise ValueError("Expiry cannot exceed 3650 days (10 years).")
        return value


class ShortenResponse(BaseModel):
    """Body returned by a successful POST /api/shorten."""

    short_url: str
    code: str
    original_url: str
    created_at: str
    click_count: int
    expires_at: str | None = None
    qr_url: str


# ── Dashboard / link list ─────────────────────────────────────────────────────

class LinkRow(BaseModel):
    """One row in the My Links table."""

    code: str
    original_url: str
    short_url: str
    click_count: int
    created_at: str
    expires_at: str | None = None
    qr_url: str


class DashboardSummary(BaseModel):
    """Counts shown in the 'My Dashboard' card."""

    total_links: int
    total_clicks: int


# ── Analytics ─────────────────────────────────────────────────────────────────

class ClickPoint(BaseModel):
    """A single point on the click-trends chart."""

    timestamp: str   # ISO datetime of the visit
    cumulative: int  # Running total at that point


class RecentVisit(BaseModel):
    """One row in the Recent Visits list."""

    visitor_number: int
    visited_at: str   # Human-readable datetime string


class AnalyticsData(BaseModel):
    """Full analytics payload for GET /api/links/{code}/analytics."""

    code: str
    original_url: str
    total_clicks: int
    last_visited: str | None  # None if never clicked
    click_trends: list[ClickPoint]
    recent_visits: list[RecentVisit]


# ── Auth (Phase 4) ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if not re.match(r"^[A-Za-z0-9_-]{3,30}$", v):
            raise ValueError("Username may only contain letters, digits, - or _.")
        return v

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters.")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Body returned by GET /api/health."""

    status: str
