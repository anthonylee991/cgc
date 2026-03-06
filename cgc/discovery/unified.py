"""Unified extraction pipeline combining spaCy + GliNER + GliREL.

Orchestrates the full extraction flow:
1. spaCy tokenization (en_core_web_sm)
2. GliNER entity extraction with domain-specific labels
3. Char-to-token position conversion
4. GliREL relation extraction
5. Semantic type constraint filtering
6. Deduplication and garbage filtering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cgc.core.triplet import Triplet
from cgc.discovery.filters import deduplicate_triplets, filter_triplets
from cgc.discovery.gliner import EntitySpan, create_gliner_extractor
from cgc.discovery.glirel import RelationSpan, create_glirel_extractor

logger = logging.getLogger(__name__)

# Default labels when no industry pack is selected
DEFAULT_ENTITY_LABELS = [
    "person", "organization", "location", "date", "money",
    "product", "technology", "role", "department", "project",
    "policy", "event", "company",
]

DEFAULT_RELATION_LABELS = [
    "founded", "leads", "CEO of", "works at", "member of",
    "reports to", "manages", "headquartered in", "located in",
    "based in", "partner of", "acquired", "subsidiary of",
    "uses", "built with", "developed by", "provides",
    "governs", "applies to", "owns", "created by",
]


@dataclass
class UnifiedExtractionResult:
    """Result from the unified extraction pipeline."""

    entities: list[EntitySpan] = field(default_factory=list)
    relations: list[RelationSpan] = field(default_factory=list)
    triplets: list[Triplet] = field(default_factory=list)
    text: str = ""
    pack_id: str | None = None


class UnifiedExtractor:
    """Combined spaCy + GliNER + GliREL extraction pipeline.

    Pipeline flow:
        Text → spaCy tokenize → GliNER entities → char-to-token →
        GliREL relations → semantic constraints → dedup → Triplets
    """

    def __init__(
        self,
        gliner_model: str | None = None,
        glirel_model: str | None = None,
    ):
        self._gliner_model_name = gliner_model
        self._glirel_model_name = glirel_model
        self._spacy_nlp = None
        self._gliner = None
        self._glirel = None

    def _load_spacy(self):
        """Lazy load spaCy en_core_web_sm for tokenization."""
        if self._spacy_nlp is None:
            try:
                import spacy
                self._spacy_nlp = spacy.load("en_core_web_sm", disable=["ner", "parser", "lemmatizer"])
            except ImportError:
                raise ImportError(
                    "spaCy not installed. Install with: pip install spacy && "
                    "python -m spacy download en_core_web_sm"
                )
            except OSError:
                raise OSError(
                    "spaCy model not found. Download with: "
                    "python -m spacy download en_core_web_sm"
                )
        return self._spacy_nlp

    def _get_gliner(self):
        """Lazy get GliNER extractor."""
        if self._gliner is None:
            kwargs = {}
            if self._gliner_model_name:
                kwargs["model_name"] = self._gliner_model_name
            self._gliner = create_gliner_extractor(**kwargs)
        return self._gliner

    def _get_glirel(self):
        """Lazy get GliREL extractor."""
        if self._glirel is None:
            kwargs = {}
            if self._glirel_model_name:
                kwargs["model_name"] = self._glirel_model_name
            self._glirel = create_glirel_extractor(**kwargs)
        return self._glirel

    def extract(
        self,
        text: str,
        entity_labels: list[str] | None = None,
        relation_labels: list[str] | None = None,
        entity_threshold: float = 0.5,
        relation_threshold: float = 0.5,
    ) -> UnifiedExtractionResult:
        """Run the full unified extraction pipeline.

        Args:
            text: Input text to extract from
            entity_labels: Entity types to detect (from industry pack)
            relation_labels: Relation types to detect (from industry pack)
            entity_threshold: Minimum GliNER confidence
            relation_threshold: Minimum GliREL confidence
        """
        use_entity_labels = entity_labels or DEFAULT_ENTITY_LABELS
        use_relation_labels = relation_labels or DEFAULT_RELATION_LABELS

        result = UnifiedExtractionResult(text=text)

        # Step 1: spaCy tokenization
        try:
            nlp = self._load_spacy()
            doc = nlp(text)
        except (ImportError, OSError) as e:
            logger.warning(f"spaCy not available: {e}. Falling back to GliNER-only.")
            return self._fallback_extract(text, use_entity_labels, entity_threshold)

        # Step 2: GliNER entity extraction
        gliner = self._get_gliner()
        try:
            entities = gliner.extract_entities(
                text,
                labels=use_entity_labels,
                threshold=entity_threshold,
            )
        except Exception as e:
            logger.warning(f"GliNER extraction failed: {e}")
            entities = []

        result.entities = entities

        if len(entities) < 2:
            # Not enough entities for relation extraction
            return result

        # Step 3: GliREL relation extraction (with char-to-token conversion)
        glirel = self._get_glirel()
        try:
            relations = glirel.extract_relations(
                text,
                entities,
                relation_labels=use_relation_labels,
                doc=doc,
                threshold=relation_threshold,
            )
        except Exception as e:
            logger.warning(f"GliREL extraction failed: {e}")
            relations = []

        result.relations = relations

        # Step 4: Convert relations to triplets with semantic validation
        triplets = glirel.to_triplets(relations, validate=True)

        # Step 5: Filter garbage and deduplicate
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
        """Convenience method returning just triplets."""
        result = self.extract(text, entity_labels, relation_labels, **kwargs)
        return result.triplets

    def _fallback_extract(
        self,
        text: str,
        entity_labels: list[str],
        threshold: float,
    ) -> UnifiedExtractionResult:
        """Fallback to GliNER entity-pairing when spaCy/GliREL unavailable."""
        result = UnifiedExtractionResult(text=text)
        gliner = self._get_gliner()
        try:
            entities = gliner.extract_entities(text, labels=entity_labels, threshold=threshold)
            result.entities = entities
            triplets = gliner.extract_triplets(text)
            triplets = filter_triplets(triplets)
            result.triplets = triplets
        except Exception as e:
            logger.warning(f"Fallback extraction failed: {e}")
        return result
