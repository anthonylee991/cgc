"""Relationship graph types for representing connections between data."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

from .schema import FieldId


class RelationshipType(Enum):
    """Types of relationships between fields/entities."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"
    SAME_ENTITY = "same_entity"  # Same logical entity across sources
    CONTAINS = "contains"  # Directory contains file, document contains section
    REFERENCES = "references"  # Generic reference
    SEMANTIC = "semantic"  # Extracted via NER/triplet extraction


class Confidence(Enum):
    """Confidence level of inferred relationships."""

    CERTAIN = "certain"  # Explicit FK constraint
    HIGH = "high"  # Strong naming + cardinality match
    MEDIUM = "medium"  # Naming convention match
    LOW = "low"  # Statistical correlation only


class InferenceMethod(Enum):
    """How the relationship was discovered."""

    EXPLICIT_CONSTRAINT = "explicit_constraint"  # FK in schema
    NAMING_CONVENTION = "naming_convention"  # user_id -> users.id
    CARDINALITY_MATCH = "cardinality_match"  # Same unique count
    VALUE_OVERLAP = "value_overlap"  # Sample values match
    CROSS_SOURCE_RULE = "cross_source_rule"  # Custom rule
    TRIPLET_EXTRACTION = "triplet_extraction"  # GliNER/patterns


@dataclass
class Relationship:
    """A discovered relationship between two fields."""

    id: str
    from_field: FieldId
    to_field: FieldId
    relationship_type: RelationshipType
    confidence: Confidence
    inferred_by: InferenceMethod
    metadata: dict = field(default_factory=dict)  # e.g., {"overlap_ratio": 0.95}

    def __hash__(self) -> int:
        return hash(self.id)

    def involves(self, field_id: FieldId) -> bool:
        """Check if this relationship involves a field."""
        return self.from_field == field_id or self.to_field == field_id

    def other_side(self, field_id: FieldId) -> FieldId | None:
        """Get the field on the other side of this relationship."""
        if self.from_field == field_id:
            return self.to_field
        if self.to_field == field_id:
            return self.from_field
        return None

    def __str__(self) -> str:
        return f"{self.from_field} --[{self.relationship_type.value}]--> {self.to_field}"


@dataclass
class RelationshipGraph:
    """Graph of relationships across all connected sources."""

    relationships: list[Relationship] = field(default_factory=list)
    _index: dict[FieldId, list[str]] = field(default_factory=dict, repr=False)

    def add(self, rel: Relationship) -> None:
        """Add a relationship to the graph."""
        self.relationships.append(rel)
        self._index.setdefault(rel.from_field, []).append(rel.id)
        self._index.setdefault(rel.to_field, []).append(rel.id)

    def remove(self, rel_id: str) -> bool:
        """Remove a relationship by ID."""
        for i, rel in enumerate(self.relationships):
            if rel.id == rel_id:
                self.relationships.pop(i)
                # Update index
                if rel.from_field in self._index:
                    self._index[rel.from_field] = [
                        r for r in self._index[rel.from_field] if r != rel_id
                    ]
                if rel.to_field in self._index:
                    self._index[rel.to_field] = [
                        r for r in self._index[rel.to_field] if r != rel_id
                    ]
                return True
        return False

    def get(self, rel_id: str) -> Relationship | None:
        """Get a relationship by ID."""
        return next((r for r in self.relationships if r.id == rel_id), None)

    def related_to(self, field_id: FieldId) -> list[Relationship]:
        """Get all relationships involving a field."""
        rel_ids = self._index.get(field_id, [])
        return [r for r in self.relationships if r.id in rel_ids]

    def find_path(
        self,
        from_field: FieldId,
        to_field: FieldId,
        max_depth: int = 5,
    ) -> list[Relationship] | None:
        """Find shortest path between two fields (BFS)."""
        if from_field == to_field:
            return []

        visited = {from_field}
        queue: deque[tuple[FieldId, list[Relationship]]] = deque([(from_field, [])])

        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            for rel in self.related_to(current):
                next_field = rel.other_side(current)
                if next_field is None:
                    continue

                new_path = path + [rel]

                if next_field == to_field:
                    return new_path

                if next_field not in visited:
                    visited.add(next_field)
                    queue.append((next_field, new_path))

        return None

    def same_entity_fields(self, field_id: FieldId) -> list[FieldId]:
        """Get all fields representing the same logical entity."""
        result = [field_id]
        for rel in self.related_to(field_id):
            if rel.relationship_type == RelationshipType.SAME_ENTITY:
                other = rel.other_side(field_id)
                if other:
                    result.append(other)
        return result

    def by_confidence(self, min_confidence: Confidence) -> list[Relationship]:
        """Get relationships at or above a confidence level."""
        confidence_order = [Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH, Confidence.CERTAIN]
        min_idx = confidence_order.index(min_confidence)
        return [
            r for r in self.relationships
            if confidence_order.index(r.confidence) >= min_idx
        ]

    def by_source(self, source_id: str) -> list[Relationship]:
        """Get relationships involving a specific source."""
        return [
            r for r in self.relationships
            if r.from_field.source_id == source_id or r.to_field.source_id == source_id
        ]

    def cross_source(self) -> list[Relationship]:
        """Get relationships that span multiple sources."""
        return [
            r for r in self.relationships
            if r.from_field.source_id != r.to_field.source_id
        ]

    def __len__(self) -> int:
        return len(self.relationships)

    def __iter__(self) -> Iterator[Relationship]:
        return iter(self.relationships)

    def to_dot(self) -> str:
        """Export as Graphviz DOT format."""
        lines = ["digraph RelationshipGraph {", "  rankdir=LR;", "  node [shape=box];"]

        # Collect unique nodes
        nodes: set[FieldId] = set()
        for rel in self.relationships:
            nodes.add(rel.from_field)
            nodes.add(rel.to_field)

        # Add nodes
        for node in nodes:
            label = f"{node.entity}.{node.field}"
            lines.append(f'  "{node}" [label="{label}"];')

        # Add edges
        for rel in self.relationships:
            style = "solid" if rel.confidence == Confidence.CERTAIN else "dashed"
            color = {
                Confidence.CERTAIN: "black",
                Confidence.HIGH: "darkgreen",
                Confidence.MEDIUM: "orange",
                Confidence.LOW: "gray",
            }.get(rel.confidence, "gray")
            lines.append(
                f'  "{rel.from_field}" -> "{rel.to_field}" '
                f'[label="{rel.relationship_type.value}" style="{style}" color="{color}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "relationships": [
                {
                    "id": r.id,
                    "from": str(r.from_field),
                    "to": str(r.to_field),
                    "type": r.relationship_type.value,
                    "confidence": r.confidence.value,
                    "inferred_by": r.inferred_by.value,
                    "metadata": r.metadata,
                }
                for r in self.relationships
            ],
            "total": len(self.relationships),
        }
