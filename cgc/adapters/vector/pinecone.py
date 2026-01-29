"""Pinecone vector database adapter."""

from __future__ import annotations

import time
from typing import Any

from cgc.adapters.base import DiscoveryOptions, FirstN, HealthStatus, SampleStrategy
from cgc.adapters.vector.base import VectorSource
from cgc.core.chunk import Chunk, ChunkMetadata, ChunkStrategy, FixedRowsStrategy
from cgc.core.query import Query, QueryResult, SemanticQuery
from cgc.core.schema import (
    DataType,
    Entity,
    EntityType,
    Field,
    Schema,
    SchemaStats,
    SourceType,
)


class PineconeAdapter(VectorSource):
    """Adapter for Pinecone vector database.

    Features:
    - Fully managed vector database
    - Automatic scaling and high availability
    - Metadata filtering
    - Namespace support for multi-tenancy
    """

    def __init__(
        self,
        source_id: str,
        api_key: str,
        index_name: str,
        environment: str | None = None,
    ):
        """Initialize Pinecone adapter.

        Args:
            source_id: Unique identifier for this source
            api_key: Pinecone API key
            index_name: Name of the Pinecone index
            environment: Pinecone environment (for legacy API)
        """
        from pinecone import Pinecone

        self._source_id = source_id
        self._index_name = index_name
        self._client = Pinecone(api_key=api_key)
        self._index = self._client.Index(index_name)

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> SourceType:
        return SourceType.PINECONE

    async def discover_schema(
        self,
        options: DiscoveryOptions | None = None,
    ) -> Schema:
        """Discover Pinecone index schema."""
        options = options or DiscoveryOptions()
        entities = []

        # Get index stats
        stats = self._index.describe_index_stats()

        # Each namespace is treated as an entity
        namespaces = stats.namespaces or {"": stats}

        for namespace, ns_stats in namespaces.items():
            ns_name = namespace or "_default"

            if options.entities and ns_name not in options.entities:
                continue

            # Basic fields
            fields = [
                Field(name="id", data_type=DataType.STRING, is_primary_key=True),
                Field(
                    name="vector",
                    data_type=DataType.VECTOR,
                    original_type=f"vector[{stats.dimension}]",
                ),
                Field(name="metadata", data_type=DataType.JSON),
            ]

            entity = Entity(
                name=ns_name,
                entity_type=EntityType.INDEX,
                fields=fields,
                row_count=ns_stats.vector_count if hasattr(ns_stats, 'vector_count') else None,
                metadata={"namespace": namespace, "dimension": stats.dimension},
            )
            entities.append(entity)

        total_vectors = sum(
            e.row_count or 0 for e in entities
        )

        stats_obj = SchemaStats(
            total_entities=len(entities),
            total_fields=sum(len(e.fields) for e in entities),
            total_rows=total_vectors,
            estimated_size_bytes=None,
        )

        return Schema(
            source_id=self._source_id,
            source_type=self._source_type,
            entities=entities,
            summary=f"Pinecone index '{self._index_name}' with {len(entities)} namespaces",
            stats=stats_obj,
        )

    async def query(self, query: Query) -> QueryResult:
        """Execute a query."""
        if isinstance(query, SemanticQuery):
            return await self.vector_search(
                collection=query.collection or "",
                query_vector=query.query_vector,
                top_k=query.top_k,
                threshold=query.threshold,
                filter=query.filter,
            )
        else:
            raise ValueError(f"Unsupported query type for Pinecone: {type(query)}")

    async def vector_search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        threshold: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Vector similarity search.

        Args:
            collection: Namespace (empty string for default)
            query_vector: Query embedding
            top_k: Max results
            threshold: Min similarity score
            filter: Metadata filter dict
        """
        start = time.time()

        # Map collection to namespace
        namespace = "" if collection in ("_default", "") else collection

        results = self._index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
            include_metadata=True,
        )

        elapsed = (time.time() - start) * 1000

        # Build result rows
        rows = []
        for match in results.matches:
            if threshold is not None and match.score < threshold:
                continue

            row = {
                "id": match.id,
                "score": match.score,
                **(match.metadata or {}),
            }
            rows.append(row)

        # Get columns from first result
        columns = ["id", "score"]
        if rows and len(rows[0]) > 2:
            columns.extend([k for k in rows[0].keys() if k not in ("id", "score")])

        return QueryResult(
            columns=columns,
            rows=[[row.get(c) for c in columns] for row in rows],
            total_count=len(rows),
            execution_time_ms=elapsed,
            source_id=self._source_id,
        )

    async def get_vector_dimensions(self, collection: str) -> int:
        """Get vector dimensionality."""
        stats = self._index.describe_index_stats()
        return stats.dimension

    async def upsert_vectors(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert or update vectors."""
        namespace = "" if collection in ("_default", "") else collection

        records = []
        for i, (id_, vector) in enumerate(zip(ids, vectors)):
            metadata = payloads[i] if payloads else {}
            records.append({
                "id": id_,
                "values": vector,
                "metadata": metadata,
            })

        self._index.upsert(vectors=records, namespace=namespace)
        return len(records)

    async def delete_vectors(
        self,
        collection: str,
        ids: list[str],
    ) -> int:
        """Delete vectors by ID."""
        namespace = "" if collection in ("_default", "") else collection
        self._index.delete(ids=ids, namespace=namespace)
        return len(ids)

    async def list_collections(self) -> list[str]:
        """List all namespaces."""
        stats = self._index.describe_index_stats()
        namespaces = list(stats.namespaces.keys()) if stats.namespaces else [""]
        return [ns or "_default" for ns in namespaces]

    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk is not well-supported by Pinecone (no scroll/pagination).

        Returns metadata-only chunks.
        """
        if not isinstance(strategy, FixedRowsStrategy):
            raise ValueError(f"Unsupported chunk strategy: {type(strategy)}")

        # Pinecone doesn't support efficient pagination
        # Return a single metadata chunk
        stats = self._index.describe_index_stats()
        namespace = "" if entity in ("_default", "") else entity

        ns_stats = stats.namespaces.get(namespace, {})
        vector_count = ns_stats.vector_count if hasattr(ns_stats, 'vector_count') else 0

        chunk = Chunk(
            id=f"{self._source_id}:{entity}:metadata",
            source_id=self._source_id,
            entity=entity,
            index=0,
            total_chunks=1,
            data={"vector_count": vector_count, "dimension": stats.dimension},
            metadata=ChunkMetadata(
                estimated_tokens=50,
            ),
        )

        return [chunk]

    async def sample(
        self,
        entity: str,
        strategy: SampleStrategy | None = None,
    ) -> list[dict[str, Any]]:
        """Sample vectors (requires fetching by ID, limited support)."""
        # Pinecone doesn't support listing vectors
        # Return stats instead
        stats = self._index.describe_index_stats()
        namespace = "" if entity in ("_default", "") else entity

        ns_stats = stats.namespaces.get(namespace, {})
        vector_count = ns_stats.vector_count if hasattr(ns_stats, 'vector_count') else 0

        return [{
            "namespace": namespace,
            "vector_count": vector_count,
            "dimension": stats.dimension,
            "note": "Pinecone does not support listing vectors without IDs",
        }]

    async def health_check(self) -> HealthStatus:
        """Check Pinecone connectivity."""
        start = time.time()
        try:
            self._index.describe_index_stats()
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=True, latency_ms=elapsed)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=False, latency_ms=elapsed, message=str(e))

    async def close(self) -> None:
        """Close is not needed for Pinecone client."""
        pass


def pinecone(
    source_id: str,
    api_key: str,
    index_name: str,
    **kwargs,
) -> PineconeAdapter:
    """Create a Pinecone adapter (convenience function)."""
    return PineconeAdapter(source_id, api_key, index_name, **kwargs)
