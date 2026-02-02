"""Relay API configuration from environment variables."""

from __future__ import annotations

import os


SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
PORT = int(os.environ.get("PORT", "8421"))
PRODUCT_ID = "cgc_standard"
