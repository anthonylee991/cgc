"""Garbage filtering and deduplication utilities for extraction pipeline.

Centralizes all filtering logic: pronouns, section headers, gerunds,
mission statements, HTML, and length-based filtering. Also provides
span overlap and fuzzy deduplication for triplets.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cgc.discovery.gliner import EntitySpan

from cgc.core.triplet import Triplet

# --- Garbage entity constants ---

PRONOUNS = frozenset({
    "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "yourself",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves",
    "they", "them", "their", "theirs", "themselves",
    "this", "that", "these", "those",
    "who", "whom", "which", "what",
})

SECTION_HEADERS = frozenset({
    "overview", "summary", "conclusion", "introduction",
    "features", "pricing", "security", "requirements",
    "background", "methodology", "results", "discussion",
    "abstract", "references", "appendix", "acknowledgments",
    "table of contents", "executive summary",
    "objectives", "scope", "deliverables",
})

SINGLE_NOISE_WORDS = frozenset({
    "left", "right", "panel", "view", "button", "link",
    "input", "output", "step", "phase", "section", "page",
    "figure", "table", "item", "row", "column", "cell",
    "top", "bottom", "header", "footer", "sidebar",
    "menu", "tab", "form", "field", "label",
})

MAX_ENTITY_LENGTH = 60

_GERUND_RE = re.compile(r"^[a-z].*ing$", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MISSION_RE = re.compile(
    r"\b(our mission|we believe|we strive|our vision|we aim|dedicated to)\b",
    re.IGNORECASE,
)
_VERB_RE = re.compile(
    r"\b(is|are|was|were|has|have|had|does|do|did|will|would|can|could|"
    r"shall|should|may|might|must)\b",
    re.IGNORECASE,
)
_PROPER_NOUN_RE = re.compile(r"^[A-Z]")


def is_garbage_entity(text: str) -> bool:
    """Return True if the entity text is noise that should be filtered out."""
    stripped = text.strip()
    lower = stripped.lower()

    # Empty or too short
    if len(stripped) < 2:
        return True

    # Too long
    if len(stripped) > MAX_ENTITY_LENGTH:
        return True

    # Pronouns
    if lower in PRONOUNS:
        return True

    # Section headers
    if lower in SECTION_HEADERS:
        return True

    # Single noise words
    if lower in SINGLE_NOISE_WORDS:
        return True

    # Contains colons (likely a label or header)
    if ":" in stripped:
        return True

    # Contains newlines
    if "\n" in stripped or "\r" in stripped:
        return True

    # HTML tags
    if _HTML_TAG_RE.search(stripped):
        return True

    # Mission/vision statements
    if _MISSION_RE.search(stripped):
        return True

    # Gerunds that aren't proper nouns (e.g., "processing" but not "Manning")
    words = stripped.split()
    if len(words) == 1 and _GERUND_RE.match(stripped) and not _PROPER_NOUN_RE.match(stripped):
        return True

    # Sentences containing auxiliary/modal verbs (likely fragments, not entities)
    if len(words) > 3 and _VERB_RE.search(stripped):
        return True

    return False


def filter_entities(entities: list[EntitySpan]) -> list[EntitySpan]:
    """Remove garbage entities from a list."""
    return [e for e in entities if not is_garbage_entity(e.text)]


def filter_triplets(triplets: list[Triplet]) -> list[Triplet]:
    """Remove triplets with garbage subjects or objects."""
    return [
        t for t in triplets
        if not is_garbage_entity(t.subject) and not is_garbage_entity(t.object)
    ]


# --- Span overlap and deduplication ---

def spans_overlap(
    a: tuple[int, int],
    b: tuple[int, int],
    threshold: float = 0.5,
) -> bool:
    """Check if two character spans overlap significantly.

    Returns True if the overlap ratio exceeds threshold relative to either span.
    """
    overlap_start = max(a[0], b[0])
    overlap_end = min(a[1], b[1])

    if overlap_start >= overlap_end:
        return False

    overlap_len = overlap_end - overlap_start
    a_len = a[1] - a[0]
    b_len = b[1] - b[0]

    if a_len == 0 or b_len == 0:
        return False

    return (overlap_len / a_len > threshold) or (overlap_len / b_len > threshold)


def fuzzy_text_match(a: str, b: str) -> bool:
    """Check if two strings are fuzzy equal (case-insensitive, substring)."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    return a_lower == b_lower or a_lower in b_lower or b_lower in a_lower


def deduplicate_triplets(triplets: list[Triplet]) -> list[Triplet]:
    """Deduplicate triplets using span overlap, fuzzy matching, and bidirectional check.

    Priority: earlier triplets (typically from higher-precision sources) are kept.
    """
    if not triplets:
        return []

    unique: list[Triplet] = []

    for triplet in triplets:
        is_dup = False
        for existing in unique:
            # Span overlap check
            if triplet.source_span and existing.source_span:
                if spans_overlap(triplet.source_span, existing.source_span):
                    is_dup = True
                    break

            # Fuzzy text match (subject + object)
            if (
                fuzzy_text_match(triplet.subject, existing.subject)
                and fuzzy_text_match(triplet.object, existing.object)
            ):
                is_dup = True
                break

            # Bidirectional: A→B same as B→A for the same relation
            if (
                fuzzy_text_match(triplet.subject, existing.object)
                and fuzzy_text_match(triplet.object, existing.subject)
                and triplet.predicate.lower() == existing.predicate.lower()
            ):
                is_dup = True
                break

        if not is_dup:
            unique.append(triplet)

    return unique
