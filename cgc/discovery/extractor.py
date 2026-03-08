"""Hybrid triplet extraction combining patterns with ML extraction.

Supports two ML pipelines (selectable via `pipeline` parameter):

v2 pipeline (default, recommended):
    GLiNER2 (NER + relation extraction in one model)
    No spaCy, no char-to-token conversion, no domain routing needed
    Dependencies: gliner2

v1 pipeline (legacy):
    spaCy tokenization → GliNER v1 (NER) → char-to-token → GliREL (relations)
    + E5 domain routing for industry pack selection
    Dependencies: gliner, glirel, spacy, sentence-transformers

Both pipelines:
1. Detect content type (structured vs unstructured)
2. STRUCTURED: StructuredExtractor (hub-and-spoke)
3. UNSTRUCTURED:
   a. Pattern Matcher (50+ patterns, high precision)
   b. ML extraction (v1 or v2)
   c. Merge pattern + ML results
4. Deduplication & filtering
"""

from __future__ import annotations

import json
import logging

from cgc.core.triplet import Triplet, TripletCollection
from cgc.discovery.filters import deduplicate_triplets, filter_triplets
from cgc.discovery.patterns import PatternMatcher, extract_triplets_with_patterns

logger = logging.getLogger(__name__)


class HybridExtractor:
    """Hybrid triplet extraction combining patterns, NER, and relation extraction.

    Supports:
    - Pattern matching (50+ patterns, high precision)
    - v1: GliNER + GliREL + spaCy + E5 routing (legacy)
    - v2: GLiNER2 unified extraction (simplified)
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
        pipeline: str = "v2",
        gliner2_model: str = "fastino/gliner2-base-v1",
    ):
        self.pattern_matcher = PatternMatcher()
        self.use_gliner = use_gliner
        self.use_glirel = use_glirel
        self.use_routing = use_routing
        self.gliner_model = gliner_model
        self.gliner_threshold = gliner_threshold
        self.force_pack = force_pack
        self.pipeline = pipeline
        self.gliner2_model = gliner2_model

        # Lazy-initialized components
        self._unified = None
        self._router = None
        self._structured = None
        self._gliner2 = None

    def _get_unified(self):
        """Lazy-load the unified extractor (v1 pipeline)."""
        if self._unified is None:
            from cgc.discovery.unified import UnifiedExtractor
            self._unified = UnifiedExtractor(gliner_model=self.gliner_model)
        return self._unified

    def _get_router(self):
        """Lazy-load the domain router (v1 pipeline)."""
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

    def _get_gliner2(self):
        """Lazy-load the GLiNER2 extractor (v2 pipeline)."""
        if self._gliner2 is None:
            from cgc.discovery.gliner2 import create_gliner2_extractor
            self._gliner2 = create_gliner2_extractor(
                model_name=self.gliner2_model,
                entity_threshold=self.gliner_threshold,
                relation_threshold=self.gliner_threshold,
            )
        return self._gliner2

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

        # Step 2: ML extraction
        if self.pipeline == "v2":
            ml_triplets = self._extract_v2(text, domain)
        else:
            ml_triplets = self._extract_v1(text, domain)

        # Step 3: Merge pattern + ML results (patterns take priority)
        all_triplets = list(pattern_triplets) + ml_triplets

        # Step 4: Filter and deduplicate
        all_triplets = filter_triplets(all_triplets)
        all_triplets = deduplicate_triplets(all_triplets)

        return all_triplets

    def _extract_v1(self, text: str, domain: str | None = None) -> list[Triplet]:
        """V1 pipeline: spaCy + GliNER + GliREL + E5 domain routing."""
        ml_triplets: list[Triplet] = []

        if not (self.use_gliner or self.use_glirel):
            return ml_triplets

        entity_labels = None
        relation_labels = None

        # Domain routing (select industry pack labels)
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

        # Unified extraction (spaCy + GliNER + GliREL)
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
                ml_triplets = self._gliner_only_extract(text, entity_labels)
        elif self.use_gliner:
            ml_triplets = self._gliner_only_extract(text, entity_labels)

        return ml_triplets

    def _extract_v2(self, text: str, domain: str | None = None) -> list[Triplet]:
        """V2 pipeline: GLiNER2 unified extraction."""
        entity_labels = None
        relation_labels = None

        # If a domain/pack is forced, use its labels (still works without routing)
        pack_id = domain or self.force_pack
        if pack_id:
            try:
                from cgc.discovery.industry_packs import get_pack
                pack = get_pack(pack_id)
                if pack:
                    entity_labels = pack.entity_labels
                    relation_labels = pack.relation_labels
            except Exception as e:
                logger.warning(f"Industry pack lookup failed: {e}")

        try:
            gliner2 = self._get_gliner2()
            return gliner2.extract_triplets(
                text,
                entity_labels=entity_labels,
                relation_labels=relation_labels,
            )
        except Exception as e:
            logger.warning(f"GLiNER2 extraction failed: {e}")
            return []

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
_default_pipeline: str = "v2"


def get_default_extractor(pipeline: str | None = None) -> HybridExtractor:
    """Get or create the default hybrid extractor."""
    global _default_extractor, _default_pipeline
    use_pipeline = pipeline or _default_pipeline
    if _default_extractor is None or _default_extractor.pipeline != use_pipeline:
        _default_extractor = HybridExtractor(use_gliner=True, pipeline=use_pipeline)
        _default_pipeline = use_pipeline
    return _default_extractor


def extract_triplets(
    text: str,
    use_gliner: bool = True,
    domain: str | None = None,
    pipeline: str = "v1",
) -> list[Triplet]:
    """Extract triplets from text using hybrid approach.

    Args:
        text: Input text
        use_gliner: Whether to use ML extraction (slower but higher recall)
        domain: Force a specific industry pack ID
        pipeline: "v1" (GliNER+GliREL) or "v2" (GLiNER2)

    Returns:
        List of extracted triplets
    """
    if use_gliner:
        extractor = get_default_extractor(pipeline=pipeline)
        return extractor.extract_triplets(text, domain=domain)
    else:
        return extract_triplets_with_patterns(text)


def extract_triplets_batch(
    texts: list[str],
    use_gliner: bool = True,
    domain: str | None = None,
    pipeline: str = "v1",
) -> list[list[Triplet]]:
    """Extract triplets from multiple texts."""
    extractor = (
        get_default_extractor(pipeline=pipeline) if use_gliner
        else HybridExtractor(use_gliner=False)
    )
    return [extractor.extract_triplets(text, domain=domain) for text in texts]
