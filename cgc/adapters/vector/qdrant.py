"""Qdrant vector database adapter."""

from __future__ import annotations

import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

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


class QdrantAdapter(VectorSource):
    """Adapter for Qdrant vector database.

    Features:
    - High-performance vector similarity search
    - Rich filtering on payload fields
    - Supports multiple distance metrics
    - Horizontal scaling with sharding
    """

    def __init__(
        self,
        source_id: str,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        prefer_grpc: bool = False,
    ):
        """Initialize Qdrant adapter.

        Args:
            source_id: Unique identifier for this source
            url: Qdrant server URL
            api_key: Optional API key
            prefer_grpc: Use gRPC instead of HTTP
        """
        self._source_id = source_id
        self._url = url
        self._client = QdrantClient(
            url=url,
            api_key=api_key,
            prefer_grpc=prefer_grpc,
        )

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> SourceType:
        return SourceType.QDRANT

    async def discover_schema(
        self,
        options: DiscoveryOptions | None = None,
    ) -> Schema:
        """Discover Qdrant collections."""
        options = options or DiscoveryOptions()
        entities = []

        # Get all collections
        collections = self._client.get_collections().collections

        for collection in collections:
            name = collection.name

            if options.entities and name not in options.entities:
                continue

            # Get collection info
            info = self._client.get_collection(name)

            # Build fields
            fields = [
                Field(
                    name="id",
                    data_type=DataType.STRING,
                    is_primary_key=True,
                ),
                Field(
                    name="vector",
                    data_type=DataType.VECTOR,
                    original_type=f"vector[{info.config.params.vectors.size}]",
                ),
            ]

            # Infer payload fields from samples
            if options.include_samples:
                sample_points, _ = self._client.scroll(
                    collection_name=name,
                    limit=options.sample_size,
                    with_payload=True,
                    with_vectors=False,
                )

                if sample_points:
                    payload_fields: set[str] = set()
                    for point in sample_points:
                        if point.payload:
                            payload_fields.update(point.payload.keys())

                    for field_name in payload_fields:
                        fields.append(Field(
                            name=field_name,
                            data_type=DataType.JSON,
                        ))

            entity = Entity(
                name=name,
                entity_type=EntityType.INDEX,
                fields=fields,
                row_count=info.points_count,
                metadata={
                    "vector_size": info.config.params.vectors.size,
                    "distance": str(info.config.params.vectors.distance),
                },
            )
            entities.append(entity)

        stats = SchemaStats(
            total_entities=len(entities),
            total_fields=sum(len(e.fields) for e in entities),
            total_rows=sum(e.row_count or 0 for e in entities),
            estimated_size_bytes=None,
        )

        return Schema(
            source_id=self._source_id,
            source_type=self._source_type,
            entities=entities,
            summary=f"Qdrant at {self._url} with {len(entities)} collections",
            stats=stats,
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
            raise ValueError(f"Unsupported query type for Qdrant: {type(query)}")

    async def vector_search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        threshold: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Vector similarity search."""
        start = time.time()

        # Build filter if provided
        qdrant_filter = None
        if filter:
            conditions = []
            for key, value in filter.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            qdrant_filter = Filter(must=conditions)

        results = self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=threshold,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        elapsed = (time.time() - start) * 1000

        # Build result rows
        rows = []
        for r in results:
            row = {
                "id": str(r.id),
                "score": r.score,
                **(r.payload or {}),
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
        """Get vector dimensionality for a collection."""
        info = self._client.get_collection(collection)
        return info.config.params.vectors.size

    async def upsert_vectors(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert or update vectors."""
        from qdrant_client.models import PointStruct

        points = []
        for i, (id_, vector) in enumerate(zip(ids, vectors)):
            payload = payloads[i] if payloads else {}
            points.append(PointStruct(
                id=id_,
                vector=vector,
                payload=payload,
            ))

        self._client.upsert(collection_name=collection, points=points)
        return len(points)

    async def delete_vectors(
        self,
        collection: str,
        ids: list[str],
    ) -> int:
        """Delete vectors by ID."""
        from qdrant_client.models import PointIdsList

        self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=ids),
        )
        return len(ids)

    async def list_collections(self) -> list[str]:
        """List all collections."""
        collections = self._client.get_collections().collections
        return [c.name for c in collections]

    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk vector collection (scroll through points)."""
        if not isinstance(strategy, FixedRowsStrategy):
            raise ValueError(f"Unsupported chunk strategy: {type(strategy)}")

        chunks = []
        offset = None
        chunk_index = 0
        chunk_size = strategy.rows_per_chunk

        # Get total count
        info = self._client.get_collection(entity)
        total_points = info.points_count or 0
        total_chunks = (total_points + chunk_size - 1) // chunk_size if total_points > 0 else 1

        while True:
            points, offset = self._client.scroll(
                collection_name=entity,
                limit=chunk_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            if not points:
                break

            data = [{"id": str(p.id), **(p.payload or {})} for p in points]

            chunk = Chunk(
                id=f"{self._source_id}:{entity}:chunk_{chunk_index}",
                source_id=self._source_id,
                entity=entity,
                index=chunk_index,
                total_chunks=total_chunks,
                data=data,
                metadata=ChunkMetadata(
                    estimated_tokens=len(str(data)) // 4,
                ),
            )
            chunks.append(chunk)
            chunk_index += 1

            if offset is None:
                break

        return chunks

    async def sample(
        self,
        entity: str,
        strategy: SampleStrategy | None = None,
    ) -> list[dict[str, Any]]:
        """Sample points from a collection."""
        n = strategy.n if isinstance(strategy, FirstN) else 5

        points, _ = self._client.scroll(
            collection_name=entity,
            limit=n,
            with_payload=True,
            with_vectors=False,
        )

        return [{"id": str(p.id), **(p.payload or {})} for p in points]

    async def health_check(self) -> HealthStatus:
        """Check Qdrant connectivity."""
        start = time.time()
        try:
            self._client.get_collections()
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=True, latency_ms=elapsed)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=False, latency_ms=elapsed, message=str(e))

    async def close(self) -> None:
        """Close the client."""
        self._client.close()


def qdrant(
    source_id: str,
    url: str = "http://localhost:6333",
    api_key: str | None = None,
    **kwargs,
) -> QdrantAdapter:
    """Create a Qdrant adapter (convenience function)."""
    return QdrantAdapter(source_id, url, api_key, **kwargs)
