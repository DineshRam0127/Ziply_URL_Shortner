"""
routes/auth.py — Phase 4 Authentication endpoints.

Endpoints:
  POST /api/auth/register  — create a new user account (hashed password).
  POST /api/auth/login     — verify credentials, return a signed JWT.
  GET  /api/auth/me        — return the current user's info (requires token).
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from jose import JWTError, jwt
from passlib.context import CryptContext

import database
from models import RegisterRequest, LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Crypto / JWT config ───────────────────────────────────────────────────────

_SECRET_KEY: str = os.environ.get("JWT_SECRET", "ziply-dev-secret-change-in-prod")
_ALGORITHM: str = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MIN", "1440"))  # 24 h

# sha256_crypt: pure-Python, no external C library required, works with all
# passlib versions. In production you may swap to argon2 or bcrypt with a
# compatible library, but sha256_crypt is perfectly secure for this project.
_pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/form", auto_error=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException 401 on any failure."""
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_user_by_username(username: str, db_path: str | None = None) -> dict | None:
    with database.get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def _create_user(username: str, password_hash: str, db_path: str | None = None) -> int:
    """Insert a new user and return the new user ID."""
    with database.get_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
    return cursor.lastrowid


# ── FastAPI dependency — optional auth ────────────────────────────────────────

def get_current_user_id(token: str | None = Depends(_oauth2_scheme)) -> int | None:
    """
    Dependency that returns the user_id from a valid Bearer token,
    or None if no / invalid token is provided.
    """
    if not token:
        return None
    try:
        payload = _decode_token(token)
        return int(payload["sub"])
    except (HTTPException, KeyError, ValueError):
        return None


def require_auth(user_id: int | None = Depends(get_current_user_id)) -> int:
    """
    Dependency that enforces authentication.
    Returns the user_id on success; raises 401 if not authenticated.
    """
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest) -> TokenResponse:
    """
    Create a new user account and return a JWT so the user is
    immediately logged in after registration.
    """
    db_path = os.environ.get("DB_PATH")
    existing = _get_user_by_username(body.username, db_path)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' is already taken.",
        )
    password_hash = _hash_password(body.password)
    user_id = _create_user(body.username, password_hash, db_path)
    token = _create_access_token(user_id, body.username)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Verify credentials and return a signed JWT."""
    db_path = os.environ.get("DB_PATH")
    user = _get_user_by_username(body.username, db_path)
    if not user or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    token = _create_access_token(user["id"], user["username"])
    return TokenResponse(access_token=token)


@router.post("/login/form", response_model=TokenResponse, include_in_schema=False)
async def login_form(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """OAuth2 password form — used by the Swagger UI 'Authorize' dialog."""
    db_path = os.environ.get("DB_PATH")
    user = _get_user_by_username(form.username, db_path)
    if not user or not _verify_password(form.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    token = _create_access_token(user["id"], user["username"])
    return TokenResponse(access_token=token)


@router.get("/me")
async def me(user_id: int = Depends(require_auth)) -> dict:
    """Return the current authenticated user's info."""
    db_path = os.environ.get("DB_PATH")
    with database.get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}
