"""License key authentication middleware for relay API."""

from __future__ import annotations

import time

import httpx
from fastapi import Request, HTTPException

from relay_api.src.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, PRODUCT_ID

# In-memory cache: license_key -> (valid: bool, expires_at: float)
_license_cache: dict[str, tuple[bool, float]] = {}
CACHE_TTL = 300  # 5 minutes


def _validate_with_supabase(key: str) -> bool:
    """Validate a license key against Supabase purchases table."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return False

    try:
        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/purchases",
            params={
                "token": f"eq.{key}",
                "product_id": f"eq.{PRODUCT_ID}",
                "select": "id",
            },
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return len(data) > 0
        return False
    except httpx.HTTPError:
        return False


def validate_license_key(key: str) -> bool:
    """Validate a license key with caching."""
    now = time.time()

    # Check cache
    if key in _license_cache:
        valid, expires_at = _license_cache[key]
        if now < expires_at:
            return valid

    # Validate with Supabase
    valid = _validate_with_supabase(key)
    _license_cache[key] = (valid, now + CACHE_TTL)
    return valid


async def require_license(request: Request) -> str:
    """FastAPI dependency: require a valid license key.

    Returns the license key on success, raises 401 on failure.
    """
    license_key = request.headers.get("X-License-Key")
    if not license_key:
        raise HTTPException(status_code=401, detail="Missing X-License-Key header")

    if not validate_license_key(license_key):
        raise HTTPException(status_code=401, detail="Invalid license key")

    return license_key
