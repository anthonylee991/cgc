"""Relationship discovery engine for finding connections across data sources.

Combines:
1. Explicit constraints (foreign keys)
2. Naming convention inference (user_id -> users.id)
3. Cardinality matching (same unique counts)
4. Value overlap detection (sample values match)
5. Triplet extraction from text (patterns + GliNER)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from cgc.core.schema import Schema, Field, FieldId
from cgc.core.graph import (
    Relationship,
    RelationshipGraph,
    RelationshipType,
    Confidence,
    InferenceMethod,
)
from cgc.core.triplet import Triplet
# NOTE: extract_triplets is imported lazily where used to avoid loading torch/spacy at startup

if TYPE_CHECKING:
    from cgc.adapters.base import DataSource


class InferenceRule(ABC):
    """Base class for relationship inference rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name for identification."""
        ...

    @abstractmethod
    def infer(self, schemas: list[Schema]) -> list[Relationship]:
        """Infer relationships from schemas."""
        ...


class NamingConventionRule(InferenceRule):
    """Infer relationships from naming conventions.

    Examples:
    - user_id -> users.id
    - userId -> users.id
    - author_user_id -> users.id
    - post_uuid -> posts.uuid
    """

    @property
    def name(self) -> str:
        return "naming_convention"

    def __init__(self):
        self.patterns = [
            # user_id -> users.id
            (re.compile(r"^(.+)_id$"), lambda m: f"{m.group(1)}s", "id"),
            # userId -> users.id (camelCase)
            (re.compile(r"^(.+)Id$"), lambda m: f"{m.group(1).lower()}s", "id"),
            # author_user_id -> users.id
            (re.compile(r"^.+_user_id$"), lambda m: "users", "id"),
            # post_uuid -> posts.uuid
            (re.compile(r"^(.+)_uuid$"), lambda m: f"{m.group(1)}s", "uuid"),
            # fk_table_column -> table.column
            (re.compile(r"^fk_(\w+)_(\w+)$"), lambda m: m.group(1), lambda m: m.group(2)),
        ]

    def infer(self, schemas: list[Schema]) -> list[Relationship]:
        """Infer relationships from field naming patterns."""
        relationships = []

        # Build lookup of all entities
        entity_lookup: dict[str, tuple[Schema, "Entity"]] = {}
        for schema in schemas:
            for entity in schema.entities:
                entity_lookup[entity.name.lower()] = (schema, entity)

        # Check each field against patterns
        for schema in schemas:
            for entity in schema.entities:
                for field in entity.fields:
                    # Skip if already a known FK
                    if field.is_foreign_key:
                        continue

                    for pattern, table_fn, target_field_fn in self.patterns:
                        match = pattern.match(field.name)
                        if not match:
                            continue

                        target_table = table_fn(match).lower()

                        if target_table in entity_lookup:
                            target_schema, target_entity = entity_lookup[target_table]

                            # Get target field name
                            if callable(target_field_fn):
                                target_field = target_field_fn(match)
                            else:
                                target_field = target_field_fn

                            # Check if target field exists
                            if any(f.name == target_field for f in target_entity.fields):
                                rel = Relationship(
                                    id=f"naming:{schema.source_id}.{entity.name}.{field.name}->{target_schema.source_id}.{target_entity.name}.{target_field}",
                                    from_field=FieldId(schema.source_id, entity.name, field.name),
                                    to_field=FieldId(target_schema.source_id, target_entity.name, target_field),
                                    relationship_type=RelationshipType.MANY_TO_ONE,
                                    confidence=Confidence.MEDIUM,
                                    inferred_by=InferenceMethod.NAMING_CONVENTION,
                                )
                                relationships.append(rel)
                                break  # Found a match, move to next field

        return relationships


class CardinalityMatchRule(InferenceRule):
    """Infer relationships from matching cardinality.

    If two fields have very similar unique counts, they might represent
    the same logical entity across different sources.
    """

    @property
    def name(self) -> str:
        return "cardinality_match"

    def __init__(self, tolerance: float = 0.1, min_unique: int = 10):
        """Initialize rule.

        Args:
            tolerance: Maximum deviation in cardinality ratio (0.1 = 10%)
            min_unique: Minimum unique values to consider
        """
        self.tolerance = tolerance
        self.min_unique = min_unique

    def infer(self, schemas: list[Schema]) -> list[Relationship]:
        """Infer relationships from cardinality matching."""
        relationships = []

        # Collect fields with cardinality
        fields_with_cardinality = []
        for schema in schemas:
            for entity in schema.entities:
                for field in entity.fields:
                    if (
                        field.cardinality
                        and field.cardinality.unique_count >= self.min_unique
                    ):
                        fields_with_cardinality.append((schema, entity, field))

        # Compare pairs
        for i, (schema_a, entity_a, field_a) in enumerate(fields_with_cardinality):
            for schema_b, entity_b, field_b in fields_with_cardinality[i + 1:]:
                # Skip same entity
                if (
                    entity_a.name == entity_b.name
                    and schema_a.source_id == schema_b.source_id
                ):
                    continue

                # Skip different data types
                if field_a.data_type != field_b.data_type:
                    continue

                # Check cardinality match
                card_a = field_a.cardinality.unique_count
                card_b = field_b.cardinality.unique_count

                ratio = min(card_a, card_b) / max(card_a, card_b)

                if ratio >= (1 - self.tolerance):
                    rel = Relationship(
                        id=f"cardinality:{schema_a.source_id}.{entity_a.name}.{field_a.name}<->{schema_b.source_id}.{entity_b.name}.{field_b.name}",
                        from_field=FieldId(schema_a.source_id, entity_a.name, field_a.name),
                        to_field=FieldId(schema_b.source_id, entity_b.name, field_b.name),
                        relationship_type=RelationshipType.SAME_ENTITY,
                        confidence=Confidence.LOW,
                        inferred_by=InferenceMethod.CARDINALITY_MATCH,
                        metadata={"cardinality_ratio": ratio},
                    )
                    relationships.append(rel)

        return relationships


class ValueOverlapRule(InferenceRule):
    """Infer relationships from sample value overlap.

    If two fields share many of the same sample values, they might
    represent related or identical entities.
    """

    @property
    def name(self) -> str:
        return "value_overlap"

    def __init__(self, min_overlap: float = 0.5, min_samples: int = 3):
        """Initialize rule.

        Args:
            min_overlap: Minimum Jaccard similarity to consider
            min_samples: Minimum sample values required
        """
        self.min_overlap = min_overlap
        self.min_samples = min_samples

    def infer(self, schemas: list[Schema]) -> list[Relationship]:
        """Infer relationships from value overlap."""
        relationships = []

        # Collect fields with sample values
        fields_with_samples = []
        for schema in schemas:
            for entity in schema.entities:
                for field in entity.fields:
                    if len(field.sample_values) >= self.min_samples:
                        fields_with_samples.append((schema, entity, field))

        # Compare pairs
        for i, (schema_a, entity_a, field_a) in enumerate(fields_with_samples):
            for schema_b, entity_b, field_b in fields_with_samples[i + 1:]:
                # Skip same entity
                if (
                    entity_a.name == entity_b.name
                    and schema_a.source_id == schema_b.source_id
                ):
                    continue

                # Skip different types
                if field_a.data_type != field_b.data_type:
                    continue

                # Calculate Jaccard similarity
                set_a = set(str(v) for v in field_a.sample_values)
                set_b = set(str(v) for v in field_b.sample_values)

                if not set_a or not set_b:
                    continue

                intersection = len(set_a & set_b)
                union = len(set_a | set_b)
                overlap = intersection / union if union > 0 else 0

                if overlap >= self.min_overlap:
                    rel = Relationship(
                        id=f"overlap:{schema_a.source_id}.{entity_a.name}.{field_a.name}<->{schema_b.source_id}.{entity_b.name}.{field_b.name}",
                        from_field=FieldId(schema_a.source_id, entity_a.name, field_a.name),
                        to_field=FieldId(schema_b.source_id, entity_b.name, field_b.name),
                        relationship_type=RelationshipType.SAME_ENTITY,
                        confidence=Confidence.LOW,
                        inferred_by=InferenceMethod.VALUE_OVERLAP,
                        metadata={"overlap_ratio": overlap},
                    )
                    relationships.append(rel)

        return relationships


class RelationshipDiscoveryEngine:
    """Engine for discovering relationships across data sources.

    Combines multiple inference strategies:
    1. Explicit constraints from schema (foreign keys)
    2. Naming convention patterns
    3. Cardinality matching
    4. Value overlap detection
    5. Triplet extraction from text content
    """

    def __init__(self):
        self.rules: list[InferenceRule] = [
            NamingConventionRule(),
            CardinalityMatchRule(),
            ValueOverlapRule(),
        ]

    def add_rule(self, rule: InferenceRule) -> None:
        """Add a custom inference rule."""
        self.rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                return True
        return False

    def discover(self, schemas: list[Schema]) -> RelationshipGraph:
        """Discover relationships across all schemas.

        Args:
            schemas: List of discovered schemas

        Returns:
            RelationshipGraph with all discovered relationships
        """
        graph = RelationshipGraph()

        # Add explicit relationships from schemas (foreign keys)
        for schema in schemas:
            for rel in schema.relationships:
                graph.add(rel)

        # Run inference rules
        for rule in self.rules:
            inferred = rule.infer(schemas)
            for rel in inferred:
                # Avoid duplicates
                existing = graph.related_to(rel.from_field)
                is_duplicate = any(r.to_field == rel.to_field for r in existing)
                if not is_duplicate:
                    graph.add(rel)

        return graph

    def extract_from_text(
        self,
        text: str,
        source_id: str = "text",
        use_gliner: bool = True,
        domain: str | None = None,
    ) -> list[Relationship]:
        """Extract relationships from unstructured text.

        Uses hybrid triplet extraction (patterns + GliNER + GliREL) to find
        semantic relationships in text content.

        Args:
            text: Input text
            source_id: Source identifier for the relationships
            use_gliner: Whether to use GliNER for NER
            domain: Force a specific industry pack ID (e.g., "tech_startup")

        Returns:
            List of semantic relationships
        """
        # Lazy import to avoid loading torch/spacy at startup
        from cgc.discovery.extractor import extract_triplets
        triplets = extract_triplets(text, use_gliner=use_gliner, domain=domain)
        return self._triplets_to_relationships(triplets, source_id)

    def extract_from_structured(
        self,
        data: list[dict],
        source_id: str = "structured",
    ) -> list[Relationship]:
        """Extract relationships from structured data (CSV rows, JSON objects).

        Uses hub-and-spoke model to identify primary entities and their
        relationships to categorical columns.

        Args:
            data: List of row dicts (e.g., from CSV or JSON)
            source_id: Source identifier for the relationships

        Returns:
            List of semantic relationships
        """
        from cgc.discovery.structured import StructuredExtractor
        extractor = StructuredExtractor()
        triplets = extractor.extract_triplets(data)
        return self._triplets_to_relationships(triplets, source_id)

    def _triplets_to_relationships(
        self,
        triplets: list[Triplet],
        source_id: str,
    ) -> list[Relationship]:
        """Convert triplets to Relationship objects."""
        relationships = []
        for triplet in triplets:
            rel = Relationship(
                id=f"triplet:{source_id}:{triplet.subject}-{triplet.predicate}-{triplet.object}",
                from_field=FieldId(source_id, "text", triplet.subject),
                to_field=FieldId(source_id, "text", triplet.object),
                relationship_type=RelationshipType.SEMANTIC,
                confidence=self._triplet_confidence(triplet),
                inferred_by=InferenceMethod.TRIPLET_EXTRACTION,
                metadata={
                    "predicate": triplet.predicate,
                    "source_text": triplet.source_text,
                    "confidence": triplet.confidence,
                },
            )
            relationships.append(rel)
        return relationships

    def _triplet_confidence(self, triplet: Triplet) -> Confidence:
        """Map triplet confidence to Confidence enum."""
        if triplet.confidence >= 0.85:
            return Confidence.HIGH
        elif triplet.confidence >= 0.7:
            return Confidence.MEDIUM
        else:
            return Confidence.LOW


# Default engine instance
default_engine = RelationshipDiscoveryEngine()


def discover_relationships(schemas: list[Schema]) -> RelationshipGraph:
    """Discover relationships using default engine."""
    return default_engine.discover(schemas)


def extract_relationships_from_text(
    text: str,
    source_id: str = "text",
    use_gliner: bool = True,
) -> list[Relationship]:
    """Extract semantic relationships from text."""
    return default_engine.extract_from_text(text, source_id, use_gliner)
