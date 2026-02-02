"""Extraction endpoints for the relay API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel

from relay_api.src.middleware.auth import require_license
from relay_api.src.middleware.rate_limit import limiter, get_client_ip

router = APIRouter(prefix="/v1/extract")


def _serialize_triplets(triplets: list) -> list[dict]:
    """Serialize Triplet objects to dicts."""
    return [
        {
            "subject": t.subject,
            "predicate": t.predicate,
            "object": t.object,
            "confidence": t.confidence,
            "source_text": getattr(t, "source_text", None),
            "metadata": t.metadata,
        }
        for t in triplets
    ]


class TextExtractionRequest(BaseModel):
    text: str
    use_gliner: bool = True
    domain: str | None = None


class StructuredExtractionRequest(BaseModel):
    data: list[dict]


@router.post("/text")
async def extract_text(
    request: Request,
    body: TextExtractionRequest,
    license_key: str = Depends(require_license),
):
    """Extract triplets from text using hybrid pipeline.

    Rate limited to 30 req/min per license key.
    """
    limiter.check(f"extract:{license_key}", limit=30)

    from cgc.discovery.extractor import extract_triplets

    triplets = extract_triplets(
        body.text,
        use_gliner=body.use_gliner,
        domain=body.domain,
    )

    return {
        "triplets": _serialize_triplets(triplets),
        "count": len(triplets),
    }


@router.post("/structured")
async def extract_structured(
    request: Request,
    body: StructuredExtractionRequest,
    license_key: str = Depends(require_license),
):
    """Extract triplets from structured data using hub-and-spoke model.

    Rate limited to 30 req/min per license key.
    """
    limiter.check(f"extract:{license_key}", limit=30)

    from cgc.discovery.structured import StructuredExtractor

    extractor = StructuredExtractor()
    triplets = extractor.extract_triplets(body.data)

    return {
        "triplets": _serialize_triplets(triplets),
        "count": len(triplets),
    }


@router.post("/file")
async def extract_file(
    request: Request,
    file: UploadFile = File(...),
    domain: str | None = Form(default=None),
    use_gliner: str = Form(default="true"),
    license_key: str = Depends(require_license),
):
    """Extract triplets from an uploaded file.

    Supports CSV, JSON, XLS, XLSX (structured) and text, PDF, Markdown
    (unstructured). Rate limited to 20 req/min per license key.
    """
    limiter.check(f"extract_file:{license_key}", limit=20)

    from cgc.adapters.parsers import parse_file

    content = await file.read()
    parsed = parse_file(content, file.filename or "unknown")

    gliner_flag = use_gliner.lower() in ("true", "1", "yes")

    if parsed.rows:
        from cgc.discovery.structured import StructuredExtractor
        extractor = StructuredExtractor()
        triplets = extractor.extract_triplets(parsed.rows)
        file_type = "structured"
    else:
        from cgc.discovery.extractor import extract_triplets
        triplets = extract_triplets(parsed.text, use_gliner=gliner_flag, domain=domain)
        file_type = "unstructured"

    return {
        "triplets": _serialize_triplets(triplets),
        "count": len(triplets),
        "file_type": file_type,
        "filename": file.filename,
    }
