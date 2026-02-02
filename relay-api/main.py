"""CGC Relay API entry point for Railway/Railpack.

This file exists at the relay-api root so Railway's auto-detection
can find it. It imports and runs the FastAPI app.
"""

import uvicorn

from src.main import app  # noqa: F401 - app is used by uvicorn

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "8421"))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port)
