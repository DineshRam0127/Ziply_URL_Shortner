"""
routes/bulk.py — POST /api/bulk  (Phase 2)

Accepts a multipart/form-data CSV file upload.
Each row must contain at least one column: the destination URL.
Optionally a second column can be an alias.
Returns 207 Multi-Status with per-row results.

CSV format (no header required, auto-detected):
    https://example.com/page1
    https://example.com/page2,my-alias
    https://example.com/page3,another-alias,14
                                             ^ optional: expires_days

Rules:
  - Max 500 rows per upload.
  - Malformed / blank rows are reported as errors, not skipped silently.
  - The response always uses HTTP 207 so callers can inspect per-row status.
"""

import csv
import io
import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

import shortener
from models import ShortenResponse
from routes.auth import require_auth

router = APIRouter()

_MAX_ROWS = 500


@router.post("/api/bulk", tags=["bulk"], status_code=207)
async def bulk_shorten(
    request: Request,
    file: UploadFile = File(...),
    user_id: int = Depends(require_auth),
) -> JSONResponse:
    """
    Shorten multiple URLs from a CSV file upload.

    **CSV format** (no header row needed):
    ```
    https://example.com/page1
    https://example.com/page2,my-alias
    https://example.com/page3,another-alias,30
    ```
    Columns: `url` (required), `alias` (optional), `expires_days` (optional).

    Returns a 207 Multi-Status JSON array:
    ```json
    [
      {"row": 1, "status": 201, "short_url": "http://....", "code": "abc123"},
      {"row": 2, "status": 409, "error": "Alias already taken."}
    ]
    ```
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    content_type = file.content_type or ""
    # Accept text/csv, application/csv, text/plain (some browsers send the latter)
    allowed = ("text/csv", "application/csv", "text/plain", "application/octet-stream")
    if not any(ct in content_type for ct in allowed):
        # Be lenient — also allow if filename ends with .csv
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=415,
                detail="Only CSV files are accepted (Content-Type: text/csv).",
            )

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")  # handles BOM from Excel
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1", errors="replace")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    # Auto-detect and skip a header row
    if rows and rows[0] and rows[0][0].strip().lower() in ("url", "destination", "link"):
        rows = rows[1:]

    if len(rows) > _MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"CSV exceeds {_MAX_ROWS}-row limit. Upload {len(rows)} rows in smaller batches.",
        )

    db_path = os.environ.get("DB_PATH")
    base_url = str(request.base_url).rstrip("/")
    results = []

    for i, cols in enumerate(rows, start=1):
        # Strip empty columns
        cols = [c.strip() for c in cols if c.strip()]
        if not cols:
            results.append({"row": i, "status": 400, "error": "Empty row — skipped."})
            continue

        url = cols[0]
        alias = cols[1] if len(cols) > 1 else None
        expires_days_raw = cols[2] if len(cols) > 2 else None

        # Validate URL scheme
        if not (url.startswith("http://") or url.startswith("https://")):
            results.append({
                "row": i, "status": 422,
                "error": f"Invalid URL '{url}': must start with http:// or https://",
            })
            continue

        # Validate alias
        if alias and not __import__("re").match(r"^[A-Za-z0-9_-]{1,30}$", alias):
            results.append({
                "row": i, "status": 422,
                "error": f"Alias '{alias}' is invalid. Use 1–30 letters/digits/- or _.",
            })
            continue

        # Parse optional expiry
        expires_days = None
        if expires_days_raw:
            try:
                expires_days = int(expires_days_raw)
                if expires_days < 1 or expires_days > 3650:
                    raise ValueError()
            except ValueError:
                results.append({
                    "row": i, "status": 422,
                    "error": f"expires_days '{expires_days_raw}' must be an integer between 1 and 3650.",
                })
                continue

        try:
            code = shortener.create_short_code(
                url,
                alias=alias or None,
                expires_days=expires_days,
                user_id=user_id,
                db_path=db_path,
            )
            results.append({
                "row": i,
                "status": 201,
                "code": code,
                "short_url": f"{base_url}/{code}",
                "original_url": url,
                "qr_url": f"{base_url}/api/links/{code}/qr",
            })
        except ValueError as exc:
            results.append({"row": i, "status": 409, "error": str(exc)})
        except RuntimeError as exc:
            results.append({"row": i, "status": 500, "error": str(exc)})

    return JSONResponse(content=results, status_code=207)
