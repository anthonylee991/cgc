"""Relationship discovery engine for Context Graph Connector."""

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

# Lazy imports for extractor (avoids loading torch/spacy at import time)
# These are loaded on first access via __getattr__
_lazy_imports = {
    "HybridExtractor": "cgc.discovery.extractor",
    "extract_triplets": "cgc.discovery.extractor",
    "extract_triplets_batch": "cgc.discovery.extractor",
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
    # Patterns
    "PatternMatcher",
    "ConversationalPattern",
    "extract_triplets_with_patterns",
]
