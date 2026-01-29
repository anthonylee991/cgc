"""MongoDB Atlas Vector Search adapter."""

from __future__ import annotations

import time
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

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


class MongoVectorAdapter(VectorSource):
    """MongoDB with Atlas Vector Search.

    Features:
    - Vector search integrated with document store
    - Rich document structure with nested fields
    - Aggregation pipeline support
    - Atlas Search for hybrid search
    """

    def __init__(
        self,
        source_id: str,
        connection_string: str,
        database: str,
        default_vector_field: str = "embedding",
        default_index_name: str = "vector_index",
    ):
        """Initialize MongoDB Vector adapter.

        Args:
            source_id: Unique identifier for this source
            connection_string: MongoDB connection string
            database: Database name
            default_vector_field: Default field containing vectors
            default_index_name: Default Atlas Search index name
        """
        self._source_id = source_id
        self._client = AsyncIOMotorClient(connection_string)
        self._db = self._client[database]
        self._database_name = database
        self._default_vector_field = default_vector_field
        self._default_index_name = default_index_name

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> SourceType:
        return SourceType.MONGODB

    async def discover_schema(
        self,
        options: DiscoveryOptions | None = None,
    ) -> Schema:
        """Discover MongoDB collections."""
        options = options or DiscoveryOptions()
        entities = []

        # Get all collections
        collections = await self._db.list_collection_names()

        for coll_name in collections:
            if options.entities and coll_name not in options.entities:
                continue

            # Skip system collections
            if coll_name.startswith("system."):
                continue

            entity = await self._discover_collection(coll_name, options)
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
            summary=f"MongoDB '{self._database_name}' with {len(entities)} collections",
            stats=stats,
        )

    async def _discover_collection(
        self,
        name: str,
        options: DiscoveryOptions,
    ) -> Entity:
        """Discover a single collection."""
        coll = self._db[name]

        # Get document count
        count = await coll.estimated_document_count()

        # Sample documents to infer schema
        fields = [
            Field(name="_id", data_type=DataType.STRING, is_primary_key=True),
        ]

        if options.include_samples:
            sample = await coll.find_one()
            if sample:
                for key, value in sample.items():
                    if key == "_id":
                        continue
                    dtype = self._infer_type(value)
                    fields.append(Field(name=key, data_type=dtype))

        return Entity(
            name=name,
            entity_type=EntityType.COLLECTION,
            fields=fields,
            row_count=count,
        )

    def _infer_type(self, value: Any) -> DataType:
        """Infer data type from a value."""
        if value is None:
            return DataType.STRING
        if isinstance(value, bool):
            return DataType.BOOLEAN
        if isinstance(value, int):
            return DataType.INTEGER
        if isinstance(value, float):
            return DataType.FLOAT
        if isinstance(value, list):
            # Check if it's a vector (list of floats)
            if value and all(isinstance(v, (int, float)) for v in value[:10]):
                return DataType.VECTOR
            return DataType.ARRAY
        if isinstance(value, dict):
            return DataType.JSON
        return DataType.STRING

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
            raise ValueError(f"Unsupported query type for MongoDB: {type(query)}")

    async def vector_search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        threshold: float | None = None,
        filter: dict[str, Any] | None = None,
        vector_field: str | None = None,
        index_name: str | None = None,
    ) -> QueryResult:
        """Vector similarity search using Atlas Vector Search.

        Args:
            collection: Collection name
            query_vector: Query embedding
            top_k: Max results
            threshold: Min similarity score
            filter: Pre-filter conditions
            vector_field: Field containing vectors
            index_name: Atlas Search index name
        """
        start = time.time()

        vec_field = vector_field or self._default_vector_field
        idx_name = index_name or self._default_index_name

        # Build aggregation pipeline
        pipeline: list[dict[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": idx_name,
                    "path": vec_field,
                    "queryVector": query_vector,
                    "numCandidates": top_k * 10,
                    "limit": top_k,
                }
            },
            {
                "$addFields": {
                    "_score": {"$meta": "vectorSearchScore"}
                }
            },
        ]

        # Add filter if provided
        if filter:
            pipeline[0]["$vectorSearch"]["filter"] = filter

        # Add score threshold
        if threshold is not None:
            pipeline.append({"$match": {"_score": {"$gte": threshold}}})

        # Execute
        coll = self._db[collection]
        cursor = coll.aggregate(pipeline)
        docs = await cursor.to_list(length=top_k)

        elapsed = (time.time() - start) * 1000

        # Build result
        rows = []
        all_keys: set[str] = set()

        for doc in docs:
            # Convert ObjectId to string
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            # Remove vector field (too large)
            doc.pop(vec_field, None)
            all_keys.update(doc.keys())
            rows.append(doc)

        # Consistent column order
        columns = ["_id", "_score"] + sorted(
            k for k in all_keys if k not in ("_id", "_score")
        )

        return QueryResult(
            columns=columns,
            rows=[[row.get(c) for c in columns] for row in rows],
            total_count=len(rows),
            execution_time_ms=elapsed,
            source_id=self._source_id,
        )

    async def get_vector_dimensions(self, collection: str) -> int:
        """Get vector dimensionality from a sample document."""
        coll = self._db[collection]
        doc = await coll.find_one(
            {self._default_vector_field: {"$exists": True}},
            {self._default_vector_field: 1},
        )

        if doc and self._default_vector_field in doc:
            vec = doc[self._default_vector_field]
            if isinstance(vec, list):
                return len(vec)

        return 0

    async def upsert_vectors(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert or update documents with vectors."""
        from pymongo import UpdateOne

        coll = self._db[collection]
        operations = []

        for i, (id_, vector) in enumerate(zip(ids, vectors)):
            payload = payloads[i] if payloads else {}
            doc = {
                self._default_vector_field: vector,
                **payload,
            }
            operations.append(
                UpdateOne(
                    {"_id": id_},
                    {"$set": doc},
                    upsert=True,
                )
            )

        if operations:
            result = await coll.bulk_write(operations)
            return result.upserted_count + result.modified_count

        return 0

    async def delete_vectors(
        self,
        collection: str,
        ids: list[str],
    ) -> int:
        """Delete documents by ID."""
        coll = self._db[collection]
        result = await coll.delete_many({"_id": {"$in": ids}})
        return result.deleted_count

    async def list_collections(self) -> list[str]:
        """List all collections."""
        return await self._db.list_collection_names()

    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk collection documents."""
        if not isinstance(strategy, FixedRowsStrategy):
            raise ValueError(f"Unsupported chunk strategy: {type(strategy)}")

        chunks = []
        coll = self._db[entity]

        # Get total count
        total_docs = await coll.estimated_document_count()
        total_chunks = (total_docs + strategy.rows_per_chunk - 1) // strategy.rows_per_chunk

        # Use skip/limit for pagination
        for i in range(total_chunks):
            skip = i * strategy.rows_per_chunk
            cursor = coll.find().skip(skip).limit(strategy.rows_per_chunk)
            docs = await cursor.to_list(length=strategy.rows_per_chunk)

            # Convert ObjectIds and remove vectors
            data = []
            for doc in docs:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                doc.pop(self._default_vector_field, None)
                data.append(doc)

            chunk = Chunk(
                id=f"{self._source_id}:{entity}:chunk_{i}",
                source_id=self._source_id,
                entity=entity,
                index=i,
                total_chunks=total_chunks,
                data=data,
                metadata=ChunkMetadata(
                    row_range=(skip, skip + len(docs)),
                    estimated_tokens=len(str(data)) // 4,
                ),
            )
            chunks.append(chunk)

        return chunks

    async def sample(
        self,
        entity: str,
        strategy: SampleStrategy | None = None,
    ) -> list[dict[str, Any]]:
        """Sample documents from a collection."""
        n = strategy.n if isinstance(strategy, FirstN) else 5
        coll = self._db[entity]

        cursor = coll.find().limit(n)
        docs = await cursor.to_list(length=n)

        # Convert ObjectIds and remove vectors
        result = []
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            doc.pop(self._default_vector_field, None)
            result.append(doc)

        return result

    async def health_check(self) -> HealthStatus:
        """Check MongoDB connectivity."""
        start = time.time()
        try:
            await self._client.admin.command("ping")
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=True, latency_ms=elapsed)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=False, latency_ms=elapsed, message=str(e))

    async def close(self) -> None:
        """Close the client."""
        self._client.close()


def mongodb_vector(
    source_id: str,
    connection_string: str,
    database: str,
    **kwargs,
) -> MongoVectorAdapter:
    """Create a MongoDB Vector adapter (convenience function)."""
    return MongoVectorAdapter(source_id, connection_string, database, **kwargs)
