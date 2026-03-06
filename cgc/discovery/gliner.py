"""GliNER-based named entity recognition for triplet extraction.

Uses the GliNER model to identify named entities with support for:
- Label batching (4 domain batches, max 20 labels per call)
- Comprehensive extraction across all label categories
- Garbage entity filtering
- Label normalization
"""

from __future__ import annotations

from dataclasses import dataclass

from cgc.core.triplet import Triplet
from cgc.discovery.constraints import normalize_label
from cgc.discovery.filters import filter_entities

# --- Label batches (max ~10 per batch, max 20 per GliNER call) ---

LABEL_BATCHES: dict[str, list[str]] = {
    "core": [
        "person", "organization", "location", "date", "money",
        "product", "service", "project", "event", "document",
    ],
    "technical": [
        "technology", "software", "api", "database", "framework",
        "programming language", "platform", "tool", "library", "protocol",
    ],
    "business": [
        "company", "brand", "industry", "department", "role",
        "client", "customer", "supplier", "partner", "competitor",
    ],
    "financial": [
        "price", "budget", "revenue", "payment", "invoice",
        "transaction", "expense", "account", "contract", "deal",
    ],
}

# Flattened default labels (backward compat)
DEFAULT_LABELS = [
    "person", "organization", "location",
    "software", "programming language", "technology", "framework", "database",
    "preference", "setting", "value", "identifier", "project", "tool",
]


@dataclass
class EntitySpan:
    """A detected entity with its span."""

    text: str
    label: str
    start: int
    end: int
    score: float


class GliNERExtractor:
    """Extract entities using GliNER with batched label support.

    GliNER is a generalist model for named entity recognition that can
    recognize arbitrary entity types specified at inference time.
    """

    DEFAULT_MODEL = "urchade/gliner_medium-v2.1"
    MAX_LABELS_PER_CALL = 20
    MAX_ENTITY_LENGTH = 60

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        labels: list[str] | None = None,
        threshold: float = 0.5,
    ):
        self.model_name = model_name
        self.labels = labels or DEFAULT_LABELS
        self.threshold = threshold
        self._model = None

    def _load_model(self):
        """Lazy load the GliNER model."""
        if self._model is None:
            try:
                from gliner import GLiNER
                self._model = GLiNER.from_pretrained(self.model_name)
            except ImportError:
                raise ImportError(
                    "GliNER not installed. Install with: pip install gliner"
                )
        return self._model

    def extract_entities(
        self,
        text: str,
        labels: list[str] | None = None,
        threshold: float | None = None,
    ) -> list[EntitySpan]:
        """Extract named entities from text with specified labels."""
        model = self._load_model()
        use_labels = labels or self.labels
        use_threshold = threshold or self.threshold

        # Batch labels if needed (GliNER max ~20 per call)
        if len(use_labels) <= self.MAX_LABELS_PER_CALL:
            raw = model.predict_entities(text, use_labels, threshold=use_threshold)
            spans = self._convert_entities(raw)
        else:
            spans = []
            for i in range(0, len(use_labels), self.MAX_LABELS_PER_CALL):
                batch = use_labels[i:i + self.MAX_LABELS_PER_CALL]
                raw = model.predict_entities(text, batch, threshold=use_threshold)
                spans.extend(self._convert_entities(raw))

        # Deduplicate overlapping spans
        spans = self._deduplicate_spans(spans)

        # Filter garbage entities
        spans = filter_entities(spans)

        # Normalize labels
        for span in spans:
            span.label = normalize_label(span.label)

        spans.sort(key=lambda s: s.start)
        return spans

    def extract_comprehensive(
        self,
        text: str,
        threshold: float | None = None,
    ) -> list[EntitySpan]:
        """Run all 4 label batches for comprehensive entity extraction.

        Use this for domain-agnostic extraction when no industry pack is selected.
        """
        use_threshold = threshold or self.threshold
        all_spans: list[EntitySpan] = []

        model = self._load_model()
        for batch_name, batch_labels in LABEL_BATCHES.items():
            raw = model.predict_entities(text, batch_labels, threshold=use_threshold)
            all_spans.extend(self._convert_entities(raw))

        # Deduplicate, filter, normalize
        all_spans = self._deduplicate_spans(all_spans)
        all_spans = filter_entities(all_spans)
        for span in all_spans:
            span.label = normalize_label(span.label)

        all_spans.sort(key=lambda s: s.start)
        return all_spans

    def extract_with_labels(
        self,
        text: str,
        labels: list[str],
        threshold: float | None = None,
    ) -> list[EntitySpan]:
        """Extract with specific labels (for domain routing)."""
        return self.extract_entities(text, labels=labels, threshold=threshold)

    def extract_triplets(self, text: str) -> list[Triplet]:
        """Extract triplets by pairing entities.

        For each pair of entities (e1, e2) where e1 appears before e2:
        - Subject = e1.text
        - Predicate = text between e1 and e2 (cleaned)
        - Object = e2.text
        - Confidence = average of entity scores
        """
        entities = self.extract_entities(text)
        triplets = []

        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                gap = e2.start - e1.end
                if gap > 100:
                    continue

                predicate = text[e1.end:e2.start].strip()
                predicate = self._clean_predicate(predicate)

                if not predicate or len(predicate) > 50:
                    continue

                triplet = Triplet(
                    subject=e1.text,
                    predicate=predicate,
                    object=e2.text,
                    confidence=(e1.score + e2.score) / 2,
                    source_span=(e1.start, e2.end),
                    source_text=text[e1.start:e2.end],
                    metadata={
                        "subject_label": e1.label,
                        "object_label": e2.label,
                        "method": "gliner",
                    },
                )
                triplets.append(triplet)

        return triplets

    def _convert_entities(self, raw_entities: list[dict]) -> list[EntitySpan]:
        """Convert raw GliNER output to EntitySpan objects."""
        spans = []
        for entity in raw_entities:
            text = entity["text"]
            if len(text) > self.MAX_ENTITY_LENGTH:
                continue
            spans.append(EntitySpan(
                text=text,
                label=entity["label"],
                start=entity["start"],
                end=entity["end"],
                score=entity["score"],
            ))
        return spans

    def _deduplicate_spans(self, spans: list[EntitySpan]) -> list[EntitySpan]:
        """Remove overlapping entity spans, keeping higher scores."""
        if not spans:
            return []

        # Sort by score descending
        sorted_spans = sorted(spans, key=lambda s: s.score, reverse=True)
        kept: list[EntitySpan] = []

        for span in sorted_spans:
            overlap = False
            for existing in kept:
                # Check character overlap > 50%
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

    def _clean_predicate(self, predicate: str) -> str:
        """Clean extracted predicate text."""
        predicate = predicate.strip(" .,;:!?-")
        filler_start = ["and", "or", "but", "the", "a", "an"]
        filler_end = ["the", "a", "an"]

        words = predicate.split()
        if words and words[0].lower() in filler_start:
            words = words[1:]
        if words and words[-1].lower() in filler_end:
            words = words[:-1]

        return " ".join(words)


class MockGliNERExtractor:
    """Mock extractor for when GliNER is not available."""

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

    def extract_comprehensive(self, text: str, **kwargs) -> list[EntitySpan]:
        return self.extract_entities(text)

    def extract_with_labels(self, text: str, labels: list[str], **kwargs) -> list[EntitySpan]:
        return self.extract_entities(text)

    def extract_triplets(self, text: str) -> list[Triplet]:
        entities = self.extract_entities(text)
        triplets = []
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                gap = e2.start - e1.end
                if gap > 50 or gap < 2:
                    continue
                predicate = text[e1.end:e2.start].strip(" .,;:!?")
                if not predicate or len(predicate) > 30:
                    continue
                triplets.append(Triplet(
                    subject=e1.text, predicate=predicate, object=e2.text,
                    confidence=0.4,
                    source_span=(e1.start, e2.end),
                    source_text=text[e1.start:e2.end],
                    metadata={"method": "mock_gliner"},
                ))
        return triplets


def create_gliner_extractor(**kwargs) -> GliNERExtractor | MockGliNERExtractor:
    """Create a GliNER extractor, falling back to mock if not available."""
    try:
        from gliner import GLiNER  # noqa: F401
        return GliNERExtractor(**kwargs)
    except ImportError:
        return MockGliNERExtractor(**kwargs)
