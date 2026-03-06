"""GliREL-based relation extraction.

Uses the GliREL model to extract relations between entities identified by GliNER.
Requires spaCy Doc for char-to-token position conversion.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from cgc.core.triplet import Triplet
from cgc.discovery.constraints import normalize_predicate, validate_relation
from cgc.discovery.gliner import EntitySpan

logger = logging.getLogger(__name__)

# Default relation labels for extraction
DEFAULT_RELATION_LABELS = [
    "founded", "leads", "CEO of", "works at", "member of",
    "reports to", "manages", "headquartered in", "located in",
    "based in", "partner of", "acquired", "subsidiary of",
    "uses", "built with", "developed by", "provides",
    "governs", "applies to", "owns", "created by",
]


@dataclass
class RelationSpan:
    """A detected relation between two entities."""

    head_text: str
    head_label: str
    tail_text: str
    tail_label: str
    relation: str
    score: float
    head_span: tuple[int, int] | None = None
    tail_span: tuple[int, int] | None = None


class GliRELExtractor:
    """Extract relations using GliREL.

    GliREL is a generalist model for relation extraction that works with
    entities from GliNER. Requires spaCy Doc for token position conversion.
    """

    DEFAULT_MODEL = "jackboyla/glirel-large-v0"
    DEFAULT_THRESHOLD = 0.5

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        threshold: float = DEFAULT_THRESHOLD,
    ):
        self.model_name = model_name
        self.threshold = threshold
        self._model = None

    def _load_model(self):
        """Lazy load the GliREL model."""
        if self._model is None:
            try:
                from glirel import GLiREL
                self._model = GLiREL.from_pretrained(self.model_name)
            except ImportError:
                raise ImportError(
                    "GliREL not installed. Install with: pip install glirel"
                )
        return self._model

    def extract_relations(
        self,
        text: str,
        entities: list[EntitySpan],
        relation_labels: list[str] | None = None,
        doc: Any = None,
        threshold: float | None = None,
    ) -> list[RelationSpan]:
        """Extract relations between entities.

        Args:
            text: Source text
            entities: Entity spans from GliNER
            relation_labels: Relation types to detect
            doc: spaCy Doc object for char-to-token conversion
            threshold: Minimum confidence threshold
        """
        if not entities or len(entities) < 2:
            return []

        model = self._load_model()
        use_labels = relation_labels or DEFAULT_RELATION_LABELS
        use_threshold = threshold or self.threshold

        if doc is None:
            logger.warning("No spaCy Doc provided; char-to-token conversion may fail")
            return []

        # Convert entities to GliREL NER span format: [start_token, end_token, label, text]
        ner_spans = self._convert_entities_to_spans(text, entities, doc)
        if not ner_spans:
            return []

        # Build tokens list from spaCy doc
        tokens = [token.text for token in doc]

        try:
            # GliREL expects: tokens, ner_spans, relation_labels
            raw_relations = model.predict_relations(
                tokens,
                use_labels,
                threshold=use_threshold,
                ner=ner_spans,
            )
        except Exception as e:
            logger.warning(f"GliREL extraction failed: {e}")
            return []

        # Convert to RelationSpan objects
        relations = self._convert_relations(raw_relations, entities, text)

        return relations

    def _convert_entities_to_spans(
        self,
        text: str,
        entities: list[EntitySpan],
        doc: Any,
    ) -> list[list]:
        """Convert EntitySpan objects to GliREL format [start_token, end_token, label, text].

        This is the CRITICAL char-to-token conversion step.
        GliNER outputs character positions, GliREL needs token positions.
        """
        ner_spans = []
        for entity in entities:
            token_start, token_end = self._char_to_token(doc, entity.start, entity.end)
            if token_start is not None and token_end is not None:
                ner_spans.append([token_start, token_end, entity.label, entity.text])

        return ner_spans

    def _char_to_token(
        self,
        doc: Any,
        char_start: int,
        char_end: int,
    ) -> tuple[int | None, int | None]:
        """Map character positions to token positions using spaCy Doc.

        This is the most fragile part of the pipeline. Iterates through
        spaCy tokens to find which tokens contain the given character range.
        """
        token_start = None
        token_end = None

        for i, token in enumerate(doc):
            tok_start = token.idx
            tok_end = token.idx + len(token)

            if tok_start <= char_start < tok_end:
                token_start = i
            if tok_start < char_end <= tok_end:
                token_end = i + 1

        return token_start, token_end

    def _convert_relations(
        self,
        raw_relations: list[dict],
        entities: list[EntitySpan],
        text: str,
    ) -> list[RelationSpan]:
        """Convert raw GliREL output to RelationSpan objects."""
        relations = []

        for rel in raw_relations:
            head_text = rel.get("head", {}).get("text", "") if isinstance(rel.get("head"), dict) else str(rel.get("head_text", ""))
            tail_text = rel.get("tail", {}).get("text", "") if isinstance(rel.get("tail"), dict) else str(rel.get("tail_text", ""))
            relation = rel.get("label", rel.get("relation", ""))
            score = rel.get("score", 0.0)

            # Find matching entities for labels
            head_label = self._find_entity_label(head_text, entities)
            tail_label = self._find_entity_label(tail_text, entities)

            if not head_text or not tail_text or not relation:
                continue

            relations.append(RelationSpan(
                head_text=head_text,
                head_label=head_label,
                tail_text=tail_text,
                tail_label=tail_label,
                relation=relation,
                score=score,
            ))

        return relations

    def _find_entity_label(self, text: str, entities: list[EntitySpan]) -> str:
        """Find the label for an entity by matching text."""
        text_lower = text.lower().strip()
        for entity in entities:
            if entity.text.lower().strip() == text_lower:
                return entity.label
        return "entity"

    def to_triplets(
        self,
        relations: list[RelationSpan],
        validate: bool = True,
    ) -> list[Triplet]:
        """Convert RelationSpans to Triplet objects with optional semantic validation."""
        triplets = []
        for rel in relations:
            # Semantic validation
            if validate and not validate_relation(rel.head_label, rel.relation, rel.tail_label):
                continue

            predicate = normalize_predicate(rel.relation)

            triplets.append(Triplet(
                subject=rel.head_text,
                predicate=predicate,
                object=rel.tail_text,
                confidence=rel.score,
                metadata={
                    "subject_label": rel.head_label,
                    "object_label": rel.tail_label,
                    "original_predicate": rel.relation,
                    "method": "glirel",
                },
            ))

        return triplets


class MockGliRELExtractor:
    """Fallback when GliREL is not installed."""

    def __init__(self, **kwargs):
        pass

    def extract_relations(self, text: str, entities: list[EntitySpan], **kwargs) -> list[RelationSpan]:
        return []

    def to_triplets(self, relations: list[RelationSpan], **kwargs) -> list[Triplet]:
        return []


def create_glirel_extractor(**kwargs) -> GliRELExtractor | MockGliRELExtractor:
    """Create a GliREL extractor, falling back to mock if not available."""
    try:
        from glirel import GLiREL  # noqa: F401
        return GliRELExtractor(**kwargs)
    except ImportError:
        return MockGliRELExtractor(**kwargs)
