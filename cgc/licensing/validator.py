"""License validation against the CGC relay API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from cgc.licensing.store import LicenseStore
from cgc.licensing.tier import (
    GRACE_PERIOD_DAYS,
    REVALIDATION_INTERVAL_DAYS,
    TRIAL_DURATION_DAYS,
    License,
    Tier,
)

RELAY_URL = "https://cgc-production.up.railway.app"


class LicenseError(Exception):
    """Raised when a license operation fails."""


def validate_token(key: str) -> bool:
    """Validate a license key against the relay API.

    Returns True if the key is valid for cgc_standard.
    """
    try:
        resp = httpx.post(
            f"{RELAY_URL}/v1/license/validate",
            json={"key": key},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json().get("valid", False)
        return False
    except httpx.HTTPError:
        return False


def activate(key: str, store: LicenseStore) -> bool:
    """Activate a license key. Validates with relay and saves locally.

    Returns True on success, raises LicenseError on failure.
    """
    if not validate_token(key):
        raise LicenseError("Invalid license key. Please check your key and try again.")

    now = datetime.now(timezone.utc)
    license = License(
        license_key=key,
        tier=Tier.PRO,
        trial_start=None,
        last_validated=now,
    )
    store.save(license)
    return True


def deactivate(store: LicenseStore) -> None:
    """Remove the stored license, revert to free tier."""
    store.clear()


def get_tier(store: LicenseStore) -> Tier:
    """Determine the current license tier.

    - If no license stored, create a trial.
    - If trial, check expiration.
    - If pro, check revalidation window + grace period.
    """
    license = store.load()
    now = datetime.now(timezone.utc)

    # First run: create trial
    if license is None:
        trial = License.new_trial()
        store.save(trial)
        return Tier.TRIAL

    # Trial tier: check if expired
    if license.tier == Tier.TRIAL:
        if license.trial_start:
            elapsed = now - license.trial_start
            if elapsed > timedelta(days=TRIAL_DURATION_DAYS):
                license.tier = Tier.FREE
                store.save(license)
                return Tier.FREE
        return Tier.TRIAL

    # Free tier: nothing to check
    if license.tier == Tier.FREE:
        return Tier.FREE

    # Pro tier: check revalidation
    if license.tier == Tier.PRO and license.last_validated:
        since_validated = now - license.last_validated
        revalidation_deadline = timedelta(days=REVALIDATION_INTERVAL_DAYS)
        grace_deadline = timedelta(days=REVALIDATION_INTERVAL_DAYS + GRACE_PERIOD_DAYS)

        if since_validated > revalidation_deadline:
            # Try to revalidate
            if validate_token(license.license_key):
                license.last_validated = now
                store.save(license)
                return Tier.PRO

            # Within grace period: still Pro
            if since_validated <= grace_deadline:
                return Tier.PRO

            # Grace period expired: downgrade
            license.tier = Tier.FREE
            store.save(license)
            return Tier.FREE

    return license.tier


def get_license_key(store: LicenseStore) -> str | None:
    """Get the stored license key, or None if not activated."""
    license = store.load()
    if license and license.license_key:
        return license.license_key
    return None


def require_extraction(store: LicenseStore) -> None:
    """Check that the current tier allows extraction.

    Raises LicenseError if extraction is not available.
    """
    tier = get_tier(store)
    if tier == Tier.FREE:
        raise LicenseError(
            "Graph extraction requires CGC Pro.\n"
            "Run 'cgc activate <license-key>' to activate your license.\n"
            "Visit https://cgc.dev to purchase a license."
        )
