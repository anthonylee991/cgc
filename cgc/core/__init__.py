"""Core types for Context Graph Connector."""

from cgc.core.chunk import (
    ByDocumentStrategy,
    ByPartitionStrategy,
    BySectionsStrategy,
    Chunk,
    ChunkMetadata,
    ChunkStrategy,
    FixedRowsStrategy,
    FixedTokensStrategy,
)
from cgc.core.errors import (
    CGCError,
    ConnectionError,
    EntityNotFoundError,
    QueryError,
    SourceNotFoundError,
)
from cgc.core.graph import (
    Confidence,
    InferenceMethod,
    Relationship,
    RelationshipGraph,
    RelationshipType,
)
from cgc.core.query import (
    AggregateQuery,
    GetQuery,
    PatternQuery,
    Query,
    QueryResult,
    SemanticQuery,
    SqlQuery,
    TraverseQuery,
)
from cgc.core.schema import (
    Cardinality,
    DataType,
    Entity,
    EntityType,
    Field,
    FieldId,
    Schema,
    SchemaStats,
    SourceType,
)
from cgc.core.triplet import Triplet

__all__ = [
    # Schema
    "Schema",
    "Entity",
    "Field",
    "FieldId",
    "SourceType",
    "EntityType",
    "DataType",
    "Cardinality",
    "SchemaStats",
    # Query
    "Query",
    "QueryResult",
    "SqlQuery",
    "GetQuery",
    "PatternQuery",
    "SemanticQuery",
    "AggregateQuery",
    "TraverseQuery",
    # Chunk
    "Chunk",
    "ChunkMetadata",
    "ChunkStrategy",
    "FixedRowsStrategy",
    "FixedTokensStrategy",
    "ByPartitionStrategy",
    "ByDocumentStrategy",
    "BySectionsStrategy",
    # Graph
    "Relationship",
    "RelationshipGraph",
    "RelationshipType",
    "Confidence",
    "InferenceMethod",
    # Triplet
    "Triplet",
    # Errors
    "CGCError",
    "SourceNotFoundError",
    "EntityNotFoundError",
    "ConnectionError",
    "QueryError",
]
