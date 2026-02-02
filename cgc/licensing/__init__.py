"""CGC License Management."""

from cgc.licensing.store import LicenseStore
from cgc.licensing.tier import License, Tier, TRIAL_DURATION_DAYS
from cgc.licensing.validator import (
    activate,
    deactivate,
    get_license_key,
    get_tier,
    require_extraction,
    validate_token,
    LicenseError,
)

__all__ = [
    "License",
    "LicenseError",
    "LicenseStore",
    "Tier",
    "TRIAL_DURATION_DAYS",
    "activate",
    "deactivate",
    "get_license_key",
    "get_tier",
    "require_extraction",
    "validate_token",
]
