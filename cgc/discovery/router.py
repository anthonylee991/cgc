"""E5 embedding-based domain router for industry pack selection.

Embeds document text and compares against cached industry pack descriptions
to select the most appropriate extraction label set.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from cgc.discovery.industry_packs import (
    IndustryPack,
    GENERAL_BUSINESS,
    ALL_PACKS,
    PACK_REGISTRY,
    get_pack,
)

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """Result from domain routing."""

    pack: IndustryPack
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)


class DomainRouter:
    """E5 embedding-based domain router.

    At init: lazily embeds all industry pack descriptions (cached).
    For each document: embeds first N chars, cosine similarity, selects best pack.
    """

    MODEL_NAME = "intfloat/e5-small-v2"  # 384 dimensions
    THRESHOLD = 0.3
    MAX_ROUTING_CHARS = 2000

    def __init__(self, threshold: float = THRESHOLD):
        self.threshold = threshold
        self._model = None
        self._pack_embeddings: dict[str, Any] | None = None

    def _load_model(self):
        """Lazy load the sentence-transformers E5 model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.MODEL_NAME)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    def _embed_packs(self):
        """Embed all industry pack descriptions (one-time, cached)."""
        if self._pack_embeddings is not None:
            return self._pack_embeddings

        model = self._load_model()
        self._pack_embeddings = {}

        for pack in ALL_PACKS:
            # Build pack text from description + examples
            pack_text = pack.description
            if pack.examples:
                pack_text += " " + " ".join(pack.examples)

            # E5 requires "passage: " prefix for documents
            embedding = model.encode(f"passage: {pack_text}", normalize_embeddings=True)
            self._pack_embeddings[pack.id] = embedding

        return self._pack_embeddings

    def route(self, text: str, title: str | None = None) -> RouteResult:
        """Route text to the best industry pack.

        1. Take first MAX_ROUTING_CHARS of text
        2. Embed with 'query: ' prefix (E5 requirement)
        3. Cosine similarity against cached pack embeddings
        4. Return best match if >= threshold, else GENERAL_BUSINESS
        """
        model = self._load_model()
        pack_embeddings = self._embed_packs()

        # Build query text
        query_text = text[:self.MAX_ROUTING_CHARS]
        if title:
            query_text = f"{title}. {query_text}"

        # Embed with "query: " prefix (E5 model requirement)
        query_embedding = model.encode(f"query: {query_text}", normalize_embeddings=True)

        # Compute cosine similarity against all packs
        scores: dict[str, float] = {}
        best_pack_id = GENERAL_BUSINESS.id
        best_score = -1.0

        for pack_id, pack_embedding in pack_embeddings.items():
            similarity = float(np.dot(query_embedding, pack_embedding))
            scores[pack_id] = similarity
            if similarity > best_score:
                best_score = similarity
                best_pack_id = pack_id

        # Apply threshold
        if best_score < self.threshold:
            return RouteResult(
                pack=GENERAL_BUSINESS,
                confidence=scores.get(GENERAL_BUSINESS.id, 0.0),
                scores=scores,
            )

        selected_pack = PACK_REGISTRY.get(best_pack_id, GENERAL_BUSINESS)
        return RouteResult(
            pack=selected_pack,
            confidence=best_score,
            scores=scores,
        )

    def get_pack_by_id(self, pack_id: str) -> IndustryPack | None:
        """Get a specific pack by ID."""
        return get_pack(pack_id)


class MockDomainRouter:
    """Fallback when sentence-transformers not installed.

    Always returns GENERAL_BUSINESS pack.
    """

    def __init__(self, **kwargs):
        pass

    def route(self, text: str, title: str | None = None) -> RouteResult:
        return RouteResult(
            pack=GENERAL_BUSINESS,
            confidence=1.0,
            scores={GENERAL_BUSINESS.id: 1.0},
        )

    def get_pack_by_id(self, pack_id: str) -> IndustryPack | None:
        return get_pack(pack_id)


def create_router(**kwargs) -> DomainRouter | MockDomainRouter:
    """Create a domain router, falling back to mock if dependencies unavailable."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        return DomainRouter(**kwargs)
    except ImportError:
        return MockDomainRouter(**kwargs)
