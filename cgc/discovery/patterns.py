"""Pattern-based triplet extraction for conversational text.

High precision extraction using regex patterns for common conversational structures
like "I prefer X", "My name is Y", "X is my Y", etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from cgc.core.triplet import Triplet


@dataclass
class ConversationalPattern:
    """A regex pattern for extracting triplets."""

    name: str
    regex: re.Pattern
    extractor: Callable[[re.Match, str], Triplet | None]
    confidence: float = 0.85


def _extract_i_prefer(match: re.Match, text: str) -> Triplet | None:
    """Extract 'I prefer/like/love/use X' patterns."""
    verb = match.group(1).lower()
    obj = match.group(2).strip().rstrip(".,!?")
    if obj:
        return Triplet(
            subject="I",
            predicate=verb,
            object=obj,
            confidence=0.90,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_i_am(match: re.Match, text: str) -> Triplet | None:
    """Extract 'I am a X' patterns."""
    obj = match.group(1).strip().rstrip(".,!?")
    if obj:
        return Triplet(
            subject="I",
            predicate="am",
            object=obj,
            confidence=0.90,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_i_work(match: re.Match, text: str) -> Triplet | None:
    """Extract 'I work at/for X' patterns."""
    prep = match.group(1).lower()
    obj = match.group(2).strip().rstrip(".,!?")
    if obj:
        return Triplet(
            subject="I",
            predicate=f"work {prep}",
            object=obj,
            confidence=0.90,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_i_live(match: re.Match, text: str) -> Triplet | None:
    """Extract 'I live in X' patterns."""
    obj = match.group(1).strip().rstrip(".,!?")
    if obj:
        return Triplet(
            subject="I",
            predicate="live in",
            object=obj,
            confidence=0.90,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_my_x_is(match: re.Match, text: str) -> Triplet | None:
    """Extract 'My X is Y' patterns."""
    what = match.group(1).strip()
    value = match.group(2).strip().rstrip(".,!?")
    if what and value:
        return Triplet(
            subject=f"My {what}",
            predicate="is",
            object=value,
            confidence=0.90,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_my_favorite(match: re.Match, text: str) -> Triplet | None:
    """Extract 'My favorite X is Y' patterns."""
    what = match.group(1).strip()
    value = match.group(2).strip().rstrip(".,!?")
    if what and value:
        return Triplet(
            subject=f"My favorite {what}",
            predicate="is",
            object=value,
            confidence=0.90,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_x_is_my(match: re.Match, text: str) -> Triplet | None:
    """Extract 'X is my Y' patterns."""
    who = match.group(1).strip()
    relation = match.group(2).strip().rstrip(".,!?")
    if who and relation:
        return Triplet(
            subject=who,
            predicate="is",
            object=f"my {relation}",
            confidence=0.85,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_the_x_is(match: re.Match, text: str) -> Triplet | None:
    """Extract 'The X is Y' patterns (constants, settings)."""
    what = match.group(1).strip()
    value = match.group(2).strip().rstrip(".,!?")
    if what and value:
        return Triplet(
            subject=what,
            predicate="is",
            object=value,
            confidence=0.85,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_x_uses(match: re.Match, text: str) -> Triplet | None:
    """Extract 'X uses/prefers/requires Y' patterns."""
    subj = match.group(1).strip()
    verb = match.group(2).lower()
    obj = match.group(3).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(
            subject=subj,
            predicate=verb,
            object=obj,
            confidence=0.85,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


def _extract_x_is_y(match: re.Match, text: str) -> Triplet | None:
    """Extract generic 'X is Y' patterns."""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj and len(subj) > 1 and len(obj) > 1:
        return Triplet(
            subject=subj,
            predicate="is",
            object=obj,
            confidence=0.70,
            source_span=(match.start(), match.end()),
            source_text=match.group(0),
        )
    return None


# Define all patterns
PATTERNS: list[ConversationalPattern] = [
    # High confidence patterns
    ConversationalPattern(
        name="i_prefer",
        regex=re.compile(r"\bI\s+(prefer|like|love|enjoy|use|want|need)\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_i_prefer,
        confidence=0.90,
    ),
    ConversationalPattern(
        name="i_am",
        regex=re.compile(r"\bI(?:'m|\s+am)\s+(?:a\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_i_am,
        confidence=0.90,
    ),
    ConversationalPattern(
        name="i_work",
        regex=re.compile(r"\bI\s+work\s+(at|for)\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_i_work,
        confidence=0.90,
    ),
    ConversationalPattern(
        name="i_live",
        regex=re.compile(r"\bI\s+live\s+in\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_i_live,
        confidence=0.90,
    ),
    ConversationalPattern(
        name="my_favorite",
        regex=re.compile(r"\bMy\s+favorite\s+(\w+)\s+is\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_my_favorite,
        confidence=0.90,
    ),
    ConversationalPattern(
        name="my_x_is",
        regex=re.compile(r"\bMy\s+(\w+(?:\s+\w+)?)\s+is\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_my_x_is,
        confidence=0.90,
    ),
    ConversationalPattern(
        name="x_is_my",
        regex=re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+is\s+my\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_x_is_my,
        confidence=0.85,
    ),
    ConversationalPattern(
        name="the_x_is",
        regex=re.compile(r"\bThe\s+(\w+(?:\s+\w+)?)\s+is\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_the_x_is,
        confidence=0.85,
    ),
    ConversationalPattern(
        name="x_uses",
        regex=re.compile(r"\b(?:my\s+)?(\w+(?:\s+project)?)\s+(uses|prefers|requires)\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_x_uses,
        confidence=0.85,
    ),
    # Lower confidence generic pattern (run last)
    ConversationalPattern(
        name="x_is_y",
        regex=re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+is\s+(?:a\s+)?([a-zA-Z][a-zA-Z\s]+?)(?:\.|$)"),
        extractor=_extract_x_is_y,
        confidence=0.70,
    ),
]


class PatternMatcher:
    """Extract triplets using regex patterns."""

    def __init__(self, patterns: list[ConversationalPattern] | None = None):
        """Initialize with optional custom patterns."""
        self.patterns = patterns or PATTERNS

    def extract_triplets(self, text: str) -> list[Triplet]:
        """Extract triplets from text using patterns.

        Returns triplets sorted by position, with no overlapping spans.
        """
        triplets = []
        seen_spans: list[tuple[int, int]] = []

        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                triplet = pattern.extractor(match, text)
                if triplet is None:
                    continue

                span = triplet.source_span
                if span is None:
                    continue

                # Check if this span is dominated by an existing span
                is_dominated = any(
                    span[0] >= existing[0] and span[1] <= existing[1]
                    for existing in seen_spans
                )

                if not is_dominated:
                    # Remove any spans dominated by this one
                    seen_spans = [
                        s for s in seen_spans
                        if not (s[0] >= span[0] and s[1] <= span[1])
                    ]
                    triplets = [
                        t for t in triplets
                        if t.source_span is None or not (
                            t.source_span[0] >= span[0] and t.source_span[1] <= span[1]
                        )
                    ]

                    seen_spans.append(span)
                    triplets.append(triplet)

        # Sort by position
        triplets.sort(key=lambda t: t.source_span[0] if t.source_span else 0)

        return triplets

    def add_pattern(self, pattern: ConversationalPattern) -> None:
        """Add a custom pattern."""
        self.patterns.append(pattern)


# Default instance for convenience
default_matcher = PatternMatcher()


def extract_triplets_with_patterns(text: str) -> list[Triplet]:
    """Extract triplets using default pattern matcher."""
    return default_matcher.extract_triplets(text)
