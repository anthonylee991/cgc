"""License tiers and data structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class Tier(Enum):
    """License tier levels."""

    TRIAL = "trial"
    FREE = "free"
    PRO = "pro"


TRIAL_DURATION_DAYS = 14
REVALIDATION_INTERVAL_DAYS = 7
GRACE_PERIOD_DAYS = 3


@dataclass
class License:
    """Local license record."""

    license_key: str
    tier: Tier
    trial_start: datetime | None = None
    last_validated: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "license_key": self.license_key,
            "tier": self.tier.value,
            "trial_start": self.trial_start.isoformat() if self.trial_start else None,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> License:
        return cls(
            license_key=data["license_key"],
            tier=Tier(data["tier"]),
            trial_start=datetime.fromisoformat(data["trial_start"]) if data.get("trial_start") else None,
            last_validated=datetime.fromisoformat(data["last_validated"]) if data.get("last_validated") else None,
        )

    @classmethod
    def new_trial(cls) -> License:
        """Create a fresh trial license."""
        now = datetime.now(timezone.utc)
        return cls(
            license_key="",
            tier=Tier.TRIAL,
            trial_start=now,
            last_validated=now,
        )
