"""License validation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from relay_api.src.middleware.auth import validate_license_key
from relay_api.src.middleware.rate_limit import limiter, get_client_ip

router = APIRouter(prefix="/v1/license")


class ValidateRequest(BaseModel):
    key: str


@router.post("/validate")
async def validate(request: Request, body: ValidateRequest):
    """Validate a license key against Supabase.

    Public endpoint (no auth required). Rate limited to 5 req/min.
    """
    ip = get_client_ip(request)
    limiter.check(f"license:{ip}", limit=5)

    valid = validate_license_key(body.key)
    return {"valid": valid}
