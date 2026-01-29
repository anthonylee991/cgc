"""Exception classes for Context Graph Connector."""

from __future__ import annotations


class CGCError(Exception):
    """Base exception for all CGC errors."""

    pass


class SourceNotFoundError(CGCError):
    """Raised when a data source is not found."""

    def __init__(self, source_id: str):
        self.source_id = source_id
        super().__init__(f"Source not found: {source_id}")


class EntityNotFoundError(CGCError):
    """Raised when an entity (table, file, collection) is not found."""

    def __init__(self, source_id: str, entity: str):
        self.source_id = source_id
        self.entity = entity
        super().__init__(f"Entity not found: {entity} in source {source_id}")


class ConnectionError(CGCError):
    """Raised when connection to a data source fails."""

    def __init__(self, source_id: str, message: str):
        self.source_id = source_id
        super().__init__(f"Connection failed for {source_id}: {message}")


class QueryError(CGCError):
    """Raised when a query execution fails."""

    def __init__(self, source_id: str, query: str, message: str):
        self.source_id = source_id
        self.query = query
        super().__init__(f"Query failed on {source_id}: {message}")


class SchemaDiscoveryError(CGCError):
    """Raised when schema discovery fails."""

    def __init__(self, source_id: str, message: str):
        self.source_id = source_id
        super().__init__(f"Schema discovery failed for {source_id}: {message}")


class ChunkingError(CGCError):
    """Raised when chunking operation fails."""

    def __init__(self, source_id: str, entity: str, message: str):
        self.source_id = source_id
        self.entity = entity
        super().__init__(f"Chunking failed for {entity} in {source_id}: {message}")


class UnsupportedOperationError(CGCError):
    """Raised when an operation is not supported by an adapter."""

    def __init__(self, adapter: str, operation: str):
        self.adapter = adapter
        self.operation = operation
        super().__init__(f"Operation '{operation}' not supported by {adapter}")
