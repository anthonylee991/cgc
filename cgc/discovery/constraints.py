"""Semantic type constraints and label normalization for graph extraction.

Provides:
- Label normalization: maps variant entity labels to canonical forms
- Predicate normalization: maps raw predicates to uppercase graph edge labels
- Semantic type constraints: validates that relations are sensible given entity types
- Invalid subject detection: prevents nonsensical relation actors
"""

from __future__ import annotations

# --- Label normalization ---
# Maps GliNER/GliREL output labels to canonical forms for graph consistency.

LABEL_MAPPING: dict[str, str] = {
    # Organizations
    "company": "organization",
    "brand": "organization",
    "startup": "organization",
    "supplier": "organization",
    "manufacturer": "organization",
    "bank": "organization",
    "fund": "organization",
    "hospital": "organization",
    "university": "organization",
    "institution": "organization",
    "agency": "organization",
    # People
    "client": "person",
    "customer": "person",
    "employee": "person",
    "researcher": "person",
    "patient": "person",
    "physician": "person",
    "attorney": "person",
    # Technology
    "framework": "technology",
    "library": "technology",
    "tool": "technology",
    "software": "technology",
    "programming language": "technology",
    "programming_language": "technology",
    "platform": "technology",
    "api": "technology",
    "protocol": "technology",
    # Location
    "city": "location",
    "country": "location",
    "address": "location",
    "warehouse": "location",
    "port": "location",
    # Organizational units
    "team": "department",
    # Roles
    "title": "role",
    # Financial
    "price": "money",
    "budget": "money",
    "revenue": "money",
    # Events
    "meeting": "event",
    "funding_round": "event",
    "campaign": "event",
    # Expansion pack: Accounting & Financial Reporting
    "reporting_entity": "organization",
    "auditor": "person",
    "accounting_standard": "regulation",
    # Expansion pack: Insurance
    "insurer": "organization",
    "policyholder": "person",
    "beneficiary": "person",
    "adjuster": "person",
    "premium": "money",
    "deductible": "money",
    # Expansion pack: Manufacturing & Engineering
    "quality_standard": "regulation",
    # Expansion pack: Marketing & Sales
    "competitor": "organization",
    "pricing_tier": "money",
    # Expansion pack: Energy & Environment
    "facility": "location",
    "environmental_regulation": "regulation",
    # Expansion pack: Software Engineering
    "service": "technology",
    "microservice": "technology",
    "endpoint": "technology",
    "database": "technology",
    "dependency": "technology",
}


def normalize_label(label: str) -> str:
    """Normalize an entity label to its canonical form."""
    lower = label.lower().strip()
    return LABEL_MAPPING.get(lower, lower)


# --- Predicate normalization ---
# Maps raw extracted predicates to uppercase graph edge labels.

PREDICATE_NORMALIZATION: dict[str, str] = {
    "founded": "FOUNDED",
    "co-founded": "FOUNDED",
    "leads": "LEADS",
    "led": "LEADS",
    "ceo of": "LEADS",
    "works at": "WORKS_AT",
    "works for": "WORKS_AT",
    "employed by": "WORKS_AT",
    "member of": "MEMBER_OF",
    "reports to": "REPORTS_TO",
    "manages": "MANAGES",
    "managed by": "MANAGES",
    "supervises": "MANAGES",
    "headquartered in": "LOCATED_IN",
    "located in": "LOCATED_IN",
    "based in": "LOCATED_IN",
    "uses": "USES",
    "requires": "USES",
    "depends on": "USES",
    "built with": "USES",
    "acquired": "ACQUIRED",
    "acquired by": "ACQUIRED",
    "owns": "OWNS",
    "owned by": "OWNS",
    "partner of": "PARTNERS_WITH",
    "partnered with": "PARTNERS_WITH",
    "competes with": "COMPETES_WITH",
    "provides": "PROVIDES",
    "developed by": "DEVELOPED_BY",
    "created by": "DEVELOPED_BY",
    "subsidiary of": "SUBSIDIARY_OF",
    "governs": "GOVERNS",
    "applies to": "APPLIES_TO",
    "purchased": "PURCHASED",
    "ordered": "ORDERED",
    "shipped to": "SHIPPED_TO",
    "sold by": "SOLD_BY",
    "paid": "PAID",
    # Accounting & Financial Reporting
    "reported in": "REPORTED_IN",
    "consolidates": "CONSOLIDATES",
    "recognized under": "RECOGNIZED_UNDER",
    "component of": "COMPONENT_OF",
    "measured at": "MEASURED_AT",
    "denominated in": "DENOMINATED_IN",
    "audited by": "AUDITED_BY",
    "for period": "FOR_PERIOD",
    # Insurance
    "insured by": "INSURED_BY",
    "covers": "COVERS",
    "filed by": "FILED_BY",
    "excludes": "EXCLUDES",
    "underwritten by": "UNDERWRITTEN_BY",
    "claimed against": "CLAIMED_AGAINST",
    "beneficiary of": "BENEFICIARY_OF",
    "adjusts": "ADJUSTS",
    "reinsured by": "REINSURED_BY",
    # Manufacturing & Engineering
    "manufactured by": "MANUFACTURED_BY",
    "meets standard": "MEETS_STANDARD",
    "tested with": "TESTED_WITH",
    "specified as": "SPECIFIED_AS",
    "supplied by": "SUPPLIED_BY",
    "assembled in": "ASSEMBLED_IN",
    "made from": "MADE_FROM",
    "produces": "PRODUCES",
    "inspected by": "INSPECTED_BY",
    # Marketing & Sales
    "targets": "TARGETS",
    "outperforms": "OUTPERFORMS",
    "distributed through": "DISTRIBUTED_THROUGH",
    "sponsors": "SPONSORS",
    "positions against": "POSITIONS_AGAINST",
    "launched in": "LAUNCHED_IN",
    # Energy & Environment
    "emits": "EMITS",
    "complies with": "COMPLIES_WITH",
    "targets reduction of": "TARGETS_REDUCTION_OF",
    "generates": "GENERATES",
    "certified by": "CERTIFIED_BY",
    "operates": "OPERATES",
    "monitors": "MONITORS",
    "regulated by": "REGULATED_BY",
    "funded by": "FUNDED_BY",
    # Software Engineering
    "implements": "IMPLEMENTS",
    "extends": "EXTENDS",
    "calls": "CALLS",
    "deployed to": "DEPLOYED_TO",
    "written in": "WRITTEN_IN",
    "exposes": "EXPOSES",
    "consumes": "CONSUMES",
    "migrated from": "MIGRATED_FROM",
    "replaces": "REPLACES",
    "compatible with": "COMPATIBLE_WITH",
    "vulnerable to": "VULNERABLE_TO",
    "maintains": "MAINTAINS",
}


def normalize_predicate(predicate: str) -> str:
    """Normalize a raw predicate to an uppercase graph edge label.

    Falls back to uppercased + underscored form if no mapping exists.
    """
    lower = predicate.lower().strip()
    if lower in PREDICATE_NORMALIZATION:
        return PREDICATE_NORMALIZATION[lower]
    # Fallback: uppercase, replace spaces with underscores, strip non-alnum
    import re
    cleaned = re.sub(r"[^a-zA-Z0-9\s_]", "", lower)
    cleaned = re.sub(r"\s+", "_", cleaned).upper()
    return cleaned[:50] if cleaned else "RELATED_TO"


# --- Semantic type constraints ---
# Each entry maps a relation label to (valid_head_types, valid_tail_types).
# None means any type is acceptable for that position.

SEMANTIC_CONSTRAINTS: dict[str, tuple[set[str] | None, set[str] | None]] = {
    # Leadership/Founding
    "founded": ({"person"}, {"organization", "company", "startup"}),
    "leads": ({"person"}, {"organization", "company", "department", "team"}),
    "CEO of": ({"person"}, {"organization", "company"}),
    "works at": ({"person"}, {"organization", "company"}),
    "member of": ({"person"}, {"organization", "company", "team", "department"}),
    "reports to": ({"person"}, {"person"}),
    "manages": ({"person"}, {"person", "team", "department", "project"}),
    # Location
    "headquartered in": ({"organization", "company", "startup"}, {"location", "city", "country"}),
    "located in": (None, {"location", "city", "country", "address"}),
    "based in": (None, {"location", "city", "country"}),
    # Business
    "acquired": ({"organization", "company", "investor"}, {"organization", "company", "startup"}),
    "subsidiary of": ({"organization", "company"}, {"organization", "company"}),
    "owns": ({"organization", "company", "person"}, {"organization", "company", "product"}),
    "partner of": ({"organization", "company"}, {"organization", "company"}),
    "competes with": ({"organization", "company"}, {"organization", "company"}),
    # Technical
    "uses": ({"organization", "company", "product", "project"}, {"technology", "product", "framework"}),
    "built with": ({"product", "project"}, {"technology", "framework"}),
    "developed by": ({"product", "technology"}, {"person", "organization", "company"}),
    "provides": ({"organization", "company"}, {"product", "service", "technology"}),
    # E-commerce
    "purchased": ({"person", "customer"}, {"product", "item"}),
    "ordered": ({"person", "customer"}, {"product", "item"}),
    "shipped to": ({"product", "order"}, {"location", "address"}),
    # Policy/Governance
    "governs": ({"policy", "regulation"}, {"department", "organization", "process"}),
    "applies to": ({"policy", "regulation"}, {"person", "organization", "department"}),
    # Accounting & Financial Reporting
    "reported in": ({"line_item", "asset", "liability", "equity_component"}, {"financial_statement"}),
    "consolidates": ({"reporting_entity", "company"}, {"reporting_entity", "company"}),
    "recognized under": ({"asset", "liability", "line_item"}, {"accounting_standard"}),
    "component of": ({"line_item", "asset", "liability"}, {"line_item", "financial_statement"}),
    "measured at": ({"asset", "liability"}, {"accounting_policy", "money"}),
    "denominated in": ({"money", "asset", "liability"}, {"currency"}),
    "audited by": ({"reporting_entity", "company"}, {"auditor", "company", "person"}),
    "for period": ({"financial_statement", "reporting_entity"}, {"reporting_period", "date"}),
    # Insurance
    "insured by": ({"policyholder", "person", "company"}, {"insurer", "company"}),
    "covers": ({"policy", "coverage_type"}, {"peril", "person", "company", "policyholder"}),
    "filed by": ({"claim"}, {"policyholder", "person", "company"}),
    "excludes": ({"policy", "coverage_type"}, {"exclusion", "peril"}),
    "underwritten by": ({"policy"}, {"insurer", "company", "person"}),
    "claimed against": ({"claim"}, {"policy", "insurer", "company"}),
    "beneficiary of": ({"beneficiary", "person"}, {"policy"}),
    "reinsured by": ({"insurer", "company"}, {"insurer", "company"}),
    # Manufacturing & Engineering
    "meets standard": ({"part", "assembly", "process", "material"}, {"quality_standard", "specification"}),
    "tested with": ({"part", "assembly", "material"}, {"measurement", "process", "machine"}),
    "specified as": ({"part", "material", "tolerance"}, {"specification", "measurement"}),
    "assembled in": ({"part", "assembly"}, {"machine", "location", "company"}),
    "made from": ({"part", "assembly"}, {"material"}),
    "produces": ({"machine", "process", "company"}, {"part", "assembly", "defect"}),
    "inspected by": ({"part", "assembly"}, {"person", "company"}),
    # Marketing & Sales
    "targets": ({"campaign", "brand", "company"}, {"target_audience", "market_segment"}),
    "outperforms": ({"brand", "company", "product"}, {"competitor", "brand", "company", "product"}),
    "distributed through": ({"product", "brand"}, {"channel", "company"}),
    "sponsors": ({"company", "brand"}, {"campaign", "person", "event"}),
    "positions against": ({"brand", "company", "product"}, {"competitor", "brand", "company", "product"}),
    # Energy & Environment
    "emits": ({"facility", "company", "process"}, {"emission", "pollutant"}),
    "complies with": ({"facility", "company"}, {"environmental_regulation"}),
    "targets reduction of": ({"company", "facility"}, {"emission", "pollutant", "target"}),
    "generates": ({"facility", "energy_source", "renewable_source"}, {"emission", "energy_source", "money"}),
    "certified by": ({"facility", "company"}, {"company", "person"}),
    "operates": ({"company", "person"}, {"facility", "energy_source", "renewable_source"}),
    "monitors": ({"company", "person", "facility"}, {"emission", "metric", "pollutant"}),
    "regulated by": ({"facility", "company", "emission"}, {"environmental_regulation", "company"}),
    # Software Engineering
    "depends on": ({"service", "microservice", "library", "repository"}, {"library", "dependency", "framework", "service"}),
    "implements": ({"service", "microservice", "library"}, {"api", "protocol", "architecture_pattern"}),
    "extends": ({"service", "microservice", "library"}, {"library", "framework", "api"}),
    "calls": ({"service", "microservice", "endpoint"}, {"service", "microservice", "endpoint", "api"}),
    "deployed to": ({"service", "microservice", "repository"}, {"environment"}),
    "written in": ({"service", "microservice", "library", "repository"}, {"programming_language"}),
    "exposes": ({"service", "microservice"}, {"endpoint", "api"}),
    "consumes": ({"service", "microservice"}, {"api", "endpoint", "service"}),
    "migrated from": ({"service", "microservice", "database"}, {"service", "database", "framework"}),
    "replaces": ({"service", "microservice", "library"}, {"service", "microservice", "library"}),
    "compatible with": ({"library", "framework", "service"}, {"library", "framework", "version"}),
    "vulnerable to": ({"service", "library", "dependency"}, {"vulnerability"}),
}

# Entity types that should never be relation subjects
INVALID_SUBJECT_TYPES: frozenset[str] = frozenset({
    "date", "money", "price", "quantity", "percentage",
    "timestamp", "budget", "revenue",
})


def validate_relation(
    head_label: str,
    relation: str,
    tail_label: str,
) -> bool:
    """Check if a relation is semantically valid given entity types.

    Returns True if the relation passes type constraints, or if no
    constraints are defined for this relation (permissive by default).
    """
    head_norm = normalize_label(head_label)
    tail_norm = normalize_label(tail_label)
    relation_lower = relation.lower().strip()

    # Check if head is an invalid subject type
    if head_norm in INVALID_SUBJECT_TYPES:
        return False

    # Look up constraints
    if relation_lower not in SEMANTIC_CONSTRAINTS:
        return True  # No constraints defined = permissive

    valid_heads, valid_tails = SEMANTIC_CONSTRAINTS[relation_lower]

    if valid_heads is not None and head_norm not in valid_heads:
        return False
    if valid_tails is not None and tail_norm not in valid_tails:
        return False

    return True


def is_invalid_subject(entity_type: str) -> bool:
    """Check if an entity type cannot be a relation subject."""
    return normalize_label(entity_type) in INVALID_SUBJECT_TYPES
