"""GLiNER2-based unified extraction: entities + relations in a single model.

Replaces the spaCy + GliNER v1 + GliREL pipeline with a single GLiNER2 model
that handles both NER and relation extraction natively, eliminating the fragile
char-to-token conversion bridge.

Model options:
- fastino/gliner2-base-v1 (205M params) — default
- fastino/gliner2-large-v1 (340M params) — higher quality
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cgc.core.triplet import Triplet
from cgc.discovery.constraints import normalize_label, normalize_predicate, validate_relation
from cgc.discovery.filters import deduplicate_triplets, filter_entities, filter_triplets
from cgc.discovery.gliner import EntitySpan

logger = logging.getLogger(__name__)

# Default entity labels matching the v1 pipeline defaults
DEFAULT_ENTITY_LABELS = [
    "person", "organization", "location", "date", "money",
    "product", "technology", "role", "department", "project",
    "policy", "event", "company",
]

# Default relation labels matching the v1 pipeline defaults
DEFAULT_RELATION_LABELS = [
    "founded", "leads", "CEO of", "works at", "member of",
    "reports to", "manages", "headquartered in", "located in",
    "based in", "partner of", "acquired", "subsidiary of",
    "uses", "built with", "developed by", "provides",
    "governs", "applies to", "owns", "created by",
]


@dataclass
class GLiNER2ExtractionResult:
    """Result from the GLiNER2 extraction pipeline."""

    entities: list[EntitySpan] = field(default_factory=list)
    triplets: list[Triplet] = field(default_factory=list)
    text: str = ""
    pack_id: str | None = None


class GLiNER2Extractor:
    """Unified entity + relation extraction using GLiNER2.

    Single model replaces spaCy + GliNER v1 + GliREL:
    - No spaCy tokenization needed
    - No char-to-token conversion needed
    - Entity extraction and relation extraction in one model
    """

    DEFAULT_MODEL = "fastino/gliner2-base-v1"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        entity_threshold: float = 0.5,
        relation_threshold: float = 0.5,
    ):
        self.model_name = model_name
        self.entity_threshold = entity_threshold
        self.relation_threshold = relation_threshold
        self._model = None

    def _load_model(self):
        """Lazy load the GLiNER2 model."""
        if self._model is None:
            try:
                from gliner2 import GLiNER2
                self._model = GLiNER2.from_pretrained(self.model_name)
            except ImportError:
                raise ImportError(
                    "GLiNER2 not installed. Install with: pip install gliner2"
                )
        return self._model

    def extract_entities(
        self,
        text: str,
        labels: list[str] | None = None,
    ) -> list[EntitySpan]:
        """Extract named entities from text.

        Returns EntitySpan objects compatible with the v1 pipeline.
        """
        model = self._load_model()
        use_labels = labels or DEFAULT_ENTITY_LABELS

        raw = model.extract_entities(
            text,
            use_labels,
            include_confidence=True,
            include_spans=True,
        )

        spans = []
        entities_dict = raw.get("entities", {})
        for label, entries in entities_dict.items():
            for entry in entries:
                if isinstance(entry, dict):
                    entity_text = entry.get("text", "")
                    score = entry.get("confidence", 0.0)
                    start = entry.get("start", 0)
                    end = entry.get("end", 0)
                else:
                    # Basic mode (string only) — shouldn't happen with include_confidence=True
                    entity_text = str(entry)
                    score = 1.0
                    start = text.find(entity_text)
                    end = start + len(entity_text) if start >= 0 else 0

                if score < self.entity_threshold:
                    continue

                if len(entity_text) > 60:
                    continue

                spans.append(EntitySpan(
                    text=entity_text,
                    label=normalize_label(label),
                    start=start,
                    end=end,
                    score=score,
                ))

        # Deduplicate overlapping spans (keep higher score)
        spans = self._deduplicate_spans(spans)

        # Filter garbage entities
        spans = filter_entities(spans)

        spans.sort(key=lambda s: s.start)
        return spans

    def extract_relations(
        self,
        text: str,
        relation_labels: list[str] | None = None,
    ) -> list[Triplet]:
        """Extract relations directly as triplets.

        GLiNER2 extracts (head, relation, tail) tuples natively — no need for
        separate NER → char-to-token → relation extraction pipeline.
        """
        model = self._load_model()
        use_labels = relation_labels or DEFAULT_RELATION_LABELS

        raw = model.extract_relations(
            text,
            use_labels,
            include_confidence=True,
            include_spans=True,
        )

        triplets = []
        relations_dict = raw.get("relation_extraction", {})
        for relation_name, entries in relations_dict.items():
            for entry in entries:
                if isinstance(entry, tuple) and len(entry) == 2:
                    # Basic mode: ('head', 'tail')
                    head_text, tail_text = entry
                    head_score = 1.0
                    tail_score = 1.0
                    head_start = text.find(head_text)
                    head_end = head_start + len(head_text) if head_start >= 0 else 0
                    tail_start = text.find(tail_text)
                    tail_end = tail_start + len(tail_text) if tail_start >= 0 else 0
                elif isinstance(entry, dict):
                    # Rich mode with confidence + spans
                    head = entry.get("head", {})
                    tail = entry.get("tail", {})
                    head_text = head.get("text", "")
                    tail_text = tail.get("text", "")
                    head_score = head.get("confidence", 0.0)
                    tail_score = tail.get("confidence", 0.0)
                    head_start = head.get("start", 0)
                    head_end = head.get("end", 0)
                    tail_start = tail.get("start", 0)
                    tail_end = tail.get("end", 0)
                else:
                    continue

                if not head_text or not tail_text:
                    continue

                confidence = (head_score + tail_score) / 2
                if confidence < self.relation_threshold:
                    continue

                # Determine entity labels from entity extraction context
                head_label = "entity"
                tail_label = "entity"

                predicate = normalize_predicate(relation_name)

                triplet = Triplet(
                    subject=head_text,
                    predicate=predicate,
                    object=tail_text,
                    confidence=confidence,
                    source_span=(
                        min(head_start, tail_start),
                        max(head_end, tail_end),
                    ),
                    source_text=text[min(head_start, tail_start):max(head_end, tail_end)],
                    metadata={
                        "subject_label": head_label,
                        "object_label": tail_label,
                        "original_predicate": relation_name,
                        "method": "gliner2",
                    },
                )
                triplets.append(triplet)

        return triplets

    def extract(
        self,
        text: str,
        entity_labels: list[str] | None = None,
        relation_labels: list[str] | None = None,
    ) -> GLiNER2ExtractionResult:
        """Run the full extraction pipeline: entities + relations.

        Unlike v1, this runs both in a single model with no intermediate
        conversion steps.
        """
        result = GLiNER2ExtractionResult(text=text)

        # Step 1: Extract entities
        entities = self.extract_entities(text, labels=entity_labels)
        result.entities = entities

        # Build entity label lookup for enriching relation triplets
        entity_label_map: dict[str, str] = {}
        for ent in entities:
            entity_label_map[ent.text.lower()] = ent.label

        # Step 2: Extract relations
        triplets = self.extract_relations(text, relation_labels=relation_labels)

        # Enrich triplets with entity labels from step 1
        for triplet in triplets:
            sub_label = entity_label_map.get(triplet.subject.lower(), "entity")
            obj_label = entity_label_map.get(triplet.object.lower(), "entity")
            triplet.metadata["subject_label"] = sub_label
            triplet.metadata["object_label"] = obj_label
            triplet.subject_label = sub_label
            triplet.object_label = obj_label

        # Step 3: Semantic validation
        triplets = [
            t for t in triplets
            if validate_relation(
                t.metadata.get("subject_label", "entity"),
                t.metadata.get("original_predicate", t.predicate),
                t.metadata.get("object_label", "entity"),
            )
        ]

        # Step 4: Filter garbage and deduplicate
        triplets = filter_triplets(triplets)
        triplets = deduplicate_triplets(triplets)

        result.triplets = triplets
        return result

    def extract_triplets(
        self,
        text: str,
        entity_labels: list[str] | None = None,
        relation_labels: list[str] | None = None,
        **kwargs,
    ) -> list[Triplet]:
        """Convenience method returning just triplets.

        Drop-in compatible with UnifiedExtractor.extract_triplets().
        """
        result = self.extract(text, entity_labels, relation_labels)
        return result.triplets

    def _deduplicate_spans(self, spans: list[EntitySpan]) -> list[EntitySpan]:
        """Remove overlapping entity spans, keeping higher scores."""
        if not spans:
            return []

        sorted_spans = sorted(spans, key=lambda s: s.score, reverse=True)
        kept: list[EntitySpan] = []

        for span in sorted_spans:
            overlap = False
            for existing in kept:
                o_start = max(span.start, existing.start)
                o_end = min(span.end, existing.end)
                if o_start < o_end:
                    overlap_len = o_end - o_start
                    span_len = span.end - span.start
                    if span_len > 0 and overlap_len / span_len > 0.5:
                        overlap = True
                        break
            if not overlap:
                kept.append(span)

        return kept


class MockGLiNER2Extractor:
    """Fallback when GLiNER2 is not installed."""

    def __init__(self, **kwargs):
        pass

    def extract_entities(self, text: str, **kwargs) -> list[EntitySpan]:
        import re
        spans = []
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
            spans.append(EntitySpan(
                text=match.group(0),
                label="entity",
                start=match.start(),
                end=match.end(),
                score=0.5,
            ))
        return spans

    def extract_relations(self, text: str, **kwargs) -> list[Triplet]:
        return []

    def extract(self, text: str, **kwargs) -> GLiNER2ExtractionResult:
        entities = self.extract_entities(text)
        return GLiNER2ExtractionResult(entities=entities, text=text)

    def extract_triplets(self, text: str, **kwargs) -> list[Triplet]:
        return []


def create_gliner2_extractor(**kwargs) -> GLiNER2Extractor | MockGLiNER2Extractor:
    """Create a GLiNER2 extractor, falling back to mock if not available."""
    try:
        from gliner2 import GLiNER2  # noqa: F401
        return GLiNER2Extractor(**kwargs)
    except ImportError:
        logger.warning("GLiNER2 not installed. Using mock extractor.")
        return MockGLiNER2Extractor(**kwargs)
