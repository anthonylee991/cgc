"""Query types for data retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class AggregateFunction(Enum):
    """Aggregate functions for queries."""

    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT_DISTINCT = "count_distinct"


@dataclass
class Aggregation:
    """An aggregation operation."""

    field: str
    function: AggregateFunction
    alias: str | None = None


@dataclass
class Query:
    """Base query type - use subclasses for specific query types."""

    pass


@dataclass
class SqlQuery(Query):
    """Raw SQL query."""

    sql: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class GetQuery(Query):
    """Key-value lookup."""

    entity: str
    key: str
    value: Any


@dataclass
class PatternQuery(Query):
    """Pattern matching (grep-like) with optional fuzzy fallback."""

    entity: str
    pattern: str
    case_sensitive: bool = False
    field: str | None = None  # Specific field to search, or all text fields
    fuzzy_fallback: bool = True  # If no exact matches, try fuzzy matching
    similarity_threshold: float = 0.5  # Minimum similarity for fuzzy matches (0-1)


@dataclass
class SearchQuery(Query):
    """Text search with ILIKE and optional trigram fallback."""

    entity: str
    field: str
    query: str
    fuzzy_fallback: bool = True
    similarity_threshold: float = 0.3


@dataclass
class SemanticQuery(Query):
    """Semantic/vector search."""

    query_vector: list[float]
    collection: str | None = None
    top_k: int = 10
    threshold: float | None = None
    filter: dict[str, Any] | None = None


@dataclass
class TraverseQuery(Query):
    """Graph traversal from a starting point."""

    from ..core.schema import FieldId

    start: FieldId
    relationship_types: list[str] | None = None
    depth: int = 1


@dataclass
class AggregateQuery(Query):
    """Aggregation query."""

    entity: str
    aggregations: list[Aggregation]
    group_by: list[str] = field(default_factory=list)
    filter: str | None = None


@dataclass
class QueryResult:
    """Unified query result format."""

    columns: list[str]
    rows: list[list[Any]]
    total_count: int | None = None
    truncated: bool = False
    execution_time_ms: float = 0.0
    source_id: str = ""

    def to_dicts(self) -> list[dict[str, Any]]:
        """Convert to list of dictionaries."""
        return [dict(zip(self.columns, row)) for row in self.rows]

    def to_pandas(self) -> "pd.DataFrame":
        """Convert to pandas DataFrame."""
        import pandas as pd

        return pd.DataFrame(self.rows, columns=self.columns)

    def __len__(self) -> int:
        return len(self.rows)

    def __bool__(self) -> bool:
        return len(self.rows) > 0

    def __iter__(self):
        """Iterate over rows as dictionaries."""
        return iter(self.to_dicts())

    @property
    def first(self) -> dict[str, Any] | None:
        """Get first row as dictionary, or None if empty."""
        if not self.rows:
            return None
        return dict(zip(self.columns, self.rows[0]))

    def column(self, name: str) -> list[Any]:
        """Get all values from a specific column."""
        if name not in self.columns:
            raise KeyError(f"Column not found: {name}")
        idx = self.columns.index(name)
        return [row[idx] for row in self.rows]
