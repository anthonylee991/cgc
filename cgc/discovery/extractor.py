"""Hybrid triplet extraction combining patterns, GliNER, GliREL, and domain routing.

v0.2.0 pipeline:
1. Detect content type (structured vs unstructured)
2. STRUCTURED: StructuredExtractor (hub-and-spoke)
3. UNSTRUCTURED:
   a. Pattern Matcher (50+ patterns, high precision)
   b. Domain Router (select industry pack via E5 embeddings)
   c. Unified Extractor (spaCy + GliNER + GliREL)
   d. Merge pattern + unified results
4. Deduplication & filtering
"""

from __future__ import annotations

import json
import logging
from typing import Any

from cgc.core.triplet import Triplet, TripletCollection
from cgc.discovery.patterns import PatternMatcher, extract_triplets_with_patterns
from cgc.discovery.filters import deduplicate_triplets, filter_triplets

logger = logging.getLogger(__name__)


class HybridExtractor:
    """Hybrid triplet extraction combining patterns, NER, and relation extraction.

    Supports:
    - Pattern matching (50+ patterns, high precision)
    - GliNER entity extraction (medium model, batched labels)
    - GliREL relation extraction (type-constrained)
    - E5 embedding domain routing (11 industry packs)
    - Structured data extraction (hub-and-spoke)
    """

    def __init__(
        self,
        use_gliner: bool = True,
        use_glirel: bool = True,
        use_routing: bool = True,
        gliner_model: str = "urchade/gliner_medium-v2.1",
        gliner_threshold: float = 0.5,
        force_pack: str | None = None,
    ):
        self.pattern_matcher = PatternMatcher()
        self.use_gliner = use_gliner
        self.use_glirel = use_glirel
        self.use_routing = use_routing
        self.gliner_model = gliner_model
        self.gliner_threshold = gliner_threshold
        self.force_pack = force_pack

        # Lazy-initialized components
        self._unified = None
        self._router = None
        self._structured = None

    def _get_unified(self):
        """Lazy-load the unified extractor."""
        if self._unified is None:
            from cgc.discovery.unified import UnifiedExtractor
            self._unified = UnifiedExtractor(gliner_model=self.gliner_model)
        return self._unified

    def _get_router(self):
        """Lazy-load the domain router."""
        if self._router is None:
            from cgc.discovery.router import create_router
            self._router = create_router()
        return self._router

    def _get_structured(self):
        """Lazy-load the structured extractor."""
        if self._structured is None:
            from cgc.discovery.structured import StructuredExtractor
            self._structured = StructuredExtractor()
        return self._structured

    def extract_triplets(self, text: str, domain: str | None = None) -> list[Triplet]:
        """Extract triplets using the full hybrid pipeline.

        Args:
            text: Input text (or JSON string for structured data)
            domain: Force a specific industry pack ID

        Returns:
            List of extracted triplets, deduplicated and filtered
        """
        # Auto-detect structured data
        if self._is_structured(text):
            try:
                data = json.loads(text)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    return self.extract_from_structured(data)
            except (json.JSONDecodeError, IndexError):
                pass

        # --- Unstructured pipeline ---

        # Step 1: Pattern matching (high precision, always runs)
        pattern_triplets = self.pattern_matcher.extract_triplets(text)

        # Step 2: ML extraction (if enabled)
        ml_triplets: list[Triplet] = []

        if self.use_gliner or self.use_glirel:
            entity_labels = None
            relation_labels = None

            # Step 2a: Domain routing (select industry pack labels)
            pack_id = domain or self.force_pack
            if self.use_routing or pack_id:
                try:
                    if pack_id:
                        from cgc.discovery.industry_packs import get_pack
                        pack = get_pack(pack_id)
                    else:
                        router = self._get_router()
                        route_result = router.route(text)
                        pack = route_result.pack

                    if pack:
                        entity_labels = pack.entity_labels
                        relation_labels = pack.relation_labels
                except Exception as e:
                    logger.warning(f"Domain routing failed: {e}")

            # Step 2b: Unified extraction (spaCy + GliNER + GliREL)
            if self.use_glirel:
                try:
                    unified = self._get_unified()
                    ml_triplets = unified.extract_triplets(
                        text,
                        entity_labels=entity_labels,
                        relation_labels=relation_labels,
                    )
                except Exception as e:
                    logger.warning(f"Unified extraction failed: {e}")
                    # Fallback to GliNER-only
                    ml_triplets = self._gliner_only_extract(text, entity_labels)
            elif self.use_gliner:
                ml_triplets = self._gliner_only_extract(text, entity_labels)

        # Step 3: Merge pattern + ML results (patterns take priority)
        all_triplets = list(pattern_triplets) + ml_triplets

        # Step 4: Filter and deduplicate
        all_triplets = filter_triplets(all_triplets)
        all_triplets = deduplicate_triplets(all_triplets)

        return all_triplets

    def extract_from_structured(self, data: list[dict]) -> list[Triplet]:
        """Extract triplets from structured data (CSV rows, JSON objects)."""
        structured = self._get_structured()
        triplets = structured.extract_triplets(data)
        return filter_triplets(triplets)

    def extract_to_collection(self, text: str) -> TripletCollection:
        """Extract triplets into a collection."""
        collection = TripletCollection()
        triplets = self.extract_triplets(text)
        collection.add_all(triplets)
        return collection

    def _gliner_only_extract(
        self,
        text: str,
        entity_labels: list[str] | None = None,
    ) -> list[Triplet]:
        """Fallback: GliNER entity-pairing without GliREL."""
        try:
            from cgc.discovery.gliner import create_gliner_extractor
            gliner = create_gliner_extractor(
                model_name=self.gliner_model,
                threshold=self.gliner_threshold,
            )
            if entity_labels:
                gliner.labels = entity_labels
            return gliner.extract_triplets(text)
        except Exception as e:
            logger.warning(f"GliNER extraction failed: {e}")
            return []

    def _is_structured(self, text: str) -> bool:
        """Check if text looks like structured JSON data."""
        stripped = text.strip()
        return stripped.startswith("[") and stripped.endswith("]")


# --- Module-level convenience functions (backward compatible) ---

_default_extractor: HybridExtractor | None = None


def get_default_extractor() -> HybridExtractor:
    """Get or create the default hybrid extractor."""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = HybridExtractor(use_gliner=True)
    return _default_extractor


def extract_triplets(
    text: str,
    use_gliner: bool = True,
    domain: str | None = None,
) -> list[Triplet]:
    """Extract triplets from text using hybrid approach.

    Args:
        text: Input text
        use_gliner: Whether to use GliNER (slower but higher recall)
        domain: Force a specific industry pack ID

    Returns:
        List of extracted triplets
    """
    if use_gliner:
        extractor = get_default_extractor()
        return extractor.extract_triplets(text, domain=domain)
    else:
        return extract_triplets_with_patterns(text)


def extract_triplets_batch(
    texts: list[str],
    use_gliner: bool = True,
    domain: str | None = None,
) -> list[list[Triplet]]:
    """Extract triplets from multiple texts."""
    extractor = get_default_extractor() if use_gliner else HybridExtractor(use_gliner=False)
    return [extractor.extract_triplets(text, domain=domain) for text in texts]
