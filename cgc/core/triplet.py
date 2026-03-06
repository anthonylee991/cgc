"""Triplet types for subject-predicate-object extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Triplet:
    """A subject-predicate-object triplet extracted from text."""

    subject: str
    predicate: str
    object: str
    confidence: float = 1.0  # 0.0 - 1.0
    source_span: tuple[int, int] | None = None  # Character offsets in original text
    source_text: str | None = None  # Original text this was extracted from
    metadata: dict[str, Any] = field(default_factory=dict)
    subject_label: str | None = None  # Entity type (person, organization, etc.)
    object_label: str | None = None   # Entity type

    def __str__(self) -> str:
        return f"({self.subject}, {self.predicate}, {self.object})"

    def __hash__(self) -> int:
        return hash((self.subject.lower(), self.predicate.lower(), self.object.lower()))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Triplet):
            return False
        return (
            self.subject.lower() == other.subject.lower()
            and self.predicate.lower() == other.predicate.lower()
            and self.object.lower() == other.object.lower()
        )

    @property
    def is_high_confidence(self) -> bool:
        """Check if confidence is above 0.8 threshold."""
        return self.confidence >= 0.8

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "source_span": self.source_span,
        }
        if self.subject_label:
            result["subject_label"] = self.subject_label
        if self.object_label:
            result["object_label"] = self.object_label
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Triplet:
        """Create from dictionary."""
        return cls(
            subject=data["subject"],
            predicate=data["predicate"],
            object=data["object"],
            confidence=data.get("confidence", 1.0),
            source_span=tuple(data["source_span"]) if data.get("source_span") else None,
            subject_label=data.get("subject_label"),
            object_label=data.get("object_label"),
        )

    def matches_subject(self, query: str, fuzzy: bool = True) -> bool:
        """Check if subject matches query."""
        if fuzzy:
            return fuzzy_match(self.subject, query)
        return self.subject.lower() == query.lower()

    def matches_object(self, query: str, fuzzy: bool = True) -> bool:
        """Check if object matches query."""
        if fuzzy:
            return fuzzy_match(self.object, query)
        return self.object.lower() == query.lower()

    def involves(self, entity: str, fuzzy: bool = True) -> bool:
        """Check if triplet involves an entity (as subject or object)."""
        return self.matches_subject(entity, fuzzy) or self.matches_object(entity, fuzzy)


def fuzzy_match(a: str, b: str) -> bool:
    """Check if two strings are fuzzy equal."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    return a_lower == b_lower or a_lower in b_lower or b_lower in a_lower


@dataclass
class TripletCollection:
    """A collection of triplets with query capabilities."""

    triplets: list[Triplet] = field(default_factory=list)

    def add(self, triplet: Triplet) -> None:
        """Add a triplet, avoiding duplicates."""
        if triplet not in self.triplets:
            self.triplets.append(triplet)

    def add_all(self, triplets: list[Triplet]) -> int:
        """Add multiple triplets, returning count of new ones added."""
        count = 0
        for t in triplets:
            if t not in self.triplets:
                self.triplets.append(t)
                count += 1
        return count

    def find_by_subject(self, subject: str, fuzzy: bool = True) -> list[Triplet]:
        """Find all triplets with matching subject."""
        return [t for t in self.triplets if t.matches_subject(subject, fuzzy)]

    def find_by_object(self, obj: str, fuzzy: bool = True) -> list[Triplet]:
        """Find all triplets with matching object."""
        return [t for t in self.triplets if t.matches_object(obj, fuzzy)]

    def find_by_predicate(self, predicate: str) -> list[Triplet]:
        """Find all triplets with matching predicate."""
        pred_lower = predicate.lower()
        return [t for t in self.triplets if pred_lower in t.predicate.lower()]

    def involving(self, entity: str, fuzzy: bool = True) -> list[Triplet]:
        """Find all triplets involving an entity."""
        return [t for t in self.triplets if t.involves(entity, fuzzy)]

    def high_confidence(self, threshold: float = 0.8) -> list[Triplet]:
        """Get triplets above confidence threshold."""
        return [t for t in self.triplets if t.confidence >= threshold]

    def __len__(self) -> int:
        return len(self.triplets)

    def __iter__(self):
        return iter(self.triplets)

    def to_list(self) -> list[dict[str, Any]]:
        """Convert to list of dictionaries."""
        return [t.to_dict() for t in self.triplets]
