"""Core types for Context Graph Connector."""

from cgc.core.schema import (
    Schema,
    Entity,
    Field,
    FieldId,
    SourceType,
    EntityType,
    DataType,
    Cardinality,
    SchemaStats,
)
from cgc.core.query import (
    Query,
    QueryResult,
    SqlQuery,
    GetQuery,
    PatternQuery,
    SemanticQuery,
    AggregateQuery,
    TraverseQuery,
)
from cgc.core.chunk import (
    Chunk,
    ChunkMetadata,
    ChunkStrategy,
    FixedRowsStrategy,
    FixedTokensStrategy,
    ByPartitionStrategy,
    ByDocumentStrategy,
    BySectionsStrategy,
)
from cgc.core.graph import (
    Relationship,
    RelationshipGraph,
    RelationshipType,
    Confidence,
    InferenceMethod,
)
from cgc.core.triplet import Triplet
from cgc.core.errors import (
    CGCError,
    SourceNotFoundError,
    EntityNotFoundError,
    ConnectionError,
    QueryError,
)

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
