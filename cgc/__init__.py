"""Context Graph Connector - Programmatic data access for LLM agents."""

from cgc.connector import Connector, ConnectorBuilder
from cgc.core.chunk import Chunk, ChunkStrategy, FixedRowsStrategy, FixedTokensStrategy
from cgc.core.graph import Relationship, RelationshipGraph, RelationshipType
from cgc.core.query import GetQuery, PatternQuery, Query, QueryResult, SemanticQuery, SqlQuery
from cgc.core.schema import (
    DataType,
    Entity,
    EntityType,
    Field,
    FieldId,
    Schema,
    SourceType,
)
from cgc.core.triplet import Triplet
from cgc.session import Session, get_session, load_session, new_session, save_session

__version__ = "0.7.0"

__all__ = [
    # Main interface
    "Connector",
    "ConnectorBuilder",
    # Schema
    "Schema",
    "Entity",
    "Field",
    "FieldId",
    "SourceType",
    "EntityType",
    "DataType",
    # Query
    "Query",
    "QueryResult",
    "SqlQuery",
    "GetQuery",
    "PatternQuery",
    "SemanticQuery",
    # Chunk
    "Chunk",
    "ChunkStrategy",
    "FixedRowsStrategy",
    "FixedTokensStrategy",
    # Graph
    "Relationship",
    "RelationshipGraph",
    "RelationshipType",
    # Triplet
    "Triplet",
    # Session
    "Session",
    "get_session",
    "save_session",
    "load_session",
    "new_session",
]
