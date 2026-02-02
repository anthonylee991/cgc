"""CGC Relay API - Cloud extraction service.

Provides license-gated graph extraction as a service.
Deployed to Railway, validates licenses against Supabase.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from relay_api.src.routes.health import router as health_router
from relay_api.src.routes.license import router as license_router
from relay_api.src.routes.extract import router as extract_router

app = FastAPI(
    title="CGC Relay API",
    description="Cloud extraction service for Context Graph Connector",
    version="0.1.0",
)

# CORS: allow desktop apps (no origin) and configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-License-Key"],
)

# Mount routes
app.include_router(health_router)
app.include_router(license_router)
app.include_router(extract_router)


@app.get("/")
async def root():
    return {
        "service": "cgc-relay",
        "version": "0.1.0",
        "endpoints": [
            "GET  /health",
            "POST /v1/license/validate",
            "POST /v1/extract/text",
            "POST /v1/extract/file",
            "POST /v1/extract/structured",
        ],
    }


def main():
    """Run the relay API server."""
    import uvicorn
    from relay_api.src.config import PORT

    uvicorn.run(
        "relay_api.src.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
