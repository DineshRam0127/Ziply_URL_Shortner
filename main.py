"""
main.py — Ziply FastAPI application entry point.

Wires together:
  * Database initialisation (creates ziply.db and all tables on startup).
  * API routers for auth, shortening, link management, bulk, and redirecting.
  * Static file serving for the HTML/CSS/JS frontend.
  * A /api/health endpoint for local verification.

Run with:
    cd ziply
    uvicorn main:app --reload
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import database
from routes.shorten import router as shorten_router
from routes.redirect import router as redirect_router
from routes.links import router as links_router
from routes.bulk import router as bulk_router
from routes.auth import router as auth_router


# ---------------------------------------------------------------------------
# Lifespan: initialise the database once on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler — replaces deprecated on_event('startup')."""
    db_path = os.environ.get("DB_PATH")  # None → database.py uses its default
    database.init_db(db_path)
    yield  # application runs here


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ziply — URL Shortener",
    description="A fast, clean URL shortener with click analytics and JWT auth. Built with FastAPI and SQLite.",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS middleware (permissive for local development; tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health endpoint — registered BEFORE the /{code} catch-all router
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["meta"])
async def health() -> JSONResponse:
    """Simple liveness check."""
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# API routers
# Order matters: specific API routes BEFORE the catch-all redirect router.
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(shorten_router)
app.include_router(links_router)
app.include_router(bulk_router)

# ---------------------------------------------------------------------------
# Static files — serve the HTML/CSS/JS frontend
# IMPORTANT: These must be registered BEFORE redirect_router (/{code} catch-all)
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).parent / "static"

# Mount static assets (CSS, JS, images) at /static
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    """Serve the main single-page dashboard UI."""
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/login", include_in_schema=False)
async def serve_login() -> FileResponse:
    """Serve the login / register page."""
    return FileResponse(str(_STATIC_DIR / "login.html"))


@app.get("/analytics/{code}", include_in_schema=False)
async def serve_analytics(code: str) -> FileResponse:
    """Serve the analytics SPA for a given short code."""
    return FileResponse(str(_STATIC_DIR / "analytics.html"))


# ---------------------------------------------------------------------------
# Redirect catch-all — MUST be last so it doesn't shadow /login, /analytics
# ---------------------------------------------------------------------------

app.include_router(redirect_router)
