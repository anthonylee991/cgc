"""Base protocol for vector database adapters."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from cgc.adapters.base import DataSource
from cgc.core.query import QueryResult


class VectorSource(DataSource):
    """Extended protocol for vector-capable data sources.

    Adds vector-specific operations on top of the base DataSource protocol.
    Implementations: pgvector, Qdrant, Pinecone, MongoDB Atlas Vector Search.
    """

    @abstractmethod
    async def vector_search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        threshold: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Similarity search by vector.

        Args:
            collection: The collection/index to search
            query_vector: The query embedding vector
            top_k: Maximum number of results
            threshold: Minimum similarity score (optional)
            filter: Metadata filter (optional)

        Returns:
            QueryResult with columns: id, score, and payload fields
        """
        ...

    @abstractmethod
    async def get_vector_dimensions(self, collection: str) -> int:
        """Get vector dimensionality for a collection.

        Useful for validating query vectors before search.
        """
        ...

    async def upsert_vectors(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert or update vectors with optional payload.

        Args:
            collection: Target collection
            ids: Unique identifiers for each vector
            vectors: Embedding vectors
            payloads: Optional metadata for each vector

        Returns:
            Number of vectors upserted

        Note: Override if the vector DB supports writes.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support vector writes")

    async def delete_vectors(
        self,
        collection: str,
        ids: list[str],
    ) -> int:
        """Delete vectors by ID.

        Returns:
            Number of vectors deleted

        Note: Override if the vector DB supports deletes.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support vector deletes")

    async def list_collections(self) -> list[str]:
        """List all vector collections/indexes.

        Note: Override to provide collection listing.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support listing collections")
