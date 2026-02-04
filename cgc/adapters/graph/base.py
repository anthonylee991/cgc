"""Base class for graph database adapters (sinks for triplet storage)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from cgc.core.triplet import Triplet


@dataclass
class GraphStats:
    """Statistics about the graph."""

    node_count: int = 0
    edge_count: int = 0
    node_labels: list[str] = field(default_factory=list)
    relationship_types: list[str] = field(default_factory=list)


@dataclass
class StorageResult:
    """Result of storing triplets."""

    nodes_created: int = 0
    nodes_merged: int = 0
    relationships_created: int = 0
    relationships_merged: int = 0
    execution_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def total_created(self) -> int:
        return self.nodes_created + self.relationships_created


class GraphSink(ABC):
    """Protocol for graph database sinks.

    Graph sinks receive extracted triplets and store them as nodes
    and relationships in a graph database.
    """

    @property
    @abstractmethod
    def sink_id(self) -> str:
        """Unique identifier for this sink."""
        ...

    @property
    @abstractmethod
    def sink_type(self) -> str:
        """Type of graph database (neo4j, age, etc.)."""
        ...

    @abstractmethod
    async def store_triplets(
        self,
        triplets: list[Triplet],
        graph_name: str | None = None,
        merge: bool = True,
    ) -> StorageResult:
        """Store triplets in the graph database.

        Args:
            triplets: List of triplets to store
            graph_name: Optional graph/namespace name (for AGE, etc.)
            merge: If True, merge with existing nodes/edges. If False, always create new.

        Returns:
            StorageResult with counts and any errors
        """
        ...

    @abstractmethod
    async def get_stats(self, graph_name: str | None = None) -> GraphStats:
        """Get statistics about the graph."""
        ...

    @abstractmethod
    async def query_graph(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
        graph_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results.

        Args:
            cypher: Cypher query string
            params: Query parameters
            graph_name: Optional graph name (for AGE)

        Returns:
            List of result dictionaries
        """
        ...

    @abstractmethod
    async def find_by_entity(
        self,
        entity: str,
        graph_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find all triplets involving an entity.

        Args:
            entity: Entity name to search for
            graph_name: Optional graph name
            limit: Maximum results to return

        Returns:
            List of triplet dictionaries
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the graph database is accessible."""
        ...

    async def connect(self) -> None:
        """Connect to the graph database.

        Default implementation does nothing; subclasses may override
        to establish connections if needed.
        """
        pass

    async def close(self) -> None:
        """Close connection / cleanup resources."""
        pass

    async def __aenter__(self) -> "GraphSink":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(sink_id={self.sink_id!r})"
