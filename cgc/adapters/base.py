"""Base protocol for all data source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from cgc.core.schema import Schema, SourceType
from cgc.core.query import Query, QueryResult
from cgc.core.chunk import Chunk, ChunkStrategy


@dataclass
class DiscoveryOptions:
    """Options for schema discovery."""

    entities: list[str] | None = None  # Specific entities to discover, or all
    include_samples: bool = True
    sample_size: int = 5
    include_cardinality: bool = True
    timeout_seconds: int | None = 60


class SampleStrategy:
    """Base class for sampling strategies."""

    pass


@dataclass
class FirstN(SampleStrategy):
    """First N rows."""

    n: int = 5


@dataclass
class RandomSample(SampleStrategy):
    """Random sample."""

    n: int = 5
    seed: int | None = None


@dataclass
class StratifiedSample(SampleStrategy):
    """Stratified by field."""

    field: str
    n_per_stratum: int = 2


@dataclass
class HealthStatus:
    """Health check result."""

    healthy: bool
    latency_ms: float = 0.0
    message: str | None = None
    details: dict[str, Any] | None = None

    def __bool__(self) -> bool:
        return self.healthy


class DataSource(ABC):
    """Protocol for all data source adapters.

    All adapters must implement these methods to provide a consistent
    interface for the Connector to work with different data sources.
    """

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this source."""
        ...

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """Type of this source."""
        ...

    @abstractmethod
    async def discover_schema(
        self,
        options: DiscoveryOptions | None = None,
    ) -> Schema:
        """Discover schema for this source.

        This should introspect the data source and return information about
        its structure without reading all data. For databases, this means
        table/column info. For filesystems, file/directory structure.
        """
        ...

    @abstractmethod
    async def query(self, query: Query) -> QueryResult:
        """Execute a query against this source.

        The query type depends on what the source supports:
        - SQL sources: SqlQuery, GetQuery, SearchQuery
        - Filesystems: PatternQuery, SearchQuery
        - Vector DBs: SemanticQuery
        """
        ...

    @abstractmethod
    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk data from an entity according to strategy.

        Chunks are sized appropriately for LLM context windows.
        Each chunk includes metadata for reassembly/reference.
        """
        ...

    @abstractmethod
    async def sample(
        self,
        entity: str,
        strategy: SampleStrategy | None = None,
    ) -> list[dict[str, Any]]:
        """Sample data from an entity.

        Returns a small representative sample for inspection.
        Default is first N rows.
        """
        ...

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check if source is healthy/connected.

        Returns health status with latency measurement.
        """
        ...

    async def close(self) -> None:
        """Close connection / cleanup resources.

        Override if the adapter maintains persistent connections.
        """
        pass

    async def __aenter__(self) -> "DataSource":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source_id={self.source_id!r})"
