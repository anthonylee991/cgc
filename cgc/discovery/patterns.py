"""Pattern-based triplet and entity extraction.

High precision extraction using 50+ regex patterns covering:
- Conversational patterns (I prefer, I work at, etc.)
- Employment & organizational relationships
- Location patterns
- E-commerce & product patterns
- Technical patterns
- Financial patterns
- General business patterns
- Entity detection (company suffixes, product names, roles, tech terms)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from cgc.core.triplet import Triplet


@dataclass
class ConversationalPattern:
    """A regex pattern for extracting triplets."""

    name: str
    regex: re.Pattern
    extractor: Callable[[re.Match, str], Triplet | None]
    confidence: float = 0.85


@dataclass
class EntityPattern:
    """A regex pattern for extracting entities."""

    name: str
    regex: re.Pattern
    label: str
    group: int = 0
    confidence: float = 0.85


@dataclass
class EntitySpanResult:
    """An entity detected by pattern matching."""

    text: str
    label: str
    start: int
    end: int
    confidence: float


# --- Known technologies for case-insensitive matching ---

KNOWN_TECHNOLOGIES = frozenset({
    "stripe", "slack", "notion", "figma", "react", "vue", "angular", "nextjs",
    "vercel", "netlify", "aws", "azure", "gcp", "docker", "kubernetes",
    "postgresql", "mongodb", "redis", "elasticsearch", "openai", "anthropic",
    "gemini", "chatgpt", "claude", "tailwind", "bootstrap", "typescript",
    "javascript", "python", "golang", "rust", "java", "node", "fastapi",
    "django", "flask", "express", "graphql", "rest", "oauth",
    "shopify", "woocommerce", "nuxt", "svelte", "remix", "astro",
    "terraform", "ansible", "jenkins", "github", "gitlab", "jira",
    "confluence", "salesforce", "hubspot", "datadog", "splunk",
})


# ============================================================
# Triplet extraction functions
# ============================================================

# --- Conversational patterns (existing, kept) ---

def _extract_i_prefer(match: re.Match, text: str) -> Triplet | None:
    verb = match.group(1).lower()
    obj = match.group(2).strip().rstrip(".,!?")
    if obj:
        return Triplet(subject="I", predicate=verb, object=obj,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_i_am(match: re.Match, text: str) -> Triplet | None:
    obj = match.group(1).strip().rstrip(".,!?")
    if obj:
        return Triplet(subject="I", predicate="am", object=obj,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_i_work(match: re.Match, text: str) -> Triplet | None:
    prep = match.group(1).lower()
    obj = match.group(2).strip().rstrip(".,!?")
    if obj:
        return Triplet(subject="I", predicate=f"work {prep}", object=obj,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_i_live(match: re.Match, text: str) -> Triplet | None:
    obj = match.group(1).strip().rstrip(".,!?")
    if obj:
        return Triplet(subject="I", predicate="live in", object=obj,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_my_x_is(match: re.Match, text: str) -> Triplet | None:
    what = match.group(1).strip()
    value = match.group(2).strip().rstrip(".,!?")
    if what and value:
        return Triplet(subject=f"My {what}", predicate="is", object=value,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_my_favorite(match: re.Match, text: str) -> Triplet | None:
    what = match.group(1).strip()
    value = match.group(2).strip().rstrip(".,!?")
    if what and value:
        return Triplet(subject=f"My favorite {what}", predicate="is", object=value,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_x_is_my(match: re.Match, text: str) -> Triplet | None:
    who = match.group(1).strip()
    relation = match.group(2).strip().rstrip(".,!?")
    if who and relation:
        return Triplet(subject=who, predicate="is", object=f"my {relation}",
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_the_x_is(match: re.Match, text: str) -> Triplet | None:
    what = match.group(1).strip()
    value = match.group(2).strip().rstrip(".,!?")
    if what and value:
        return Triplet(subject=what, predicate="is", object=value,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_x_uses(match: re.Match, text: str) -> Triplet | None:
    subj = match.group(1).strip()
    verb = match.group(2).lower()
    obj = match.group(3).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate=verb, object=obj,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_x_is_y(match: re.Match, text: str) -> Triplet | None:
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj and len(subj) > 1 and len(obj) > 1:
        return Triplet(subject=subj, predicate="is", object=obj,
                       confidence=0.70, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


# --- Employment & Organizational patterns (new) ---

def _extract_works_at(match: re.Match, text: str) -> Triplet | None:
    """X works at/for Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="WORKS_AT", object=obj,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


def _extract_is_role_of(match: re.Match, text: str) -> Triplet | None:
    """X is the CEO/Manager/Director of Y"""
    subj = match.group(1).strip()
    obj = match.group(3).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="LEADS", object=obj,
                       confidence=0.92, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


def _extract_appositive_role(match: re.Match, text: str) -> Triplet | None:
    """X, CEO of Y (appositive)"""
    subj = match.group(1).strip()
    obj = match.group(3).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="LEADS", object=obj,
                       confidence=0.93, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


def _extract_inverted_role(match: re.Match, text: str) -> Triplet | None:
    """The CEO of Y, X"""
    org = match.group(2).strip().rstrip(",")
    person = match.group(3).strip().rstrip(".,!?")
    if person and org:
        return Triplet(subject=person, predicate="LEADS", object=org,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


def _extract_serves_as(match: re.Match, text: str) -> Triplet | None:
    """X serves/acts as CEO of Y"""
    subj = match.group(1).strip()
    obj = match.group(3).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="LEADS", object=obj,
                       confidence=0.92, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


def _extract_founded(match: re.Match, text: str) -> Triplet | None:
    """X founded/co-founded Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="FOUNDED", object=obj,
                       confidence=0.92, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


def _extract_founded_by(match: re.Match, text: str) -> Triplet | None:
    """Y, founded/established by X"""
    person = match.group(1).strip().rstrip(".,!?")
    # The org is captured before the pattern in context; use text before match
    org_end = match.start()
    org_text = text[max(0, org_end - 60):org_end].strip().rstrip(",;: ")
    # Take the last proper noun sequence
    org_words = org_text.split()
    org_parts = []
    for w in reversed(org_words):
        if w[0:1].isupper() or w.lower() in ("of", "the", "and", "&"):
            org_parts.insert(0, w)
        else:
            break
    org = " ".join(org_parts).strip()
    if person and org:
        return Triplet(subject=person, predicate="FOUNDED", object=org,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


def _extract_em_dash_role(match: re.Match, text: str) -> Triplet | None:
    """X — CEO/Founder"""
    subj = match.group(1).strip()
    role = match.group(2).strip().rstrip(".,!?")
    if subj and role:
        return Triplet(subject=subj, predicate="HAS_ROLE", object=role,
                       confidence=0.88, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "role"})
    return None


def _extract_led_by(match: re.Match, text: str) -> Triplet | None:
    """led/managed by X"""
    person = match.group(1).strip().rstrip(".,!?")
    if person:
        return Triplet(subject=person, predicate="LEADS", object="[context]",
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person"})
    return None


def _extract_joined_as(match: re.Match, text: str) -> Triplet | None:
    """X joined/appointed as CEO of Y"""
    subj = match.group(1).strip()
    obj = match.group(3).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="LEADS", object=obj,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


def _extract_reports_to(match: re.Match, text: str) -> Triplet | None:
    """X reports to Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="REPORTS_TO", object=obj,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "person"})
    return None


def _extract_manages(match: re.Match, text: str) -> Triplet | None:
    """X manages/supervises Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="MANAGES", object=obj,
                       confidence=0.88, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person"})
    return None


def _extract_vp_at(match: re.Match, text: str) -> Triplet | None:
    """X, VP of Engineering at Y"""
    subj = match.group(1).strip()
    org = match.group(2).strip().rstrip(".,!?")
    if subj and org:
        return Triplet(subject=subj, predicate="WORKS_AT", object=org,
                       confidence=0.92, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "organization"})
    return None


# --- Location patterns ---

def _extract_located_in(match: re.Match, text: str) -> Triplet | None:
    """X based/located/headquartered in Y"""
    subj = match.group(1).strip()
    loc = match.group(2).strip().rstrip(".,!?")
    if subj and loc:
        return Triplet(subject=subj, predicate="LOCATED_IN", object=loc,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"object_label": "location"})
    return None


def _extract_has_office(match: re.Match, text: str) -> Triplet | None:
    """X has offices/operations in Y"""
    subj = match.group(1).strip()
    loc = match.group(2).strip().rstrip(".,!?")
    if subj and loc:
        return Triplet(subject=subj, predicate="HAS_OFFICE_IN", object=loc,
                       confidence=0.88, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"object_label": "location"})
    return None


def _extract_position_at(match: re.Match, text: str) -> Triplet | None:
    """Customer Support Manager at CommerceFlow"""
    role = match.group(1).strip()
    org = match.group(2).strip().rstrip(".,!?")
    if role and org:
        return Triplet(subject=role, predicate="POSITION_AT", object=org,
                       confidence=0.88, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "role", "object_label": "organization"})
    return None


# --- E-Commerce & Product patterns ---

def _extract_has_price(match: re.Match, text: str) -> Triplet | None:
    """X costs/priced at $Y"""
    subj = match.group(1).strip()
    price = match.group(2).strip().rstrip(".,!?")
    if subj and price:
        return Triplet(subject=subj, predicate="HAS_PRICE", object=price,
                       confidence=0.92, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "product", "object_label": "money"})
    return None


def _extract_sold_by(match: re.Match, text: str) -> Triplet | None:
    """X sold by Y"""
    subj = match.group(1).strip()
    seller = match.group(2).strip().rstrip(".,!?")
    if subj and seller:
        return Triplet(subject=subj, predicate="SOLD_BY", object=seller,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "product", "object_label": "organization"})
    return None


def _extract_ordered(match: re.Match, text: str) -> Triplet | None:
    """X ordered/purchased/bought Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="ORDERED", object=obj,
                       confidence=0.88, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "product"})
    return None


def _extract_in_category(match: re.Match, text: str) -> Triplet | None:
    """X belongs to category Y"""
    subj = match.group(1).strip()
    cat = match.group(2).strip().rstrip(".,!?")
    if subj and cat:
        return Triplet(subject=subj, predicate="IN_CATEGORY", object=cat,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "product", "object_label": "category"})
    return None


def _extract_supplied_by(match: re.Match, text: str) -> Triplet | None:
    """X supplied by/shipped from Y"""
    subj = match.group(1).strip()
    supplier = match.group(3).strip().rstrip(".,!?")
    if subj and supplier:
        return Triplet(subject=subj, predicate="SUPPLIED_BY", object=supplier,
                       confidence=0.87, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


# --- Technical patterns ---

def _extract_uses_tech(match: re.Match, text: str) -> Triplet | None:
    """X uses/requires/depends on Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        predicate = "USES"
        return Triplet(subject=subj, predicate=predicate, object=obj,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_used_for(match: re.Match, text: str) -> Triplet | None:
    """will use X for Y"""
    tool = match.group(1).strip()
    purpose = match.group(2).strip().rstrip(".,!?")
    if tool and purpose:
        return Triplet(subject=tool, predicate="USED_FOR", object=purpose,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


def _extract_version(match: re.Match, text: str) -> Triplet | None:
    """X version Y"""
    subj = match.group(1).strip()
    ver = match.group(2).strip().rstrip(".,!?")
    if subj and ver:
        return Triplet(subject=subj, predicate="HAS_VERSION", object=ver,
                       confidence=0.92, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


# --- Financial patterns ---

def _extract_paid(match: re.Match, text: str) -> Triplet | None:
    """X paid $Y"""
    subj = match.group(1).strip()
    amount = match.group(2).strip().rstrip(".,!?")
    if subj and amount:
        return Triplet(subject=subj, predicate="PAID", object=amount,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "person", "object_label": "money"})
    return None


def _extract_invoiced(match: re.Match, text: str) -> Triplet | None:
    """Invoice X for Y"""
    invoice = match.group(1).strip()
    recipient = match.group(2).strip().rstrip(".,!?")
    if invoice and recipient:
        return Triplet(subject=invoice, predicate="INVOICED_TO", object=recipient,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0))
    return None


# --- General business patterns ---

def _extract_owns(match: re.Match, text: str) -> Triplet | None:
    """X owns/acquired/bought out Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="OWNS", object=obj,
                       confidence=0.90, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "organization", "object_label": "organization"})
    return None


def _extract_partners(match: re.Match, text: str) -> Triplet | None:
    """X partnered with Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="PARTNERS_WITH", object=obj,
                       confidence=0.88, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "organization", "object_label": "organization"})
    return None


def _extract_competes(match: re.Match, text: str) -> Triplet | None:
    """X competes with Y"""
    subj = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if subj and obj:
        return Triplet(subject=subj, predicate="COMPETES_WITH", object=obj,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "organization", "object_label": "organization"})
    return None


# --- Departments & Positions ---

def _extract_dept_handles(match: re.Match, text: str) -> Triplet | None:
    """X Department handles/manages Y"""
    dept = match.group(1).strip()
    obj = match.group(2).strip().rstrip(".,!?")
    if dept and obj:
        return Triplet(subject=dept, predicate="HANDLES", object=obj,
                       confidence=0.85, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "department"})
    return None


def _extract_dept_part_of(match: re.Match, text: str) -> Triplet | None:
    """Y's X Department"""
    org = match.group(1).strip().rstrip("'s\u2019s")
    dept = match.group(2).strip().rstrip(".,!?")
    if org and dept:
        return Triplet(subject=dept, predicate="PART_OF", object=org,
                       confidence=0.88, source_span=(match.start(), match.end()),
                       source_text=match.group(0),
                       metadata={"subject_label": "department", "object_label": "organization"})
    return None


# ============================================================
# Pattern registry
# ============================================================

# Proper noun sequence for subject capture
_PN = r"([A-Z][a-zA-Z]+(?:\s+(?:[A-Z][a-zA-Z]+|of|the|and|&))*)"
# Role titles
_ROLE = r"(?:CEO|CTO|CFO|COO|CMO|CIO|CISO|CPO|President|Founder|Co-Founder|" \
        r"Director|Manager|Head|Lead|Chief|Chairman|Partner|VP|SVP|EVP|" \
        r"Vice\s+President|General\s+Manager|Managing\s+Director)"

PATTERNS: list[ConversationalPattern] = [
    # --- Conversational (original 10, kept) ---
    ConversationalPattern(
        name="i_prefer",
        regex=re.compile(r"\bI\s+(prefer|like|love|enjoy|use|want|need)\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_i_prefer, confidence=0.90,
    ),
    ConversationalPattern(
        name="i_am",
        regex=re.compile(r"\bI(?:'m|\s+am)\s+(?:a\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_i_am, confidence=0.90,
    ),
    ConversationalPattern(
        name="i_work",
        regex=re.compile(r"\bI\s+work\s+(at|for)\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_i_work, confidence=0.90,
    ),
    ConversationalPattern(
        name="i_live",
        regex=re.compile(r"\bI\s+live\s+in\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_i_live, confidence=0.90,
    ),
    ConversationalPattern(
        name="my_favorite",
        regex=re.compile(r"\bMy\s+favorite\s+(\w+)\s+is\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_my_favorite, confidence=0.90,
    ),
    ConversationalPattern(
        name="my_x_is",
        regex=re.compile(r"\bMy\s+(\w+(?:\s+\w+)?)\s+is\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_my_x_is, confidence=0.90,
    ),
    ConversationalPattern(
        name="x_is_my",
        regex=re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+is\s+my\s+(.+?)(?:\.|$)"),
        extractor=_extract_x_is_my, confidence=0.85,
    ),
    ConversationalPattern(
        name="the_x_is",
        regex=re.compile(r"\bThe\s+(\w+(?:\s+\w+)?)\s+is\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_the_x_is, confidence=0.85,
    ),
    ConversationalPattern(
        name="x_uses_conv",
        regex=re.compile(r"\b(?:my\s+)?(\w+(?:\s+project)?)\s+(uses|prefers|requires)\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_x_uses, confidence=0.85,
    ),
    # --- Employment & Organizational ---
    ConversationalPattern(
        name="works_at",
        regex=re.compile(rf"\b{_PN}\s+(?:works?\s+(?:at|for))\s+{_PN}"),
        extractor=_extract_works_at, confidence=0.90,
    ),
    ConversationalPattern(
        name="is_role_of",
        regex=re.compile(rf"\b{_PN}\s+is\s+(?:the\s+)?({_ROLE})\s+(?:of|at)\s+{_PN}"),
        extractor=_extract_is_role_of, confidence=0.92,
    ),
    ConversationalPattern(
        name="appositive_role",
        regex=re.compile(rf"\b{_PN},\s*({_ROLE})\s+(?:of|at)\s+{_PN}"),
        extractor=_extract_appositive_role, confidence=0.93,
    ),
    ConversationalPattern(
        name="inverted_role",
        regex=re.compile(rf"\b(?:The\s+)?({_ROLE})\s+of\s+{_PN},\s*{_PN}"),
        extractor=_extract_inverted_role, confidence=0.90,
    ),
    ConversationalPattern(
        name="serves_as",
        regex=re.compile(rf"\b{_PN}\s+(?:serves?|acts?)\s+as\s+({_ROLE})\s+(?:of|at)\s+{_PN}"),
        extractor=_extract_serves_as, confidence=0.92,
    ),
    ConversationalPattern(
        name="founded",
        regex=re.compile(rf"\b{_PN}\s+(?:(?:co-)?founded|established)\s+{_PN}"),
        extractor=_extract_founded, confidence=0.92,
    ),
    ConversationalPattern(
        name="founded_by",
        regex=re.compile(r"\b(?:founded|established|co-founded)\s+by\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)"),
        extractor=_extract_founded_by, confidence=0.85,
    ),
    ConversationalPattern(
        name="em_dash_role",
        regex=re.compile(rf"\b{_PN}\s*[\u2014\u2013—–-]+\s*({_ROLE})"),
        extractor=_extract_em_dash_role, confidence=0.88,
    ),
    ConversationalPattern(
        name="led_by",
        regex=re.compile(rf"\b(?:[Ll]ed|[Mm]anaged|[Hh]eaded|[Dd]irected)\s+by\s+{_PN}"),
        extractor=_extract_led_by, confidence=0.85,
    ),
    ConversationalPattern(
        name="joined_as",
        regex=re.compile(rf"\b{_PN}\s+(?:joined|appointed)\s+(?:as\s+)?({_ROLE})\s+(?:of|at)\s+{_PN}"),
        extractor=_extract_joined_as, confidence=0.90,
    ),
    ConversationalPattern(
        name="reports_to",
        regex=re.compile(rf"\b{_PN}\s+reports?\s+to\s+{_PN}"),
        extractor=_extract_reports_to, confidence=0.90,
    ),
    ConversationalPattern(
        name="manages",
        regex=re.compile(rf"\b{_PN}\s+(?:manages?|supervises?)\s+{_PN}"),
        extractor=_extract_manages, confidence=0.88,
    ),
    ConversationalPattern(
        name="vp_at",
        regex=re.compile(rf"\b{_PN},\s*(?:VP|SVP|EVP|Vice\s+President)\s+of\s+\w+(?:\s+\w+)?\s+at\s+{_PN}"),
        extractor=_extract_vp_at, confidence=0.92,
    ),

    # --- Location ---
    ConversationalPattern(
        name="located_in",
        regex=re.compile(rf"\b{_PN}\s+(?:(?:is\s+)?(?:based|located|headquartered))\s+in\s+{_PN}"),
        extractor=_extract_located_in, confidence=0.90,
    ),
    ConversationalPattern(
        name="has_office",
        regex=re.compile(rf"\b{_PN}\s+(?:has\s+(?:offices?|operations?|branches?))\s+in\s+{_PN}"),
        extractor=_extract_has_office, confidence=0.88,
    ),
    ConversationalPattern(
        name="position_at",
        regex=re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z]?[a-zA-Z]+)*\s+(?:Manager|Director|Lead|Head|Officer|Coordinator|Analyst|Engineer|Specialist|Supervisor))\s+at\s+([A-Z][a-zA-Z]+(?:\s+[A-Z]?[a-zA-Z]+)*)"),
        extractor=_extract_position_at, confidence=0.88,
    ),

    # --- E-Commerce & Products ---
    ConversationalPattern(
        name="has_price",
        regex=re.compile(r"\b(.+?)\s+(?:costs?|priced\s+at|retails?\s+(?:at|for))\s+(\$[\d,.]+(?:\s*(?:per|each|/\w+))?)", re.IGNORECASE),
        extractor=_extract_has_price, confidence=0.92,
    ),
    ConversationalPattern(
        name="sold_by",
        regex=re.compile(rf"\b(.+?)\s+(?:sold|distributed|offered)\s+by\s+{_PN}"),
        extractor=_extract_sold_by, confidence=0.85,
    ),
    ConversationalPattern(
        name="ordered",
        regex=re.compile(rf"\b{_PN}\s+(?:ordered|purchased|bought)\s+(.+?)(?:\.|$)"),
        extractor=_extract_ordered, confidence=0.88,
    ),
    ConversationalPattern(
        name="in_category",
        regex=re.compile(r"\b(.+?)\s+belongs?\s+to\s+(?:the\s+)?(?:category\s+)?(.+?)(?:\s+category)?(?:\.|$)", re.IGNORECASE),
        extractor=_extract_in_category, confidence=0.85,
    ),
    ConversationalPattern(
        name="supplied_by",
        regex=re.compile(r"\b(.+?)\s+(supplied\s+by|shipped\s+from)\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_supplied_by, confidence=0.87,
    ),

    # --- Technical ---
    ConversationalPattern(
        name="uses_tech",
        regex=re.compile(rf"\b{_PN}\s+(?:uses?|utilizes?|requires?|depends?\s+on)\s+(.+?)(?:\.|$)"),
        extractor=_extract_uses_tech, confidence=0.85,
    ),
    ConversationalPattern(
        name="used_for",
        regex=re.compile(r"\b(?:will\s+)?use\s+(.+?)\s+for\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_used_for, confidence=0.85,
    ),
    ConversationalPattern(
        name="version",
        regex=re.compile(r"\b(\w+(?:\s+\w+)?)\s+(?:version|v\.?|ver\.?)\s*([\d]+(?:\.[\d]+)*)", re.IGNORECASE),
        extractor=_extract_version, confidence=0.92,
    ),

    # --- Financial ---
    ConversationalPattern(
        name="paid",
        regex=re.compile(rf"\b{_PN}\s+paid\s+(\$[\d,.]+(?:\s*(?:million|billion|k|m|b))?)"),
        extractor=_extract_paid, confidence=0.90,
    ),
    ConversationalPattern(
        name="invoiced",
        regex=re.compile(r"\bInvoice\s+(.+?)\s+for\s+(.+?)(?:\.|$)", re.IGNORECASE),
        extractor=_extract_invoiced, confidence=0.90,
    ),

    # --- General Business ---
    ConversationalPattern(
        name="owns",
        regex=re.compile(rf"\b{_PN}\s+(?:owns?|acquired|bought\s+out)\s+{_PN}"),
        extractor=_extract_owns, confidence=0.90,
    ),
    ConversationalPattern(
        name="partners",
        regex=re.compile(rf"\b{_PN}\s+partnered\s+with\s+{_PN}"),
        extractor=_extract_partners, confidence=0.88,
    ),
    ConversationalPattern(
        name="competes",
        regex=re.compile(rf"\b{_PN}\s+competes?\s+with\s+{_PN}"),
        extractor=_extract_competes, confidence=0.85,
    ),

    # --- Departments ---
    ConversationalPattern(
        name="dept_handles",
        regex=re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z]?[a-zA-Z]+)*)\s+(?:Department|Team|Division)\s+(?:handles?|manages?|oversees?)\s+(.+?)(?:\.|$)"),
        extractor=_extract_dept_handles, confidence=0.85,
    ),
    ConversationalPattern(
        name="dept_part_of",
        regex=re.compile(r"\b([A-Z][a-zA-Z]+(?:'s|\u2019s)?)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z]?[a-zA-Z]+)*\s+(?:Department|Team|Division))"),
        extractor=_extract_dept_part_of, confidence=0.88,
    ),

    # --- Generic catch-all (lowest priority, at end) ---
    ConversationalPattern(
        name="x_is_y",
        regex=re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+is\s+(?:a\s+)?([a-zA-Z][a-zA-Z\s]+?)(?:\.|$)"),
        extractor=_extract_x_is_y, confidence=0.70,
    ),
]


# ============================================================
# Entity detection patterns
# ============================================================

ENTITY_PATTERNS: list[EntityPattern] = [
    # Company suffixes
    EntityPattern(
        name="company_suffix",
        regex=re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Inc|Corp|LLC|Ltd|Co|Group|Holdings|Solutions|Systems|Technologies|Enterprises|Partners|Associates|International|Global|Services|Labs|Studios|Ventures|Capital)\.?)\b"),
        label="organization",
        group=1,
        confidence=0.92,
    ),
    # Quoted product/brand names
    EntityPattern(
        name="quoted_name",
        regex=re.compile(r'"([A-Z][a-zA-Z]+(?:\s+[A-Z]?[a-zA-Z]+)*)"'),
        label="product",
        group=1,
        confidence=0.90,
    ),
    # "the X app/platform/service/tool/software"
    EntityPattern(
        name="product_pattern",
        regex=re.compile(r"\bthe\s+([A-Z][a-zA-Z]+(?:\s+[A-Z]?[a-zA-Z]+)*)\s+(?:app|platform|service|tool|software|system|product)\b", re.IGNORECASE),
        label="product",
        group=1,
        confidence=0.88,
    ),
    # Role patterns: VP of X, Lead Developer, etc.
    EntityPattern(
        name="role_pattern",
        regex=re.compile(rf"\b({_ROLE})\b"),
        label="role",
        group=1,
        confidence=0.85,
    ),
    # Department patterns: X Department/Team/Division
    EntityPattern(
        name="department_pattern",
        regex=re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z]?[a-zA-Z]+)*\s+(?:Department|Team|Division|Group|Unit))\b"),
        label="department",
        group=1,
        confidence=0.88,
    ),
    # Technology terms: via/using/with/through/powered by X
    EntityPattern(
        name="tech_via",
        regex=re.compile(r"\b(?:via|using|with|through|powered\s+by|built\s+(?:with|on|using))\s+([A-Z][a-zA-Z]+(?:\s+[A-Z]?[a-zA-Z]+)*)\b"),
        label="technology",
        group=1,
        confidence=0.85,
    ),
]


# ============================================================
# PatternMatcher class
# ============================================================

class PatternMatcher:
    """Extract triplets and entities using regex patterns."""

    def __init__(self, patterns: list[ConversationalPattern] | None = None):
        self.patterns = patterns or PATTERNS

    def extract_triplets(self, text: str) -> list[Triplet]:
        """Extract triplets from text using patterns.

        Returns triplets sorted by position, with no overlapping spans.
        Higher-confidence patterns win over lower-confidence when spans overlap.
        """
        triplets: list[Triplet] = []

        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                triplet = pattern.extractor(match, text)
                if triplet is None:
                    continue

                span = triplet.source_span
                if span is None:
                    continue

                # Check overlap with existing triplets
                overlapping = [
                    (i, t) for i, t in enumerate(triplets)
                    if t.source_span and self._spans_overlap(span, t.source_span)
                ]

                if not overlapping:
                    triplets.append(triplet)
                    continue

                # If any overlapping triplet has higher confidence, skip this one
                dominated = any(
                    existing.confidence >= triplet.confidence
                    for _, existing in overlapping
                )
                if dominated:
                    continue

                # This triplet has higher confidence — remove overlapping ones
                remove_indices = {i for i, _ in overlapping}
                triplets = [t for i, t in enumerate(triplets) if i not in remove_indices]
                triplets.append(triplet)

        # Sort by position
        triplets.sort(key=lambda t: t.source_span[0] if t.source_span else 0)

        return triplets

    @staticmethod
    def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
        """Check if two spans overlap."""
        return a[0] < b[1] and b[0] < a[1]

    def extract_entities(self, text: str) -> list[EntitySpanResult]:
        """Extract entities using regex patterns (complement to GliNER).

        Detects company names, product names, roles, departments, and
        technology terms using high-precision patterns.
        """
        entities: list[EntitySpanResult] = []
        seen_spans: list[tuple[int, int]] = []

        # Pattern-based entity extraction
        for ep in ENTITY_PATTERNS:
            for match in ep.regex.finditer(text):
                entity_text = match.group(ep.group).strip()
                if not entity_text or len(entity_text) < 2:
                    continue
                span = (match.start(ep.group), match.end(ep.group))
                # Skip overlapping spans
                if any(spans_overlap_simple(span, s) for s in seen_spans):
                    continue
                seen_spans.append(span)
                entities.append(EntitySpanResult(
                    text=entity_text,
                    label=ep.label,
                    start=span[0],
                    end=span[1],
                    confidence=ep.confidence,
                ))

        # Known technology matching (case-insensitive)
        for match in re.finditer(r"\b(\w+)\b", text):
            word = match.group(1)
            if word.lower() in KNOWN_TECHNOLOGIES:
                span = (match.start(), match.end())
                if any(spans_overlap_simple(span, s) for s in seen_spans):
                    continue
                seen_spans.append(span)
                entities.append(EntitySpanResult(
                    text=word,
                    label="technology",
                    start=span[0],
                    end=span[1],
                    confidence=0.85,
                ))

        entities.sort(key=lambda e: e.start)
        return entities

    def add_pattern(self, pattern: ConversationalPattern) -> None:
        """Add a custom pattern."""
        self.patterns.append(pattern)


def spans_overlap_simple(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """Check if two spans overlap at all."""
    return a[0] < b[1] and b[0] < a[1]


# Default instance for convenience
default_matcher = PatternMatcher()


def extract_triplets_with_patterns(text: str) -> list[Triplet]:
    """Extract triplets using default pattern matcher."""
    return default_matcher.extract_triplets(text)
