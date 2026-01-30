"""Relationship discovery engine for Context Graph Connector.

v0.2.0: Multi-stage extraction pipeline with:
- 50+ regex patterns (high precision)
- GliNER entity extraction (medium model, batched labels)
- GliREL relation extraction (type-constrained)
- E5 embedding domain routing (11 industry packs)
- Structured data extraction (hub-and-spoke)
- Semantic type constraints and garbage filtering
"""

from cgc.discovery.engine import (
    RelationshipDiscoveryEngine,
    InferenceRule,
    NamingConventionRule,
    CardinalityMatchRule,
    ValueOverlapRule,
    discover_relationships,
    extract_relationships_from_text,
)
from cgc.discovery.patterns import (
    PatternMatcher,
    ConversationalPattern,
    extract_triplets_with_patterns,
)
from cgc.discovery.filters import (
    is_garbage_entity,
    filter_triplets,
    deduplicate_triplets,
)
from cgc.discovery.constraints import (
    normalize_label,
    normalize_predicate,
    validate_relation,
)
from cgc.discovery.industry_packs import (
    IndustryPack,
    get_pack,
    get_all_packs,
    PACK_REGISTRY,
)

# Lazy imports for heavy modules (avoids loading torch/spacy at import time)
_lazy_imports = {
    "HybridExtractor": "cgc.discovery.extractor",
    "extract_triplets": "cgc.discovery.extractor",
    "extract_triplets_batch": "cgc.discovery.extractor",
    "UnifiedExtractor": "cgc.discovery.unified",
    "DomainRouter": "cgc.discovery.router",
    "create_router": "cgc.discovery.router",
    "GliNERExtractor": "cgc.discovery.gliner",
    "GliRELExtractor": "cgc.discovery.glirel",
    "StructuredExtractor": "cgc.discovery.structured",
}


def __getattr__(name: str):
    """Lazy import for heavy modules."""
    if name in _lazy_imports:
        import importlib
        module = importlib.import_module(_lazy_imports[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Engine
    "RelationshipDiscoveryEngine",
    "InferenceRule",
    "NamingConventionRule",
    "CardinalityMatchRule",
    "ValueOverlapRule",
    "discover_relationships",
    "extract_relationships_from_text",
    # Extractor (lazy loaded)
    "HybridExtractor",
    "extract_triplets",
    "extract_triplets_batch",
    # Unified pipeline (lazy loaded)
    "UnifiedExtractor",
    "DomainRouter",
    "create_router",
    "GliNERExtractor",
    "GliRELExtractor",
    "StructuredExtractor",
    # Patterns
    "PatternMatcher",
    "ConversationalPattern",
    "extract_triplets_with_patterns",
    # Filters & constraints
    "is_garbage_entity",
    "filter_triplets",
    "deduplicate_triplets",
    "normalize_label",
    "normalize_predicate",
    "validate_relation",
    # Industry packs
    "IndustryPack",
    "get_pack",
    "get_all_packs",
    "PACK_REGISTRY",
]
