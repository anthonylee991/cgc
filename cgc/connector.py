"""Main Connector class - the primary interface for Context Graph Connector."""

from __future__ import annotations

import asyncio
from typing import Any

from cgc.adapters.base import DataSource, DiscoveryOptions, FirstN, HealthStatus
from cgc.core.chunk import Chunk, ChunkStrategy
from cgc.core.errors import SourceNotFoundError
from cgc.core.graph import RelationshipGraph
from cgc.core.query import Query, QueryResult, SqlQuery, SemanticQuery
from cgc.core.schema import FieldId, Schema
from cgc.core.triplet import Triplet
from cgc.discovery.engine import RelationshipDiscoveryEngine
# NOTE: extract_triplets is imported lazily in the method to avoid loading torch/spacy at startup


class Connector:
    """Main interface for Context Graph Connector.

    The Connector manages multiple data sources and provides a unified
    interface for:
    - Schema discovery
    - Querying
    - Chunking
    - Relationship graph construction
    - Cross-source operations

    Example:
        ```python
        async with Connector() as cgc:
            cgc.add_source(SqlAdapter("db", "postgresql://localhost/app"))
            cgc.add_source(FilesystemAdapter("docs", "./documents"))

            # Discover schemas
            await cgc.discover_all()

            # Query data
            result = await cgc.sql("db", "SELECT * FROM users LIMIT 10")

            # Get relationship graph
            graph = await cgc.graph()
        ```
    """

    def __init__(self, cache_path: str | None = None):
        """Initialize Connector.

        Args:
            cache_path: Optional path for SQLite cache (not yet implemented)
        """
        self._sources: dict[str, DataSource] = {}
        self._schemas: dict[str, Schema] = {}
        self._graph: RelationshipGraph | None = None
        self._discovery_engine = RelationshipDiscoveryEngine()
        self._cache_path = cache_path

    # === Source Management ===

    def add_source(self, source: DataSource) -> "Connector":
        """Add a data source.

        Args:
            source: DataSource instance to add

        Returns:
            Self for chaining
        """
        self._sources[source.source_id] = source
        # Invalidate graph cache
        self._graph = None
        return self

    def remove_source(self, source_id: str) -> bool:
        """Remove a data source.

        Args:
            source_id: ID of source to remove

        Returns:
            True if source was removed, False if not found
        """
        if source_id in self._sources:
            del self._sources[source_id]
            self._schemas.pop(source_id, None)
            self._graph = None
            return True
        return False

    @property
    def sources(self) -> list[str]:
        """List connected source IDs."""
        return list(self._sources.keys())

    def get_source(self, source_id: str) -> DataSource:
        """Get a specific source by ID.

        Args:
            source_id: Source identifier

        Returns:
            DataSource instance

        Raises:
            SourceNotFoundError: If source not found
        """
        if source_id not in self._sources:
            raise SourceNotFoundError(source_id)
        return self._sources[source_id]

    def has_source(self, source_id: str) -> bool:
        """Check if a source exists."""
        return source_id in self._sources

    # === Schema Discovery ===

    async def discover(
        self,
        source_id: str,
        options: DiscoveryOptions | None = None,
        refresh: bool = False,
    ) -> Schema:
        """Discover schema for a source.

        Args:
            source_id: Source identifier
            options: Discovery options
            refresh: Force refresh even if cached

        Returns:
            Discovered schema
        """
        # Check cache
        if not refresh and source_id in self._schemas:
            return self._schemas[source_id]

        # Discover
        source = self.get_source(source_id)
        schema = await source.discover_schema(options)

        # Cache
        self._schemas[source_id] = schema

        return schema

    async def discover_all(
        self,
        options: DiscoveryOptions | None = None,
        refresh: bool = False,
    ) -> dict[str, Schema]:
        """Discover schemas for all sources.

        Args:
            options: Discovery options (applied to all sources)
            refresh: Force refresh

        Returns:
            Dict mapping source_id to Schema
        """
        tasks = [
            self.discover(source_id, options, refresh)
            for source_id in self._sources
        ]
        schemas = await asyncio.gather(*tasks)
        return dict(zip(self._sources.keys(), schemas))

    async def schema(self, source_id: str) -> Schema:
        """Get schema for a source (discover if needed).

        Convenience method that ensures schema is available.
        """
        return await self.discover(source_id)

    # === Relationship Graph ===

    async def graph(self, refresh: bool = False) -> RelationshipGraph:
        """Get relationship graph across all sources.

        Args:
            refresh: Force re-discovery

        Returns:
            RelationshipGraph with all discovered relationships
        """
        if not refresh and self._graph:
            return self._graph

        # Discover all schemas first
        schemas = await self.discover_all()

        # Run discovery engine
        self._graph = self._discovery_engine.discover(list(schemas.values()))

        return self._graph

    # === Querying ===

    async def query(self, source_id: str, query: Query) -> QueryResult:
        """Execute a query against a source.

        Args:
            source_id: Source identifier
            query: Query object

        Returns:
            QueryResult
        """
        source = self.get_source(source_id)
        return await source.query(query)

    async def sql(self, source_id: str, sql: str, **params) -> QueryResult:
        """Execute a SQL query (convenience method).

        Args:
            source_id: Source identifier
            sql: SQL query string
            **params: Query parameters

        Returns:
            QueryResult
        """
        return await self.query(source_id, SqlQuery(sql=sql, params=params))

    async def vector_search(
        self,
        source_id: str,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        threshold: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a vector similarity search.

        Args:
            source_id: Source identifier (must be a VectorSource)
            collection: Collection/table to search
            query_vector: Query embedding vector
            top_k: Maximum results
            threshold: Minimum similarity score
            filter: Metadata filter

        Returns:
            QueryResult with similarity scores
        """
        return await self.query(
            source_id,
            SemanticQuery(
                collection=collection,
                query_vector=query_vector,
                top_k=top_k,
                threshold=threshold,
                filter=filter,
            ),
        )

    # === Chunking ===

    async def chunk(
        self,
        source_id: str,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk data from a source.

        Args:
            source_id: Source identifier
            entity: Entity (table, file) to chunk
            strategy: Chunking strategy

        Returns:
            List of chunks ready for LLM processing
        """
        source = self.get_source(source_id)
        return await source.chunk(entity, strategy)

    # === Sampling ===

    async def sample(
        self,
        source_id: str,
        entity: str,
        n: int = 5,
    ) -> list[dict[str, Any]]:
        """Sample data from a source.

        Args:
            source_id: Source identifier
            entity: Entity to sample from
            n: Number of samples

        Returns:
            List of sample records
        """
        source = self.get_source(source_id)
        return await source.sample(entity, FirstN(n))

    # === Cross-Source Operations ===

    async def find_related(
        self,
        field_id: FieldId,
        value: Any,
    ) -> list[dict[str, Any]]:
        """Find related records across sources.

        Given a field and value, find all related records via
        the relationship graph.

        Args:
            field_id: Starting field
            value: Value to search for

        Returns:
            List of related records with source info
        """
        graph = await self.graph()
        related = graph.related_to(field_id)

        results = []
        for rel in related:
            other_field = rel.other_side(field_id)
            if not other_field:
                continue

            # Query the related source
            from cgc.core.query import GetQuery

            try:
                source = self.get_source(other_field.source_id)
                result = await source.query(
                    GetQuery(
                        entity=other_field.entity,
                        key=other_field.field,
                        value=value,
                    )
                )

                for row in result.to_dicts():
                    results.append({
                        "source_id": other_field.source_id,
                        "entity": other_field.entity,
                        "relationship": rel.relationship_type.value,
                        "confidence": rel.confidence.value,
                        "record": row,
                    })
            except Exception:
                continue

        return results

    # === Triplet Extraction ===

    def extract_triplets(
        self,
        text: str,
        use_gliner: bool = True,
    ) -> list[Triplet]:
        """Extract triplets from text.

        Uses hybrid extraction (patterns + GliNER) to find
        subject-predicate-object relationships.

        Args:
            text: Input text
            use_gliner: Whether to use GliNER (higher recall, slower)

        Returns:
            List of extracted triplets
        """
        # Lazy import to avoid loading torch/spacy at startup
        from cgc.discovery.extractor import extract_triplets
        return extract_triplets(text, use_gliner=use_gliner)

    # === Health Checks ===

    async def health_check(self) -> dict[str, HealthStatus]:
        """Check health of all sources.

        Returns:
            Dict mapping source_id to HealthStatus
        """
        tasks = [source.health_check() for source in self._sources.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        health = {}
        for source_id, result in zip(self._sources.keys(), results):
            if isinstance(result, Exception):
                health[source_id] = HealthStatus(
                    healthy=False,
                    message=str(result),
                )
            else:
                health[source_id] = result

        return health

    async def health_check_source(self, source_id: str) -> HealthStatus:
        """Check health of a specific source."""
        source = self.get_source(source_id)
        return await source.health_check()

    # === Utilities ===

    def summary(self) -> str:
        """Generate compact summary for LLM context.

        Returns summary of all connected sources and their schemas.
        """
        lines = [f"Connected sources: {len(self._sources)}"]

        for source_id, schema in self._schemas.items():
            lines.append(f"\n{schema.to_compact()}")

        if self._graph:
            lines.append(f"\nRelationships: {len(self._graph.relationships)}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert connector state to dictionary."""
        return {
            "sources": list(self._sources.keys()),
            "schemas": {
                sid: schema.to_dict() for sid, schema in self._schemas.items()
            },
            "relationships": (
                self._graph.to_dict() if self._graph else {"relationships": [], "total": 0}
            ),
        }

    async def close(self) -> None:
        """Close all connections."""
        for source in self._sources.values():
            await source.close()

    async def __aenter__(self) -> "Connector":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


class ConnectorBuilder:
    """Builder for creating Connector instances.

    Provides a fluent interface for adding sources.

    Example:
        ```python
        connector = (
            ConnectorBuilder()
            .add_postgres("db", "postgresql://localhost/app")
            .add_filesystem("docs", "./documents")
            .add_qdrant("vectors", "http://localhost:6333")
            .build()
        )
        ```
    """

    def __init__(self):
        self._sources: list[DataSource] = []
        self._cache_path: str | None = None

    def add_source(self, source: DataSource) -> "ConnectorBuilder":
        """Add a generic data source."""
        self._sources.append(source)
        return self

    def add_postgres(
        self,
        source_id: str,
        connection_string: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a PostgreSQL source."""
        from cgc.adapters.sql import SqlAdapter

        self._sources.append(SqlAdapter(source_id, connection_string, **kwargs))
        return self

    def add_mysql(
        self,
        source_id: str,
        connection_string: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a MySQL source."""
        from cgc.adapters.sql import SqlAdapter

        self._sources.append(SqlAdapter(source_id, connection_string, **kwargs))
        return self

    def add_sqlite(
        self,
        source_id: str,
        path: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a SQLite source."""
        from cgc.adapters.sql import SqlAdapter

        self._sources.append(SqlAdapter(source_id, f"sqlite:///{path}", **kwargs))
        return self

    def add_filesystem(
        self,
        source_id: str,
        path: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a local filesystem source."""
        from cgc.adapters.filesystem import FilesystemAdapter

        self._sources.append(FilesystemAdapter(source_id, path, **kwargs))
        return self

    def add_pgvector(
        self,
        source_id: str,
        connection_string: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a pgvector source."""
        from cgc.adapters.vector.pgvector import PgVectorAdapter

        self._sources.append(PgVectorAdapter(source_id, connection_string, **kwargs))
        return self

    def add_qdrant(
        self,
        source_id: str,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a Qdrant source."""
        from cgc.adapters.vector.qdrant import QdrantAdapter

        self._sources.append(QdrantAdapter(source_id, url, api_key, **kwargs))
        return self

    def add_pinecone(
        self,
        source_id: str,
        api_key: str,
        index_name: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a Pinecone source."""
        from cgc.adapters.vector.pinecone import PineconeAdapter

        self._sources.append(PineconeAdapter(source_id, api_key, index_name, **kwargs))
        return self

    def add_mongodb_vector(
        self,
        source_id: str,
        connection_string: str,
        database: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a MongoDB Atlas Vector Search source."""
        from cgc.adapters.vector.mongodb import MongoVectorAdapter

        self._sources.append(
            MongoVectorAdapter(source_id, connection_string, database, **kwargs)
        )
        return self

    def with_cache(self, path: str) -> "ConnectorBuilder":
        """Set cache path for schema caching."""
        self._cache_path = path
        return self

    def build(self) -> Connector:
        """Build the Connector instance."""
        connector = Connector(cache_path=self._cache_path)
        for source in self._sources:
            connector.add_source(source)
        return connector
