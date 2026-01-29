"""GliNER-based named entity recognition for triplet extraction.

Uses the GliNER model to identify named entities, then forms triplets
from entity pairs based on text between them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cgc.core.triplet import Triplet


# Default entity labels for extraction
DEFAULT_LABELS = [
    # Traditional NER
    "person",
    "organization",
    "location",
    # Technical
    "software",
    "programming language",
    "technology",
    "framework",
    "database",
    # Conversational
    "preference",
    "setting",
    "value",
    "identifier",
    "project",
    "tool",
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
    """Extract triplets using GliNER for named entity recognition.

    GliNER is a generalist model for named entity recognition that can
    recognize arbitrary entity types specified at inference time.
    """

    def __init__(
        self,
        model_name: str = "urchade/gliner_small-v2.1",
        labels: list[str] | None = None,
        threshold: float = 0.5,
    ):
        """Initialize GliNER extractor.

        Args:
            model_name: HuggingFace model name or local path
            labels: Entity labels to recognize
            threshold: Minimum confidence threshold
        """
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

    def extract_entities(self, text: str) -> list[EntitySpan]:
        """Extract named entities from text."""
        model = self._load_model()

        # Run inference
        entities = model.predict_entities(
            text,
            self.labels,
            threshold=self.threshold,
        )

        # Convert to EntitySpan objects
        spans = []
        for entity in entities:
            spans.append(EntitySpan(
                text=entity["text"],
                label=entity["label"],
                start=entity["start"],
                end=entity["end"],
                score=entity["score"],
            ))

        # Sort by position
        spans.sort(key=lambda s: s.start)

        return spans

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
                # Only pair entities that are close together
                gap = e2.start - e1.end
                if gap > 100:  # Skip if entities are too far apart
                    continue

                # Extract predicate from text between entities
                predicate = text[e1.end:e2.start].strip()

                # Clean predicate
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

    def _clean_predicate(self, predicate: str) -> str:
        """Clean extracted predicate text."""
        # Remove leading/trailing punctuation
        predicate = predicate.strip(" .,;:!?-")

        # Remove common filler words at boundaries
        filler_start = ["and", "or", "but", "the", "a", "an"]
        filler_end = ["the", "a", "an"]

        words = predicate.split()
        if words and words[0].lower() in filler_start:
            words = words[1:]
        if words and words[-1].lower() in filler_end:
            words = words[:-1]

        return " ".join(words)


class MockGliNERExtractor:
    """Mock extractor for when GliNER is not available.

    Uses simple regex-based extraction as a fallback.
    """

    def __init__(self, **kwargs):
        pass

    def extract_entities(self, text: str) -> list[EntitySpan]:
        """Extract entities using simple patterns."""
        import re

        spans = []

        # Find capitalized words (likely proper nouns)
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
            spans.append(EntitySpan(
                text=match.group(0),
                label="entity",
                start=match.start(),
                end=match.end(),
                score=0.5,
            ))

        return spans

    def extract_triplets(self, text: str) -> list[Triplet]:
        """Extract triplets using simple patterns."""
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
                    subject=e1.text,
                    predicate=predicate,
                    object=e2.text,
                    confidence=0.4,
                    source_span=(e1.start, e2.end),
                    source_text=text[e1.start:e2.end],
                    metadata={"method": "mock_gliner"},
                ))

        return triplets


def create_gliner_extractor(**kwargs) -> GliNERExtractor | MockGliNERExtractor:
    """Create a GliNER extractor, falling back to mock if not available."""
    try:
        from gliner import GLiNER
        return GliNERExtractor(**kwargs)
    except ImportError:
        return MockGliNERExtractor(**kwargs)
