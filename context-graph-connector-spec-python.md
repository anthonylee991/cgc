# Context Graph Connector (CGC)

## Technical Specification v0.1 — Python Edition

---

## 1. Overview

### 1.1 What It Is

Context Graph Connector is a Python library and CLI tool that gives LLM-based agents programmatic access to external data sources. Instead of cramming data into context windows (which causes "context rot"), CGC exposes primitives that let an orchestrating agent probe, query, chunk, and navigate data surgically.

### 1.2 Core Philosophy

- **Data stays where it is** — CGC doesn't copy or move data; it provides access patterns
- **LLM-minimal** — The connector itself makes zero LLM calls; all intelligence lives in the orchestrating agent
- **Relationships are first-class** — Automatic discovery of how data connects across and within sources
- **RLM-native** — Runs directly in Python REPLs; no bridging needed

### 1.3 The Problem It Solves

Modern LLMs fail at long-context reasoning not because they can't hold the tokens, but because attention degrades ("context rot"). Research shows GPT-5-class models collapse to near-zero accuracy on complex tasks beyond ~33k tokens, despite advertising 1M+ context windows.

The solution: treat context as an external environment to navigate programmatically, not as something to memorize. CGC provides the navigation layer.

### 1.4 License

**Apache 2.0** — Permissive, allows commercial use, provides patent protection.

---

## 2. Architecture

### 2.1 High-Level Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrating Agent (External)                │
│          (LLM writing Python in REPL, or tool-calling)          │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ cgc.probe() / cgc.query() / cgc.chunk()
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Context Graph Connector                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Schema    │  │   Query     │  │      Relationship       │  │
│  │  Discovery  │  │   Engine    │  │        Graph            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Chunking   │  │    Cache    │  │     Adapters            │  │
│  │  Strategies │  │   (SQLite)  │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
    ┌──────────┐          ┌──────────┐          ┌──────────┐
    │ Postgres │          │  Files   │          │  Qdrant  │
    │  MySQL   │          │   S3     │          │ Pinecone │
    │  SQLite  │          │   GCS    │          │ Weaviate │
    └──────────┘          └──────────┘          └──────────┘
```

### 2.2 Package Structure

```
context-graph-connector/
├── pyproject.toml
├── LICENSE
├── README.md
├── cgc/
│   ├── __init__.py           # Public API exports
│   ├── connector.py          # Main Connector class
│   ├── core/
│   │   ├── __init__.py
│   │   ├── schema.py         # Schema types and discovery
│   │   ├── query.py          # Query types and execution
│   │   ├── chunk.py          # Chunking strategies
│   │   ├── graph.py          # Relationship graph
│   │   └── errors.py         # Exception classes
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py           # DataSource protocol
│   │   ├── sql.py            # Postgres, MySQL, SQLite via SQLAlchemy
│   │   ├── document.py       # MongoDB via pymongo
│   │   ├── vector.py         # Qdrant, Pinecone, Weaviate
│   │   ├── filesystem.py     # Local, S3, GCS
│   │   └── api.py            # REST APIs via OpenAPI
│   ├── discovery/
│   │   ├── __init__.py
│   │   ├── engine.py         # Relationship discovery engine
│   │   └── rules.py          # Inference rules
│   ├── cache/
│   │   ├── __init__.py
│   │   └── sqlite.py         # SQLite-backed cache
│   └── cli/
│       ├── __init__.py
│       └── main.py           # Typer CLI
├── tests/
│   ├── __init__.py
│   ├── test_adapters/
│   ├── test_discovery/
│   └── fixtures/
└── examples/
    ├── basic_sql.py
    ├── multi_source.py
    ├── rlm_integration.py
    └── filesystem_analysis.py
```

### 2.3 Dependencies

```toml
[project]
name = "context-graph-connector"
version = "0.1.0"
description = "Programmatic data access layer for LLM agents"
requires-python = ">=3.10"
license = "Apache-2.0"

dependencies = [
    # SQL databases (one library handles all)
    "sqlalchemy>=2.0",
    "asyncpg",              # Postgres async driver
    "aiomysql",             # MySQL async driver
    "aiosqlite",            # SQLite async driver
    
    # Document stores
    "pymongo>=4.0",
    "motor",                # Async MongoDB
    
    # Vector databases
    "qdrant-client>=1.0",
    
    # Object storage
    "boto3",                # S3
    "aioboto3",             # Async S3
    "google-cloud-storage", # GCS
    
    # API introspection
    "httpx",                # Async HTTP
    "openapi-pydantic",     # OpenAPI parsing
    
    # Data handling
    "pydantic>=2.0",        # Data validation
    "pandas",               # Tabular data
    "pyarrow",              # Parquet support
    
    # CLI
    "typer>=0.9",
    "rich",                 # Pretty output
    
    # Utilities
    "python-dotenv",
    "structlog",            # Logging
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio",
    "pytest-cov",
    "testcontainers",       # Docker-based integration tests
    "ruff",                 # Linting
    "mypy",                 # Type checking
]

[project.scripts]
cgc = "cgc.cli.main:app"
```

---

## 3. Core Types

### 3.1 Schema Representation

```python
# cgc/core/schema.py

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SourceType(Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    QDRANT = "qdrant"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    FILESYSTEM = "filesystem"
    S3 = "s3"
    GCS = "gcs"
    API = "api"


class EntityType(Enum):
    TABLE = "table"
    VIEW = "view"
    COLLECTION = "collection"
    FILE = "file"
    DIRECTORY = "directory"
    ENDPOINT = "endpoint"
    INDEX = "index"  # Vector index


class DataType(Enum):
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    STRING = "string"
    TEXT = "text"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    BYTES = "bytes"
    JSON = "json"
    ARRAY = "array"
    VECTOR = "vector"
    UNKNOWN = "unknown"


@dataclass
class FieldId:
    """Unique identifier for a field across all sources."""
    source_id: str
    entity: str
    field: str

    def __hash__(self):
        return hash((self.source_id, self.entity, self.field))
    
    def __str__(self):
        return f"{self.source_id}.{self.entity}.{self.field}"


@dataclass
class Cardinality:
    """Statistics about a field's value distribution."""
    unique_count: int
    null_count: int
    total_count: int
    
    @property
    def uniqueness_ratio(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.unique_count / self.total_count


@dataclass
class Field:
    """A column/field within an entity."""
    name: str
    data_type: DataType
    nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_ref: FieldId | None = None
    description: str | None = None
    sample_values: list[Any] = field(default_factory=list)
    cardinality: Cardinality | None = None
    original_type: str | None = None  # Raw type string from source
    
    def to_field_id(self, source_id: str, entity: str) -> FieldId:
        return FieldId(source_id=source_id, entity=entity, field=self.name)


@dataclass
class Entity:
    """A table, collection, file, or endpoint."""
    name: str
    entity_type: EntityType
    fields: list[Field] = field(default_factory=list)
    row_count: int | None = None
    sample_data: list[dict[str, Any]] = field(default_factory=list)
    description: str | None = None
    
    def get_field(self, name: str) -> Field | None:
        return next((f for f in self.fields if f.name == name), None)
    
    @property
    def primary_keys(self) -> list[Field]:
        return [f for f in self.fields if f.is_primary_key]
    
    @property
    def foreign_keys(self) -> list[Field]:
        return [f for f in self.fields if f.is_foreign_key]


@dataclass
class SchemaStats:
    """Summary statistics for a schema."""
    total_entities: int
    total_fields: int
    total_rows: int | None
    estimated_size_bytes: int | None


@dataclass
class Schema:
    """Complete schema for a data source."""
    source_id: str
    source_type: SourceType
    entities: list[Entity]
    relationships: list[Relationship] = field(default_factory=list)
    summary: str = ""
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    stats: SchemaStats | None = None
    
    def get_entity(self, name: str) -> Entity | None:
        return next((e for e in self.entities if e.name == name), None)
    
    def to_compact(self) -> str:
        """Generate compact summary for LLM context."""
        lines = [f"Source: {self.source_id} ({self.source_type.value})"]
        for entity in self.entities:
            fields_str = ", ".join(f.name for f in entity.fields[:5])
            if len(entity.fields) > 5:
                fields_str += f", ... (+{len(entity.fields) - 5} more)"
            rows = f" ({entity.row_count} rows)" if entity.row_count else ""
            lines.append(f"  {entity.name}{rows}: {fields_str}")
        return "\n".join(lines)
```

### 3.2 Relationship Graph

```python
# cgc/core/graph.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

from .schema import FieldId


class RelationshipType(Enum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"
    SAME_ENTITY = "same_entity"      # Same logical entity across sources
    CONTAINS = "contains"             # Directory contains file
    REFERENCES = "references"         # Generic reference


class Confidence(Enum):
    CERTAIN = "certain"       # Explicit FK constraint
    HIGH = "high"             # Strong naming + cardinality match
    MEDIUM = "medium"         # Naming convention match
    LOW = "low"               # Statistical correlation only


class InferenceMethod(Enum):
    EXPLICIT_CONSTRAINT = "explicit_constraint"
    NAMING_CONVENTION = "naming_convention"
    CARDINALITY_MATCH = "cardinality_match"
    VALUE_OVERLAP = "value_overlap"
    CROSS_SOURCE_RULE = "cross_source_rule"


@dataclass
class Relationship:
    """A discovered relationship between two fields."""
    id: str
    from_field: FieldId
    to_field: FieldId
    relationship_type: RelationshipType
    confidence: Confidence
    inferred_by: InferenceMethod
    metadata: dict = field(default_factory=dict)  # e.g., {"overlap_ratio": 0.95}
    
    def __hash__(self):
        return hash(self.id)
    
    def involves(self, field_id: FieldId) -> bool:
        return self.from_field == field_id or self.to_field == field_id
    
    def other_side(self, field_id: FieldId) -> FieldId | None:
        if self.from_field == field_id:
            return self.to_field
        if self.to_field == field_id:
            return self.from_field
        return None


@dataclass
class RelationshipGraph:
    """Graph of relationships across all connected sources."""
    relationships: list[Relationship] = field(default_factory=list)
    _index: dict[FieldId, list[str]] = field(default_factory=dict, repr=False)
    
    def add(self, rel: Relationship) -> None:
        self.relationships.append(rel)
        self._index.setdefault(rel.from_field, []).append(rel.id)
        self._index.setdefault(rel.to_field, []).append(rel.id)
    
    def related_to(self, field_id: FieldId) -> list[Relationship]:
        """Get all relationships involving a field."""
        rel_ids = self._index.get(field_id, [])
        return [r for r in self.relationships if r.id in rel_ids]
    
    def find_path(
        self, 
        from_field: FieldId, 
        to_field: FieldId,
        max_depth: int = 5
    ) -> list[Relationship] | None:
        """Find shortest path between two fields (BFS)."""
        from collections import deque
        
        if from_field == to_field:
            return []
        
        visited = {from_field}
        queue = deque([(from_field, [])])
        
        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue
                
            for rel in self.related_to(current):
                next_field = rel.other_side(current)
                if next_field is None:
                    continue
                    
                new_path = path + [rel]
                
                if next_field == to_field:
                    return new_path
                
                if next_field not in visited:
                    visited.add(next_field)
                    queue.append((next_field, new_path))
        
        return None
    
    def same_entity_fields(self, field_id: FieldId) -> list[FieldId]:
        """Get all fields representing the same logical entity."""
        result = [field_id]
        for rel in self.related_to(field_id):
            if rel.relationship_type == RelationshipType.SAME_ENTITY:
                other = rel.other_side(field_id)
                if other:
                    result.append(other)
        return result
    
    def to_dot(self) -> str:
        """Export as Graphviz DOT format."""
        lines = ["digraph RelationshipGraph {", "  rankdir=LR;"]
        
        # Nodes
        nodes = set()
        for rel in self.relationships:
            nodes.add(rel.from_field)
            nodes.add(rel.to_field)
        
        for node in nodes:
            label = f"{node.entity}.{node.field}"
            lines.append(f'  "{node}" [label="{label}"];')
        
        # Edges
        for rel in self.relationships:
            style = "solid" if rel.confidence == Confidence.CERTAIN else "dashed"
            lines.append(
                f'  "{rel.from_field}" -> "{rel.to_field}" '
                f'[label="{rel.relationship_type.value}" style="{style}"];'
            )
        
        lines.append("}")
        return "\n".join(lines)
```

### 3.3 Query Types

```python
# cgc/core/query.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AggregateFunction(Enum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT_DISTINCT = "count_distinct"


@dataclass
class Aggregation:
    field: str
    function: AggregateFunction
    alias: str | None = None


@dataclass
class Query:
    """Base query type — use subclasses for specific query types."""
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
    """Pattern matching (grep-like)."""
    entity: str
    pattern: str
    case_sensitive: bool = False


@dataclass
class SemanticQuery(Query):
    """Semantic/vector search."""
    query: str
    entity: str | None = None
    top_k: int = 10
    threshold: float | None = None


@dataclass
class TraverseQuery(Query):
    """Graph traversal from a starting point."""
    start: FieldId
    relationship_types: list[RelationshipType] | None = None
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
    
    def to_pandas(self):
        """Convert to pandas DataFrame."""
        import pandas as pd
        return pd.DataFrame(self.rows, columns=self.columns)
    
    def __len__(self) -> int:
        return len(self.rows)
    
    def __bool__(self) -> bool:
        return len(self.rows) > 0
```

### 3.4 Chunking

```python
# cgc/core/chunk.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenEstimator(Enum):
    CHAR_DIV_4 = "char_div_4"      # len(text) / 4
    CHAR_DIV_3 = "char_div_3"      # len(text) / 3 (more conservative)
    TIKTOKEN = "tiktoken"          # Actual tokenizer (requires tiktoken)


@dataclass
class ChunkStrategy:
    """Base chunking strategy — use subclasses."""
    pass


@dataclass 
class FixedRowsStrategy(ChunkStrategy):
    """Fixed number of rows per chunk."""
    rows_per_chunk: int = 1000


@dataclass
class FixedTokensStrategy(ChunkStrategy):
    """Approximate token count per chunk."""
    tokens_per_chunk: int = 50_000
    estimator: TokenEstimator = TokenEstimator.CHAR_DIV_4


@dataclass
class ByPartitionStrategy(ChunkStrategy):
    """Partition by a field value."""
    field: str


@dataclass
class ByDocumentStrategy(ChunkStrategy):
    """Each document/file is a chunk."""
    pass


@dataclass
class BySectionsStrategy(ChunkStrategy):
    """Split by structural boundaries."""
    delimiters: list[str] = field(default_factory=lambda: ["#", "##", "###"])


@dataclass
class ByFilterStrategy(ChunkStrategy):
    """Only chunks matching a filter."""
    filter: str  # SQL WHERE clause or equivalent


@dataclass
class ByRelevanceStrategy(ChunkStrategy):
    """Top-k by semantic relevance."""
    query: str
    top_k: int = 10


@dataclass
class ChunkMetadata:
    """Metadata about a chunk."""
    row_range: tuple[int, int] | None = None
    byte_range: tuple[int, int] | None = None
    partition_value: str | None = None
    estimated_tokens: int = 0
    file_path: str | None = None


@dataclass
class Chunk:
    """A chunk of data ready for LLM processing."""
    id: str
    source_id: str
    entity: str
    index: int
    total_chunks: int
    data: list[dict[str, Any]] | str | bytes
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)
    
    def to_text(self) -> str:
        """Convert chunk to text representation."""
        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, bytes):
            return self.data.decode("utf-8", errors="replace")
        if isinstance(self.data, list):
            import json
            return json.dumps(self.data, indent=2, default=str)
        return str(self.data)
    
    def to_json(self) -> str:
        """Convert chunk to JSON string."""
        import json
        return json.dumps({
            "id": self.id,
            "source_id": self.source_id,
            "entity": self.entity,
            "index": self.index,
            "total_chunks": self.total_chunks,
            "data": self.data if not isinstance(self.data, bytes) else "<binary>",
            "metadata": {
                "row_range": self.metadata.row_range,
                "estimated_tokens": self.metadata.estimated_tokens,
            }
        }, indent=2, default=str)


def estimate_tokens(text: str, estimator: TokenEstimator = TokenEstimator.CHAR_DIV_4) -> int:
    """Estimate token count for text."""
    if estimator == TokenEstimator.CHAR_DIV_4:
        return len(text) // 4
    elif estimator == TokenEstimator.CHAR_DIV_3:
        return len(text) // 3
    elif estimator == TokenEstimator.TIKTOKEN:
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            # Fallback if tiktoken not installed
            return len(text) // 4
    return len(text) // 4
```

---

## 4. Adapter Protocol

### 4.1 Base Protocol

```python
# cgc/adapters/base.py

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from ..core.schema import Schema, SourceType, Entity
from ..core.query import Query, QueryResult
from ..core.chunk import Chunk, ChunkStrategy


class DiscoveryOptions:
    """Options for schema discovery."""
    
    def __init__(
        self,
        entities: list[str] | None = None,
        include_samples: bool = True,
        sample_size: int = 5,
        include_cardinality: bool = True,
        timeout_seconds: int | None = 60,
    ):
        self.entities = entities
        self.include_samples = include_samples
        self.sample_size = sample_size
        self.include_cardinality = include_cardinality
        self.timeout_seconds = timeout_seconds


class SampleStrategy:
    """Strategy for sampling data."""
    pass


class FirstN(SampleStrategy):
    """First N rows."""
    def __init__(self, n: int = 5):
        self.n = n


class RandomSample(SampleStrategy):
    """Random sample."""
    def __init__(self, n: int = 5, seed: int | None = None):
        self.n = n
        self.seed = seed


class StratifiedSample(SampleStrategy):
    """Stratified by field."""
    def __init__(self, field: str, n_per_stratum: int = 2):
        self.field = field
        self.n_per_stratum = n_per_stratum


class HealthStatus:
    """Health check result."""
    
    def __init__(
        self,
        healthy: bool,
        latency_ms: float = 0.0,
        message: str | None = None,
    ):
        self.healthy = healthy
        self.latency_ms = latency_ms
        self.message = message


class DataSource(ABC):
    """Protocol for all data source adapters."""
    
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
        options: DiscoveryOptions | None = None
    ) -> Schema:
        """Discover schema for this source."""
        ...
    
    @abstractmethod
    async def query(self, query: Query) -> QueryResult:
        """Execute a query."""
        ...
    
    @abstractmethod
    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk data according to strategy."""
        ...
    
    @abstractmethod
    async def sample(
        self,
        entity: str,
        strategy: SampleStrategy | None = None,
    ) -> list[dict[str, Any]]:
        """Sample data from an entity."""
        ...
    
    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check if source is healthy/connected."""
        ...
    
    async def close(self) -> None:
        """Close connection / cleanup."""
        pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
```

---

## 5. Adapters

### 5.1 SQL Adapter

```python
# cgc/adapters/sql.py

from __future__ import annotations
import asyncio
import time
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text, inspect, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from .base import (
    DataSource, DiscoveryOptions, SampleStrategy, FirstN, 
    RandomSample, HealthStatus
)
from ..core.schema import (
    Schema, SourceType, Entity, EntityType, Field, DataType,
    Cardinality, SchemaStats, FieldId
)
from ..core.query import Query, SqlQuery, GetQuery, QueryResult
from ..core.chunk import Chunk, ChunkStrategy, FixedRowsStrategy, ChunkMetadata
from ..core.graph import Relationship, RelationshipType, Confidence, InferenceMethod


# Map SQLAlchemy types to our DataType enum
TYPE_MAP = {
    "INTEGER": DataType.INTEGER,
    "BIGINT": DataType.INTEGER,
    "SMALLINT": DataType.INTEGER,
    "FLOAT": DataType.FLOAT,
    "REAL": DataType.FLOAT,
    "DOUBLE": DataType.FLOAT,
    "NUMERIC": DataType.DECIMAL,
    "DECIMAL": DataType.DECIMAL,
    "BOOLEAN": DataType.BOOLEAN,
    "VARCHAR": DataType.STRING,
    "CHAR": DataType.STRING,
    "TEXT": DataType.TEXT,
    "DATE": DataType.DATE,
    "TIME": DataType.TIME,
    "DATETIME": DataType.DATETIME,
    "TIMESTAMP": DataType.TIMESTAMP,
    "BLOB": DataType.BYTES,
    "BYTEA": DataType.BYTES,
    "JSON": DataType.JSON,
    "JSONB": DataType.JSON,
}


def detect_dialect(connection_string: str) -> SourceType:
    """Detect SQL dialect from connection string."""
    parsed = urlparse(connection_string)
    scheme = parsed.scheme.split("+")[0]
    
    if scheme in ("postgresql", "postgres"):
        return SourceType.POSTGRES
    elif scheme == "mysql":
        return SourceType.MYSQL
    elif scheme == "sqlite":
        return SourceType.SQLITE
    else:
        raise ValueError(f"Unsupported SQL dialect: {scheme}")


def to_async_url(connection_string: str) -> str:
    """Convert sync connection URL to async driver URL."""
    parsed = urlparse(connection_string)
    scheme = parsed.scheme.split("+")[0]
    
    driver_map = {
        "postgresql": "postgresql+asyncpg",
        "postgres": "postgresql+asyncpg",
        "mysql": "mysql+aiomysql",
        "sqlite": "sqlite+aiosqlite",
    }
    
    new_scheme = driver_map.get(scheme, scheme)
    return connection_string.replace(parsed.scheme, new_scheme, 1)


class SqlAdapter(DataSource):
    """Adapter for SQL databases (Postgres, MySQL, SQLite)."""
    
    def __init__(
        self,
        source_id: str,
        connection_string: str,
    ):
        self._source_id = source_id
        self._connection_string = connection_string
        self._source_type = detect_dialect(connection_string)
        self._engine: AsyncEngine | None = None
    
    async def _get_engine(self) -> AsyncEngine:
        if self._engine is None:
            async_url = to_async_url(self._connection_string)
            self._engine = create_async_engine(async_url, echo=False)
        return self._engine
    
    @property
    def source_id(self) -> str:
        return self._source_id
    
    @property
    def source_type(self) -> SourceType:
        return self._source_type
    
    async def discover_schema(
        self, 
        options: DiscoveryOptions | None = None
    ) -> Schema:
        options = options or DiscoveryOptions()
        engine = await self._get_engine()
        
        entities = []
        relationships = []
        
        async with engine.connect() as conn:
            # Use run_sync for SQLAlchemy inspection (it's not async-native)
            def sync_inspect(sync_conn):
                inspector = inspect(sync_conn)
                return {
                    "tables": inspector.get_table_names(),
                    "views": inspector.get_view_names(),
                }
            
            info = await conn.run_sync(sync_inspect)
            
            # Process tables
            for table_name in info["tables"]:
                if options.entities and table_name not in options.entities:
                    continue
                
                entity = await self._discover_entity(
                    conn, table_name, EntityType.TABLE, options
                )
                entities.append(entity)
            
            # Process views
            for view_name in info["views"]:
                if options.entities and view_name not in options.entities:
                    continue
                
                entity = await self._discover_entity(
                    conn, view_name, EntityType.VIEW, options
                )
                entities.append(entity)
            
            # Discover foreign key relationships
            relationships = await self._discover_relationships(conn, entities)
        
        # Calculate stats
        stats = SchemaStats(
            total_entities=len(entities),
            total_fields=sum(len(e.fields) for e in entities),
            total_rows=sum(e.row_count or 0 for e in entities),
            estimated_size_bytes=None,
        )
        
        # Generate summary
        summary = self._generate_summary(entities, relationships)
        
        return Schema(
            source_id=self._source_id,
            source_type=self._source_type,
            entities=entities,
            relationships=relationships,
            summary=summary,
            stats=stats,
        )
    
    async def _discover_entity(
        self,
        conn,
        name: str,
        entity_type: EntityType,
        options: DiscoveryOptions,
    ) -> Entity:
        """Discover a single entity (table or view)."""
        
        # Get columns
        def sync_get_columns(sync_conn):
            inspector = inspect(sync_conn)
            columns = inspector.get_columns(name)
            pk_constraint = inspector.get_pk_constraint(name)
            pk_columns = pk_constraint.get("constrained_columns", []) if pk_constraint else []
            fk_constraints = inspector.get_foreign_keys(name)
            
            return columns, pk_columns, fk_constraints
        
        columns, pk_columns, fk_constraints = await conn.run_sync(sync_get_columns)
        
        # Build FK lookup
        fk_lookup = {}
        for fk in fk_constraints:
            for local_col, remote_col in zip(
                fk["constrained_columns"], 
                fk["referred_columns"]
            ):
                fk_lookup[local_col] = FieldId(
                    source_id=self._source_id,
                    entity=fk["referred_table"],
                    field=remote_col,
                )
        
        # Build fields
        fields = []
        for col in columns:
            col_name = col["name"]
            type_str = str(col["type"]).upper().split("(")[0]
            data_type = TYPE_MAP.get(type_str, DataType.UNKNOWN)
            
            field = Field(
                name=col_name,
                data_type=data_type,
                nullable=col.get("nullable", True),
                is_primary_key=col_name in pk_columns,
                is_foreign_key=col_name in fk_lookup,
                foreign_key_ref=fk_lookup.get(col_name),
                original_type=str(col["type"]),
            )
            fields.append(field)
        
        # Get row count
        row_count = None
        try:
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {name}"))
            row_count = result.scalar()
        except Exception:
            pass
        
        # Get sample data
        sample_data = []
        if options.include_samples:
            sample_data = await self._sample_entity(conn, name, options.sample_size)
        
        # Get cardinality for each field
        if options.include_cardinality:
            for field in fields:
                field.cardinality = await self._get_cardinality(conn, name, field.name)
                field.sample_values = await self._get_sample_values(conn, name, field.name)
        
        return Entity(
            name=name,
            entity_type=entity_type,
            fields=fields,
            row_count=row_count,
            sample_data=sample_data,
        )
    
    async def _sample_entity(
        self, 
        conn, 
        name: str, 
        n: int
    ) -> list[dict[str, Any]]:
        """Get sample rows from an entity."""
        try:
            result = await conn.execute(text(f"SELECT * FROM {name} LIMIT {n}"))
            rows = result.fetchall()
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]
        except Exception:
            return []
    
    async def _get_cardinality(
        self, 
        conn, 
        table: str, 
        column: str
    ) -> Cardinality | None:
        """Get cardinality statistics for a column."""
        try:
            query = text(f"""
                SELECT 
                    COUNT(DISTINCT "{column}") as unique_count,
                    SUM(CASE WHEN "{column}" IS NULL THEN 1 ELSE 0 END) as null_count,
                    COUNT(*) as total_count
                FROM {table}
            """)
            result = await conn.execute(query)
            row = result.fetchone()
            return Cardinality(
                unique_count=row[0] or 0,
                null_count=row[1] or 0,
                total_count=row[2] or 0,
            )
        except Exception:
            return None
    
    async def _get_sample_values(
        self, 
        conn, 
        table: str, 
        column: str,
        n: int = 5
    ) -> list[Any]:
        """Get sample distinct values for a column."""
        try:
            query = text(f"""
                SELECT DISTINCT "{column}" 
                FROM {table} 
                WHERE "{column}" IS NOT NULL 
                LIMIT {n}
            """)
            result = await conn.execute(query)
            return [row[0] for row in result.fetchall()]
        except Exception:
            return []
    
    async def _discover_relationships(
        self, 
        conn, 
        entities: list[Entity]
    ) -> list[Relationship]:
        """Discover relationships from foreign keys."""
        relationships = []
        
        for entity in entities:
            for field in entity.fields:
                if field.is_foreign_key and field.foreign_key_ref:
                    rel = Relationship(
                        id=f"{entity.name}.{field.name}->{field.foreign_key_ref}",
                        from_field=FieldId(
                            source_id=self._source_id,
                            entity=entity.name,
                            field=field.name,
                        ),
                        to_field=field.foreign_key_ref,
                        relationship_type=RelationshipType.MANY_TO_ONE,
                        confidence=Confidence.CERTAIN,
                        inferred_by=InferenceMethod.EXPLICIT_CONSTRAINT,
                    )
                    relationships.append(rel)
        
        return relationships
    
    def _generate_summary(
        self, 
        entities: list[Entity], 
        relationships: list[Relationship]
    ) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Database with {len(entities)} tables/views and {len(relationships)} relationships.",
            "",
            "Tables:"
        ]
        for e in entities[:10]:  # First 10
            lines.append(f"  - {e.name} ({e.row_count or '?'} rows, {len(e.fields)} columns)")
        if len(entities) > 10:
            lines.append(f"  ... and {len(entities) - 10} more")
        
        return "\n".join(lines)
    
    async def query(self, query: Query) -> QueryResult:
        """Execute a query."""
        engine = await self._get_engine()
        start = time.time()
        
        async with engine.connect() as conn:
            if isinstance(query, SqlQuery):
                result = await conn.execute(text(query.sql), query.params)
                rows = result.fetchall()
                columns = list(result.keys())
            
            elif isinstance(query, GetQuery):
                sql = f'SELECT * FROM {query.entity} WHERE "{query.key}" = :value'
                result = await conn.execute(text(sql), {"value": query.value})
                rows = result.fetchall()
                columns = list(result.keys())
            
            else:
                raise ValueError(f"Unsupported query type: {type(query)}")
        
        elapsed = (time.time() - start) * 1000
        
        return QueryResult(
            columns=columns,
            rows=[list(row) for row in rows],
            total_count=len(rows),
            truncated=False,
            execution_time_ms=elapsed,
            source_id=self._source_id,
        )
    
    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk data according to strategy."""
        engine = await self._get_engine()
        
        if isinstance(strategy, FixedRowsStrategy):
            return await self._chunk_by_rows(engine, entity, strategy.rows_per_chunk)
        else:
            raise ValueError(f"Unsupported chunk strategy for SQL: {type(strategy)}")
    
    async def _chunk_by_rows(
        self, 
        engine: AsyncEngine, 
        entity: str, 
        rows_per_chunk: int
    ) -> list[Chunk]:
        """Chunk by fixed row count."""
        chunks = []
        
        async with engine.connect() as conn:
            # Get total count
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {entity}"))
            total_rows = result.scalar()
            total_chunks = (total_rows + rows_per_chunk - 1) // rows_per_chunk
            
            for i in range(total_chunks):
                offset = i * rows_per_chunk
                sql = f"SELECT * FROM {entity} LIMIT {rows_per_chunk} OFFSET {offset}"
                result = await conn.execute(text(sql))
                rows = result.fetchall()
                columns = list(result.keys())
                
                data = [dict(zip(columns, row)) for row in rows]
                
                chunk = Chunk(
                    id=f"{self._source_id}:{entity}:chunk_{i}",
                    source_id=self._source_id,
                    entity=entity,
                    index=i,
                    total_chunks=total_chunks,
                    data=data,
                    metadata=ChunkMetadata(
                        row_range=(offset, offset + len(rows)),
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
        """Sample data from an entity."""
        strategy = strategy or FirstN(5)
        engine = await self._get_engine()
        
        async with engine.connect() as conn:
            if isinstance(strategy, FirstN):
                return await self._sample_entity(conn, entity, strategy.n)
            elif isinstance(strategy, RandomSample):
                # SQLite and others have different random syntax
                if self._source_type == SourceType.POSTGRES:
                    sql = f"SELECT * FROM {entity} ORDER BY RANDOM() LIMIT {strategy.n}"
                else:
                    sql = f"SELECT * FROM {entity} ORDER BY RANDOM() LIMIT {strategy.n}"
                result = await conn.execute(text(sql))
                rows = result.fetchall()
                columns = list(result.keys())
                return [dict(zip(columns, row)) for row in rows]
            else:
                return await self._sample_entity(conn, entity, 5)
    
    async def health_check(self) -> HealthStatus:
        """Check database connectivity."""
        start = time.time()
        try:
            engine = await self._get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=True, latency_ms=elapsed)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=False, latency_ms=elapsed, message=str(e))
    
    async def close(self) -> None:
        """Close the connection pool."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None


# Convenience factory functions
async def postgres(source_id: str, connection_string: str) -> SqlAdapter:
    """Create a Postgres adapter."""
    return SqlAdapter(source_id, connection_string)


async def mysql(source_id: str, connection_string: str) -> SqlAdapter:
    """Create a MySQL adapter."""
    return SqlAdapter(source_id, connection_string)


async def sqlite(source_id: str, path: str) -> SqlAdapter:
    """Create a SQLite adapter."""
    connection_string = f"sqlite:///{path}"
    return SqlAdapter(source_id, connection_string)
```

### 5.2 Filesystem Adapter

```python
# cgc/adapters/filesystem.py

from __future__ import annotations
import asyncio
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator
import hashlib

import aiofiles
import aiofiles.os

from .base import (
    DataSource, DiscoveryOptions, SampleStrategy, FirstN, HealthStatus
)
from ..core.schema import (
    Schema, SourceType, Entity, EntityType, Field, DataType, SchemaStats
)
from ..core.query import Query, PatternQuery, QueryResult
from ..core.chunk import (
    Chunk, ChunkStrategy, FixedRowsStrategy, FixedTokensStrategy,
    BySectionsStrategy, ChunkMetadata, estimate_tokens
)
from ..core.graph import Relationship, RelationshipType, Confidence, InferenceMethod


class FileType:
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    BINARY = "binary"
    DIRECTORY = "directory"


EXTENSION_MAP = {
    ".csv": FileType.CSV,
    ".tsv": FileType.CSV,
    ".json": FileType.JSON,
    ".jsonl": FileType.JSONL,
    ".ndjson": FileType.JSONL,
    ".parquet": FileType.PARQUET,
    ".txt": FileType.TEXT,
    ".log": FileType.TEXT,
    ".md": FileType.MARKDOWN,
    ".markdown": FileType.MARKDOWN,
    ".pdf": FileType.PDF,
}


class FilesystemAdapter(DataSource):
    """Adapter for local filesystem."""
    
    def __init__(self, source_id: str, root_path: str):
        self._source_id = source_id
        self._root = Path(root_path).resolve()
        
        if not self._root.exists():
            raise ValueError(f"Path does not exist: {self._root}")
    
    @property
    def source_id(self) -> str:
        return self._source_id
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.FILESYSTEM
    
    def _detect_file_type(self, path: Path) -> str:
        """Detect file type from extension or content."""
        if path.is_dir():
            return FileType.DIRECTORY
        
        suffix = path.suffix.lower()
        return EXTENSION_MAP.get(suffix, FileType.BINARY)
    
    async def discover_schema(
        self, 
        options: DiscoveryOptions | None = None
    ) -> Schema:
        options = options or DiscoveryOptions()
        entities = []
        relationships = []
        
        # Walk directory tree
        for item in self._root.rglob("*"):
            rel_path = str(item.relative_to(self._root))
            
            if options.entities and rel_path not in options.entities:
                continue
            
            file_type = self._detect_file_type(item)
            
            if file_type == FileType.DIRECTORY:
                entity = Entity(
                    name=rel_path,
                    entity_type=EntityType.DIRECTORY,
                    fields=[],
                )
            elif file_type == FileType.CSV:
                entity = await self._discover_csv(item, rel_path, options)
            elif file_type in (FileType.JSON, FileType.JSONL):
                entity = await self._discover_json(item, rel_path, file_type, options)
            elif file_type in (FileType.TEXT, FileType.MARKDOWN):
                entity = await self._discover_text(item, rel_path, options)
            else:
                entity = Entity(
                    name=rel_path,
                    entity_type=EntityType.FILE,
                    fields=[Field(name="content", data_type=DataType.BYTES)],
                    row_count=1,
                )
            
            entities.append(entity)
        
        # Infer directory containment relationships
        relationships = self._infer_containment(entities)
        
        stats = SchemaStats(
            total_entities=len(entities),
            total_fields=sum(len(e.fields) for e in entities),
            total_rows=None,
            estimated_size_bytes=sum(
                item.stat().st_size for item in self._root.rglob("*") if item.is_file()
            ),
        )
        
        return Schema(
            source_id=self._source_id,
            source_type=self._source_type,
            entities=entities,
            relationships=relationships,
            summary=f"Filesystem at {self._root} with {len(entities)} files/directories",
            stats=stats,
        )
    
    async def _discover_csv(
        self, 
        path: Path, 
        name: str, 
        options: DiscoveryOptions
    ) -> Entity:
        """Discover schema from CSV file."""
        fields = []
        sample_data = []
        row_count = 0
        
        async with aiofiles.open(path, mode='r', newline='') as f:
            content = await f.read()
            reader = csv.DictReader(content.splitlines())
            
            rows = list(reader)
            row_count = len(rows)
            
            if rows:
                # Infer fields from first row
                for col_name in rows[0].keys():
                    data_type = self._infer_type_from_values([r.get(col_name) for r in rows[:100]])
                    fields.append(Field(
                        name=col_name,
                        data_type=data_type,
                        nullable=True,
                    ))
                
                if options.include_samples:
                    sample_data = rows[:options.sample_size]
        
        return Entity(
            name=name,
            entity_type=EntityType.FILE,
            fields=fields,
            row_count=row_count,
            sample_data=sample_data,
        )
    
    async def _discover_json(
        self,
        path: Path,
        name: str,
        file_type: str,
        options: DiscoveryOptions,
    ) -> Entity:
        """Discover schema from JSON/JSONL file."""
        fields = []
        sample_data = []
        row_count = 0
        
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
            
            if file_type == FileType.JSONL:
                rows = [json.loads(line) for line in content.strip().split('\n') if line.strip()]
            else:
                data = json.loads(content)
                rows = data if isinstance(data, list) else [data]
            
            row_count = len(rows)
            
            if rows and isinstance(rows[0], dict):
                # Infer fields from first row
                for key, value in rows[0].items():
                    data_type = self._infer_type_from_value(value)
                    fields.append(Field(
                        name=key,
                        data_type=data_type,
                        nullable=True,
                    ))
                
                if options.include_samples:
                    sample_data = rows[:options.sample_size]
        
        return Entity(
            name=name,
            entity_type=EntityType.FILE,
            fields=fields,
            row_count=row_count,
            sample_data=sample_data,
        )
    
    async def _discover_text(
        self,
        path: Path,
        name: str,
        options: DiscoveryOptions,
    ) -> Entity:
        """Discover schema from text file."""
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
        
        lines = content.split('\n')
        
        return Entity(
            name=name,
            entity_type=EntityType.FILE,
            fields=[
                Field(name="content", data_type=DataType.TEXT),
                Field(name="line_count", data_type=DataType.INTEGER),
                Field(name="char_count", data_type=DataType.INTEGER),
            ],
            row_count=1,
            sample_data=[{
                "content": content[:1000] + ("..." if len(content) > 1000 else ""),
                "line_count": len(lines),
                "char_count": len(content),
            }] if options.include_samples else [],
        )
    
    def _infer_type_from_values(self, values: list) -> DataType:
        """Infer data type from a list of values."""
        for value in values:
            if value is None or value == "":
                continue
            return self._infer_type_from_value(value)
        return DataType.STRING
    
    def _infer_type_from_value(self, value: Any) -> DataType:
        """Infer data type from a single value."""
        if value is None:
            return DataType.STRING
        if isinstance(value, bool):
            return DataType.BOOLEAN
        if isinstance(value, int):
            return DataType.INTEGER
        if isinstance(value, float):
            return DataType.FLOAT
        if isinstance(value, list):
            return DataType.ARRAY
        if isinstance(value, dict):
            return DataType.JSON
        
        # Try parsing string values
        if isinstance(value, str):
            # Integer
            try:
                int(value)
                return DataType.INTEGER
            except ValueError:
                pass
            
            # Float
            try:
                float(value)
                return DataType.FLOAT
            except ValueError:
                pass
            
            # Boolean
            if value.lower() in ('true', 'false'):
                return DataType.BOOLEAN
        
        return DataType.STRING
    
    def _infer_containment(self, entities: list[Entity]) -> list[Relationship]:
        """Infer directory containment relationships."""
        relationships = []
        
        dirs = [e for e in entities if e.entity_type == EntityType.DIRECTORY]
        files = [e for e in entities if e.entity_type == EntityType.FILE]
        
        for file_entity in files:
            file_path = Path(file_entity.name)
            parent = str(file_path.parent)
            
            if parent == ".":
                continue
            
            # Find parent directory
            for dir_entity in dirs:
                if dir_entity.name == parent:
                    rel = Relationship(
                        id=f"{dir_entity.name}->contains->{file_entity.name}",
                        from_field=FieldId(self._source_id, dir_entity.name, ""),
                        to_field=FieldId(self._source_id, file_entity.name, ""),
                        relationship_type=RelationshipType.CONTAINS,
                        confidence=Confidence.CERTAIN,
                        inferred_by=InferenceMethod.EXPLICIT_CONSTRAINT,
                    )
                    relationships.append(rel)
                    break
        
        return relationships
    
    async def query(self, query: Query) -> QueryResult:
        """Execute a query (pattern search for filesystem)."""
        start = time.time()
        
        if isinstance(query, PatternQuery):
            return await self._pattern_search(query)
        else:
            raise ValueError(f"Unsupported query type for filesystem: {type(query)}")
    
    async def _pattern_search(self, query: PatternQuery) -> QueryResult:
        """Search for pattern in files."""
        start = time.time()
        results = []
        
        path = self._root / query.entity
        if not path.exists():
            raise ValueError(f"Entity not found: {query.entity}")
        
        flags = 0 if query.case_sensitive else re.IGNORECASE
        pattern = re.compile(query.pattern, flags)
        
        async with aiofiles.open(path, mode='r') as f:
            line_num = 0
            async for line in f:
                line_num += 1
                if pattern.search(line):
                    results.append([line_num, line.strip()])
        
        elapsed = (time.time() - start) * 1000
        
        return QueryResult(
            columns=["line_number", "content"],
            rows=results,
            total_count=len(results),
            execution_time_ms=elapsed,
            source_id=self._source_id,
        )
    
    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk a file according to strategy."""
        path = self._root / entity
        if not path.exists():
            raise ValueError(f"Entity not found: {entity}")
        
        file_type = self._detect_file_type(path)
        
        if isinstance(strategy, FixedRowsStrategy):
            if file_type == FileType.CSV:
                return await self._chunk_csv_by_rows(path, entity, strategy.rows_per_chunk)
            elif file_type == FileType.JSONL:
                return await self._chunk_jsonl_by_rows(path, entity, strategy.rows_per_chunk)
        
        elif isinstance(strategy, FixedTokensStrategy):
            return await self._chunk_by_tokens(path, entity, strategy.tokens_per_chunk, strategy.estimator)
        
        elif isinstance(strategy, BySectionsStrategy):
            return await self._chunk_by_sections(path, entity, strategy.delimiters)
        
        raise ValueError(f"Unsupported chunk strategy for {file_type}: {type(strategy)}")
    
    async def _chunk_csv_by_rows(
        self, 
        path: Path, 
        entity: str, 
        rows_per_chunk: int
    ) -> list[Chunk]:
        """Chunk CSV by rows."""
        chunks = []
        
        async with aiofiles.open(path, mode='r', newline='') as f:
            content = await f.read()
            reader = csv.DictReader(content.splitlines())
            rows = list(reader)
        
        total_rows = len(rows)
        total_chunks = (total_rows + rows_per_chunk - 1) // rows_per_chunk
        
        for i in range(total_chunks):
            start_idx = i * rows_per_chunk
            end_idx = min(start_idx + rows_per_chunk, total_rows)
            chunk_rows = rows[start_idx:end_idx]
            
            chunk = Chunk(
                id=f"{self._source_id}:{entity}:chunk_{i}",
                source_id=self._source_id,
                entity=entity,
                index=i,
                total_chunks=total_chunks,
                data=chunk_rows,
                metadata=ChunkMetadata(
                    row_range=(start_idx, end_idx),
                    estimated_tokens=estimate_tokens(str(chunk_rows)),
                    file_path=str(path),
                ),
            )
            chunks.append(chunk)
        
        return chunks
    
    async def _chunk_jsonl_by_rows(
        self,
        path: Path,
        entity: str,
        rows_per_chunk: int,
    ) -> list[Chunk]:
        """Chunk JSONL by rows."""
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
        
        lines = [json.loads(line) for line in content.strip().split('\n') if line.strip()]
        total_rows = len(lines)
        total_chunks = (total_rows + rows_per_chunk - 1) // rows_per_chunk
        
        chunks = []
        for i in range(total_chunks):
            start_idx = i * rows_per_chunk
            end_idx = min(start_idx + rows_per_chunk, total_rows)
            chunk_rows = lines[start_idx:end_idx]
            
            chunk = Chunk(
                id=f"{self._source_id}:{entity}:chunk_{i}",
                source_id=self._source_id,
                entity=entity,
                index=i,
                total_chunks=total_chunks,
                data=chunk_rows,
                metadata=ChunkMetadata(
                    row_range=(start_idx, end_idx),
                    estimated_tokens=estimate_tokens(str(chunk_rows)),
                    file_path=str(path),
                ),
            )
            chunks.append(chunk)
        
        return chunks
    
    async def _chunk_by_tokens(
        self,
        path: Path,
        entity: str,
        tokens_per_chunk: int,
        estimator,
    ) -> list[Chunk]:
        """Chunk text file by approximate token count."""
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
        
        # Estimate chars per chunk
        chars_per_chunk = tokens_per_chunk * 4  # Rough estimate
        
        chunks = []
        total_chunks = (len(content) + chars_per_chunk - 1) // chars_per_chunk
        
        for i in range(total_chunks):
            start_idx = i * chars_per_chunk
            end_idx = min(start_idx + chars_per_chunk, len(content))
            chunk_text = content[start_idx:end_idx]
            
            chunk = Chunk(
                id=f"{self._source_id}:{entity}:chunk_{i}",
                source_id=self._source_id,
                entity=entity,
                index=i,
                total_chunks=total_chunks,
                data=chunk_text,
                metadata=ChunkMetadata(
                    byte_range=(start_idx, end_idx),
                    estimated_tokens=estimate_tokens(chunk_text, estimator),
                    file_path=str(path),
                ),
            )
            chunks.append(chunk)
        
        return chunks
    
    async def _chunk_by_sections(
        self,
        path: Path,
        entity: str,
        delimiters: list[str],
    ) -> list[Chunk]:
        """Chunk by section delimiters (e.g., markdown headers)."""
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
        
        # Build regex pattern from delimiters
        patterns = [re.escape(d) for d in delimiters]
        pattern = re.compile(f"^({'|'.join(patterns)})", re.MULTILINE)
        
        # Split by pattern
        parts = pattern.split(content)
        
        # Recombine delimiter with following content
        sections = []
        i = 0
        while i < len(parts):
            if i == 0 and not pattern.match(parts[0]):
                # Content before first delimiter
                if parts[0].strip():
                    sections.append(parts[0])
                i += 1
            else:
                # Delimiter + content
                section = parts[i]
                if i + 1 < len(parts):
                    section += parts[i + 1]
                    i += 2
                else:
                    i += 1
                if section.strip():
                    sections.append(section)
        
        chunks = []
        for i, section in enumerate(sections):
            chunk = Chunk(
                id=f"{self._source_id}:{entity}:section_{i}",
                source_id=self._source_id,
                entity=entity,
                index=i,
                total_chunks=len(sections),
                data=section,
                metadata=ChunkMetadata(
                    estimated_tokens=estimate_tokens(section),
                    file_path=str(path),
                ),
            )
            chunks.append(chunk)
        
        return chunks
    
    async def sample(
        self,
        entity: str,
        strategy: SampleStrategy | None = None,
    ) -> list[dict[str, Any]]:
        """Sample data from a file."""
        path = self._root / entity
        file_type = self._detect_file_type(path)
        strategy = strategy or FirstN(5)
        n = getattr(strategy, 'n', 5)
        
        if file_type == FileType.CSV:
            async with aiofiles.open(path, mode='r', newline='') as f:
                content = await f.read()
                reader = csv.DictReader(content.splitlines())
                return list(reader)[:n]
        
        elif file_type == FileType.JSONL:
            async with aiofiles.open(path, mode='r') as f:
                content = await f.read()
            lines = content.strip().split('\n')[:n]
            return [json.loads(line) for line in lines if line.strip()]
        
        elif file_type == FileType.JSON:
            async with aiofiles.open(path, mode='r') as f:
                content = await f.read()
            data = json.loads(content)
            if isinstance(data, list):
                return data[:n]
            return [data]
        
        else:
            async with aiofiles.open(path, mode='r') as f:
                content = await f.read()
            return [{"content": content[:10000]}]
    
    async def health_check(self) -> HealthStatus:
        """Check if root path is accessible."""
        start = time.time()
        try:
            exists = await aiofiles.os.path.exists(self._root)
            elapsed = (time.time() - start) * 1000
            if exists:
                return HealthStatus(healthy=True, latency_ms=elapsed)
            return HealthStatus(healthy=False, latency_ms=elapsed, message="Path not found")
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=False, latency_ms=elapsed, message=str(e))


# Convenience factory
def local(source_id: str, path: str) -> FilesystemAdapter:
    """Create a local filesystem adapter."""
    return FilesystemAdapter(source_id, path)
```

### 5.3 Vector Adapter (Qdrant)

```python
# cgc/adapters/vector.py

from __future__ import annotations
import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from .base import DataSource, DiscoveryOptions, SampleStrategy, FirstN, HealthStatus
from ..core.schema import Schema, SourceType, Entity, EntityType, Field, DataType, SchemaStats
from ..core.query import Query, SemanticQuery, QueryResult
from ..core.chunk import Chunk, ChunkStrategy


class QdrantAdapter(DataSource):
    """Adapter for Qdrant vector database."""
    
    def __init__(
        self,
        source_id: str,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
    ):
        self._source_id = source_id
        self._url = url
        self._client = QdrantClient(url=url, api_key=api_key)
    
    @property
    def source_id(self) -> str:
        return self._source_id
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.QDRANT
    
    async def discover_schema(
        self, 
        options: DiscoveryOptions | None = None
    ) -> Schema:
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
            
            # Add payload fields if we can infer them
            if options.include_samples:
                sample_points = self._client.scroll(
                    collection_name=name,
                    limit=options.sample_size,
                    with_payload=True,
                    with_vectors=False,
                )[0]
                
                if sample_points:
                    payload_fields = set()
                    for point in sample_points:
                        if point.payload:
                            payload_fields.update(point.payload.keys())
                    
                    for field_name in payload_fields:
                        fields.append(Field(
                            name=field_name,
                            data_type=DataType.JSON,  # Payload is flexible
                        ))
            
            entity = Entity(
                name=name,
                entity_type=EntityType.INDEX,
                fields=fields,
                row_count=info.points_count,
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
        """Execute a vector search query."""
        start = time.time()
        
        if isinstance(query, SemanticQuery):
            # Note: In real usage, you'd need to embed the query text first
            # This assumes query.query is already a vector or you have an embedder
            raise NotImplementedError(
                "SemanticQuery requires an embedding model. "
                "Use search_by_vector() instead, or provide embeddings."
            )
        else:
            raise ValueError(f"Unsupported query type for Qdrant: {type(query)}")
    
    def search_by_vector(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search by vector (synchronous, for direct use)."""
        results = self._client.search(
            collection_name=collection,
            query_vector=vector,
            limit=top_k,
            score_threshold=threshold,
            with_payload=True,
        )
        
        return [
            {
                "id": str(r.id),
                "score": r.score,
                **r.payload,
            }
            for r in results
        ]
    
    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk vector collection (scroll through points)."""
        # For vector DBs, chunking means scrolling through points
        # This is less common but supported
        
        chunks = []
        offset = None
        chunk_index = 0
        
        # Get total count
        info = self._client.get_collection(entity)
        total_points = info.points_count
        chunk_size = 100  # Points per chunk
        total_chunks = (total_points + chunk_size - 1) // chunk_size
        
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
            
            data = [
                {"id": str(p.id), **p.payload}
                for p in points
            ]
            
            chunk = Chunk(
                id=f"{self._source_id}:{entity}:chunk_{chunk_index}",
                source_id=self._source_id,
                entity=entity,
                index=chunk_index,
                total_chunks=total_chunks,
                data=data,
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
        n = getattr(strategy, 'n', 5) if strategy else 5
        
        points, _ = self._client.scroll(
            collection_name=entity,
            limit=n,
            with_payload=True,
            with_vectors=False,
        )
        
        return [
            {"id": str(p.id), **p.payload}
            for p in points
        ]
    
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
) -> QdrantAdapter:
    """Create a Qdrant adapter."""
    return QdrantAdapter(source_id, url, api_key)
```

---

## 6. Relationship Discovery Engine

```python
# cgc/discovery/engine.py

from __future__ import annotations
from abc import ABC, abstractmethod
import re
from typing import TYPE_CHECKING

from ..core.schema import Schema, Field, FieldId
from ..core.graph import (
    Relationship, RelationshipGraph, RelationshipType, 
    Confidence, InferenceMethod
)

if TYPE_CHECKING:
    from ..adapters.base import DataSource


class InferenceRule(ABC):
    """Base class for relationship inference rules."""
    
    @abstractmethod
    def infer(
        self,
        schemas: list[Schema],
    ) -> list[Relationship]:
        """Infer relationships from schemas."""
        ...


class NamingConventionRule(InferenceRule):
    """Infer relationships from naming conventions like user_id -> users.id"""
    
    def __init__(self):
        self.patterns = [
            # user_id -> users.id
            (re.compile(r'^(.+)_id$'), lambda m: f"{m.group(1)}s", "id"),
            # userId -> users.id
            (re.compile(r'^(.+)Id$'), lambda m: f"{m.group(1).lower()}s", "id"),
            # author_user_id -> users.id
            (re.compile(r'^.+_user_id$'), lambda m: "users", "id"),
            # post_uuid -> posts.uuid
            (re.compile(r'^(.+)_uuid$'), lambda m: f"{m.group(1)}s", "uuid"),
        ]
    
    def infer(self, schemas: list[Schema]) -> list[Relationship]:
        relationships = []
        
        # Build lookup of all entities
        entity_lookup: dict[str, tuple[Schema, Entity]] = {}
        for schema in schemas:
            for entity in schema.entities:
                entity_lookup[entity.name.lower()] = (schema, entity)
        
        # Check each field against patterns
        for schema in schemas:
            for entity in schema.entities:
                for field in entity.fields:
                    for pattern, table_fn, target_field in self.patterns:
                        match = pattern.match(field.name)
                        if not match:
                            continue
                        
                        target_table = table_fn(match).lower()
                        
                        if target_table in entity_lookup:
                            target_schema, target_entity = entity_lookup[target_table]
                            
                            # Check if target field exists
                            if any(f.name == target_field for f in target_entity.fields):
                                rel = Relationship(
                                    id=f"{schema.source_id}.{entity.name}.{field.name}->{target_schema.source_id}.{target_entity.name}.{target_field}",
                                    from_field=FieldId(schema.source_id, entity.name, field.name),
                                    to_field=FieldId(target_schema.source_id, target_entity.name, target_field),
                                    relationship_type=RelationshipType.MANY_TO_ONE,
                                    confidence=Confidence.MEDIUM,
                                    inferred_by=InferenceMethod.NAMING_CONVENTION,
                                )
                                relationships.append(rel)
        
        return relationships


class CardinalityMatchRule(InferenceRule):
    """Infer relationships from matching cardinality."""
    
    def __init__(self, tolerance: float = 0.1):
        self.tolerance = tolerance
    
    def infer(self, schemas: list[Schema]) -> list[Relationship]:
        relationships = []
        
        # Collect fields with cardinality
        fields_with_cardinality = []
        for schema in schemas:
            for entity in schema.entities:
                for field in entity.fields:
                    if field.cardinality and field.cardinality.unique_count > 0:
                        fields_with_cardinality.append((schema, entity, field))
        
        # Compare pairs
        for i, (schema_a, entity_a, field_a) in enumerate(fields_with_cardinality):
            for schema_b, entity_b, field_b in fields_with_cardinality[i+1:]:
                # Skip same entity
                if entity_a.name == entity_b.name and schema_a.source_id == schema_b.source_id:
                    continue
                
                # Skip different types
                if field_a.data_type != field_b.data_type:
                    continue
                
                # Check cardinality match
                card_a = field_a.cardinality.unique_count
                card_b = field_b.cardinality.unique_count
                
                if card_a == 0 or card_b == 0:
                    continue
                
                ratio = min(card_a, card_b) / max(card_a, card_b)
                
                if ratio >= (1 - self.tolerance):
                    rel = Relationship(
                        id=f"cardinality:{schema_a.source_id}.{entity_a.name}.{field_a.name}<->{schema_b.source_id}.{entity_b.name}.{field_b.name}",
                        from_field=FieldId(schema_a.source_id, entity_a.name, field_a.name),
                        to_field=FieldId(schema_b.source_id, entity_b.name, field_b.name),
                        relationship_type=RelationshipType.SAME_ENTITY,
                        confidence=Confidence.LOW,
                        inferred_by=InferenceMethod.CARDINALITY_MATCH,
                        metadata={"cardinality_ratio": ratio},
                    )
                    relationships.append(rel)
        
        return relationships


class ValueOverlapRule(InferenceRule):
    """Infer relationships from sample value overlap."""
    
    def __init__(self, min_overlap: float = 0.5):
        self.min_overlap = min_overlap
    
    def infer(self, schemas: list[Schema]) -> list[Relationship]:
        relationships = []
        
        # Collect fields with sample values
        fields_with_samples = []
        for schema in schemas:
            for entity in schema.entities:
                for field in entity.fields:
                    if field.sample_values:
                        fields_with_samples.append((schema, entity, field))
        
        # Compare pairs
        for i, (schema_a, entity_a, field_a) in enumerate(fields_with_samples):
            for schema_b, entity_b, field_b in fields_with_samples[i+1:]:
                # Skip same entity
                if entity_a.name == entity_b.name and schema_a.source_id == schema_b.source_id:
                    continue
                
                # Skip different types
                if field_a.data_type != field_b.data_type:
                    continue
                
                # Calculate overlap
                set_a = set(str(v) for v in field_a.sample_values)
                set_b = set(str(v) for v in field_b.sample_values)
                
                if not set_a or not set_b:
                    continue
                
                intersection = len(set_a & set_b)
                union = len(set_a | set_b)
                overlap = intersection / union if union > 0 else 0
                
                if overlap >= self.min_overlap:
                    rel = Relationship(
                        id=f"overlap:{schema_a.source_id}.{entity_a.name}.{field_a.name}<->{schema_b.source_id}.{entity_b.name}.{field_b.name}",
                        from_field=FieldId(schema_a.source_id, entity_a.name, field_a.name),
                        to_field=FieldId(schema_b.source_id, entity_b.name, field_b.name),
                        relationship_type=RelationshipType.SAME_ENTITY,
                        confidence=Confidence.LOW,
                        inferred_by=InferenceMethod.VALUE_OVERLAP,
                        metadata={"overlap_ratio": overlap},
                    )
                    relationships.append(rel)
        
        return relationships


class RelationshipDiscoveryEngine:
    """Engine for discovering relationships across data sources."""
    
    def __init__(self):
        self.rules: list[InferenceRule] = [
            NamingConventionRule(),
            CardinalityMatchRule(),
            ValueOverlapRule(),
        ]
    
    def add_rule(self, rule: InferenceRule) -> None:
        """Add a custom inference rule."""
        self.rules.append(rule)
    
    def discover(self, schemas: list[Schema]) -> RelationshipGraph:
        """Discover relationships across all schemas."""
        graph = RelationshipGraph()
        
        # Add explicit relationships from schemas
        for schema in schemas:
            for rel in schema.relationships:
                graph.add(rel)
        
        # Run inference rules
        for rule in self.rules:
            inferred = rule.infer(schemas)
            for rel in inferred:
                # Avoid duplicates
                existing = graph.related_to(rel.from_field)
                is_duplicate = any(
                    r.to_field == rel.to_field for r in existing
                )
                if not is_duplicate:
                    graph.add(rel)
        
        return graph
```

---

## 7. Main Connector Class

```python
# cgc/connector.py

from __future__ import annotations
import asyncio
from typing import Any

from .core.schema import Schema, FieldId
from .core.query import Query, QueryResult
from .core.chunk import Chunk, ChunkStrategy
from .core.graph import RelationshipGraph
from .adapters.base import DataSource, DiscoveryOptions, HealthStatus
from .discovery.engine import RelationshipDiscoveryEngine
from .cache.sqlite import SqliteCache


class Connector:
    """Main interface for Context Graph Connector."""
    
    def __init__(self, cache_path: str | None = None):
        self._sources: dict[str, DataSource] = {}
        self._schemas: dict[str, Schema] = {}
        self._graph: RelationshipGraph | None = None
        self._discovery_engine = RelationshipDiscoveryEngine()
        self._cache = SqliteCache(cache_path) if cache_path else None
    
    # === Source Management ===
    
    def add_source(self, source: DataSource) -> None:
        """Add a data source."""
        self._sources[source.source_id] = source
        # Invalidate graph cache
        self._graph = None
    
    def remove_source(self, source_id: str) -> None:
        """Remove a data source."""
        if source_id in self._sources:
            del self._sources[source_id]
            self._schemas.pop(source_id, None)
            self._graph = None
    
    @property
    def sources(self) -> list[str]:
        """List connected source IDs."""
        return list(self._sources.keys())
    
    def get_source(self, source_id: str) -> DataSource:
        """Get a specific source."""
        if source_id not in self._sources:
            raise KeyError(f"Source not found: {source_id}")
        return self._sources[source_id]
    
    # === Schema Discovery ===
    
    async def discover(
        self, 
        source_id: str, 
        options: DiscoveryOptions | None = None,
        refresh: bool = False,
    ) -> Schema:
        """Discover schema for a source."""
        # Check cache
        if not refresh and source_id in self._schemas:
            return self._schemas[source_id]
        
        if self._cache and not refresh:
            cached = await self._cache.get_schema(source_id)
            if cached:
                self._schemas[source_id] = cached
                return cached
        
        # Discover
        source = self.get_source(source_id)
        schema = await source.discover_schema(options)
        
        # Cache
        self._schemas[source_id] = schema
        if self._cache:
            await self._cache.put_schema(schema)
        
        return schema
    
    async def discover_all(
        self, 
        options: DiscoveryOptions | None = None,
        refresh: bool = False,
    ) -> dict[str, Schema]:
        """Discover schemas for all sources."""
        tasks = [
            self.discover(source_id, options, refresh)
            for source_id in self._sources
        ]
        schemas = await asyncio.gather(*tasks)
        return dict(zip(self._sources.keys(), schemas))
    
    async def schema(self, source_id: str) -> Schema:
        """Get schema for a source (discover if needed)."""
        return await self.discover(source_id)
    
    # === Relationship Graph ===
    
    async def graph(self, refresh: bool = False) -> RelationshipGraph:
        """Get relationship graph across all sources."""
        if not refresh and self._graph:
            return self._graph
        
        # Discover all schemas first
        schemas = await self.discover_all()
        
        # Run discovery engine
        self._graph = self._discovery_engine.discover(list(schemas.values()))
        
        return self._graph
    
    # === Querying ===
    
    async def query(self, source_id: str, query: Query) -> QueryResult:
        """Execute a query against a source."""
        source = self.get_source(source_id)
        return await source.query(query)
    
    async def sql(self, source_id: str, sql: str, **params) -> QueryResult:
        """Execute a SQL query (convenience method)."""
        from .core.query import SqlQuery
        return await self.query(source_id, SqlQuery(sql=sql, params=params))
    
    # === Chunking ===
    
    async def chunk(
        self,
        source_id: str,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk data from a source."""
        source = self.get_source(source_id)
        return await source.chunk(entity, strategy)
    
    # === Sampling ===
    
    async def sample(
        self,
        source_id: str,
        entity: str,
        n: int = 5,
    ) -> list[dict[str, Any]]:
        """Sample data from a source."""
        from .adapters.base import FirstN
        source = self.get_source(source_id)
        return await source.sample(entity, FirstN(n))
    
    # === Cross-Source Operations ===
    
    async def find_related(
        self,
        field_id: FieldId,
        value: Any,
    ) -> list[dict[str, Any]]:
        """Find related records across sources."""
        graph = await self.graph()
        related = graph.related_to(field_id)
        
        results = []
        for rel in related:
            other_field = rel.other_side(field_id)
            if not other_field:
                continue
            
            # Query the related source
            from .core.query import GetQuery
            try:
                source = self.get_source(other_field.source_id)
                result = await source.query(GetQuery(
                    entity=other_field.entity,
                    key=other_field.field,
                    value=value,
                ))
                
                for row in result.to_dicts():
                    results.append({
                        "source_id": other_field.source_id,
                        "entity": other_field.entity,
                        "relationship": rel.relationship_type.value,
                        "record": row,
                    })
            except Exception:
                continue
        
        return results
    
    # === Health Checks ===
    
    async def health_check(self) -> dict[str, HealthStatus]:
        """Check health of all sources."""
        tasks = [
            source.health_check()
            for source in self._sources.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health = {}
        for source_id, result in zip(self._sources.keys(), results):
            if isinstance(result, Exception):
                health[source_id] = HealthStatus(
                    healthy=False, 
                    message=str(result)
                )
            else:
                health[source_id] = result
        
        return health
    
    # === Utilities ===
    
    def summary(self) -> str:
        """Generate compact summary for LLM context."""
        lines = [f"Connected sources: {len(self._sources)}"]
        
        for source_id, schema in self._schemas.items():
            lines.append(f"\n{schema.to_compact()}")
        
        if self._graph:
            lines.append(f"\nRelationships: {len(self._graph.relationships)}")
        
        return "\n".join(lines)
    
    async def close(self) -> None:
        """Close all connections."""
        for source in self._sources.values():
            await source.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# === Builder Pattern ===

class ConnectorBuilder:
    """Builder for creating Connector instances."""
    
    def __init__(self):
        self._sources: list[DataSource] = []
        self._cache_path: str | None = None
    
    def add_postgres(self, source_id: str, connection_string: str) -> ConnectorBuilder:
        from .adapters.sql import SqlAdapter
        self._sources.append(SqlAdapter(source_id, connection_string))
        return self
    
    def add_mysql(self, source_id: str, connection_string: str) -> ConnectorBuilder:
        from .adapters.sql import SqlAdapter
        self._sources.append(SqlAdapter(source_id, connection_string))
        return self
    
    def add_sqlite(self, source_id: str, path: str) -> ConnectorBuilder:
        from .adapters.sql import SqlAdapter
        self._sources.append(SqlAdapter(source_id, f"sqlite:///{path}"))
        return self
    
    def add_filesystem(self, source_id: str, path: str) -> ConnectorBuilder:
        from .adapters.filesystem import FilesystemAdapter
        self._sources.append(FilesystemAdapter(source_id, path))
        return self
    
    def add_qdrant(
        self, 
        source_id: str, 
        url: str = "http://localhost:6333",
        api_key: str | None = None,
    ) -> ConnectorBuilder:
        from .adapters.vector import QdrantAdapter
        self._sources.append(QdrantAdapter(source_id, url, api_key))
        return self
    
    def with_cache(self, path: str) -> ConnectorBuilder:
        self._cache_path = path
        return self
    
    def build(self) -> Connector:
        connector = Connector(cache_path=self._cache_path)
        for source in self._sources:
            connector.add_source(source)
        return connector
```

---

## 8. CLI

```python
# cgc/cli/main.py

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..connector import Connector, ConnectorBuilder
from ..core.chunk import FixedRowsStrategy, FixedTokensStrategy

app = typer.Typer(help="Context Graph Connector CLI")
console = Console()


def get_connector(config_path: str = "cgc.toml") -> Connector:
    """Load connector from config file."""
    # TODO: Implement config file loading
    # For now, return empty connector
    return Connector()


@app.command()
def init():
    """Initialize a new CGC configuration file."""
    config = """# CGC Configuration
[cache]
path = ".cgc/cache.db"

# Example sources:
# [[sources]]
# id = "main_db"
# type = "postgres"
# connection = "postgresql://localhost/myapp"

# [[sources]]
# id = "logs"
# type = "filesystem"
# path = "./logs"
"""
    Path("cgc.toml").write_text(config)
    console.print("[green]Created cgc.toml[/green]")


@app.command()
def sources():
    """List connected data sources."""
    connector = get_connector()
    
    if not connector.sources:
        console.print("[yellow]No sources configured[/yellow]")
        return
    
    table = Table(title="Connected Sources")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Status")
    
    async def check():
        health = await connector.health_check()
        for source_id in connector.sources:
            source = connector.get_source(source_id)
            status = health.get(source_id)
            status_str = "[green]✓[/green]" if status and status.healthy else "[red]✗[/red]"
            table.add_row(source_id, source.source_type.value, status_str)
    
    asyncio.run(check())
    console.print(table)


@app.command()
def discover(
    source_id: str,
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Force refresh"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Discover schema for a data source."""
    connector = get_connector()
    
    async def run():
        schema = await connector.discover(source_id, refresh=refresh)
        
        if output:
            # Export as JSON
            data = {
                "source_id": schema.source_id,
                "source_type": schema.source_type.value,
                "entities": [
                    {
                        "name": e.name,
                        "type": e.entity_type.value,
                        "fields": [f.name for f in e.fields],
                        "row_count": e.row_count,
                    }
                    for e in schema.entities
                ],
                "relationships": len(schema.relationships),
            }
            Path(output).write_text(json.dumps(data, indent=2))
            console.print(f"[green]Saved to {output}[/green]")
        else:
            console.print(schema.to_compact())
    
    asyncio.run(run())


@app.command()
def schema(
    source_id: str,
    entity: Optional[str] = typer.Option(None, "--entity", "-e", help="Specific entity"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show schema for a source."""
    connector = get_connector()
    
    async def run():
        schema = await connector.schema(source_id)
        
        if entity:
            e = schema.get_entity(entity)
            if not e:
                console.print(f"[red]Entity not found: {entity}[/red]")
                return
            
            table = Table(title=f"{entity} ({e.row_count or '?'} rows)")
            table.add_column("Field")
            table.add_column("Type")
            table.add_column("Nullable")
            table.add_column("PK")
            table.add_column("FK")
            
            for f in e.fields:
                table.add_row(
                    f.name,
                    f.data_type.value,
                    "✓" if f.nullable else "",
                    "✓" if f.is_primary_key else "",
                    str(f.foreign_key_ref) if f.is_foreign_key else "",
                )
            console.print(table)
        else:
            console.print(schema.to_compact())
    
    asyncio.run(run())


@app.command()
def graph(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, dot, json"),
):
    """Show relationship graph."""
    connector = get_connector()
    
    async def run():
        g = await connector.graph()
        
        if format == "dot":
            content = g.to_dot()
        elif format == "json":
            content = json.dumps([
                {
                    "from": str(r.from_field),
                    "to": str(r.to_field),
                    "type": r.relationship_type.value,
                    "confidence": r.confidence.value,
                }
                for r in g.relationships
            ], indent=2)
        else:
            lines = [f"Relationships: {len(g.relationships)}"]
            for r in g.relationships:
                lines.append(f"  {r.from_field} -> {r.to_field} ({r.relationship_type.value})")
            content = "\n".join(lines)
        
        if output:
            Path(output).write_text(content)
            console.print(f"[green]Saved to {output}[/green]")
        else:
            console.print(content)
    
    asyncio.run(run())


@app.command()
def query(
    source_id: str,
    sql: str,
    limit: int = typer.Option(100, "--limit", "-l", help="Max rows"),
):
    """Execute a SQL query."""
    connector = get_connector()
    
    async def run():
        result = await connector.sql(source_id, f"{sql} LIMIT {limit}")
        
        table = Table()
        for col in result.columns:
            table.add_column(col)
        
        for row in result.rows:
            table.add_row(*[str(v) for v in row])
        
        console.print(table)
        console.print(f"[dim]{len(result)} rows, {result.execution_time_ms:.1f}ms[/dim]")
    
    asyncio.run(run())


@app.command()
def chunk(
    source_id: str,
    entity: str,
    strategy: str = typer.Option("rows:1000", "--strategy", "-s", help="Chunking strategy"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """Chunk data from a source."""
    connector = get_connector()
    
    # Parse strategy
    if strategy.startswith("rows:"):
        n = int(strategy.split(":")[1])
        strat = FixedRowsStrategy(rows_per_chunk=n)
    elif strategy.startswith("tokens:"):
        n = int(strategy.split(":")[1])
        strat = FixedTokensStrategy(tokens_per_chunk=n)
    else:
        console.print(f"[red]Unknown strategy: {strategy}[/red]")
        return
    
    async def run():
        chunks = await connector.chunk(source_id, entity, strat)
        
        console.print(f"Created {len(chunks)} chunks")
        
        for chunk in chunks:
            console.print(f"  Chunk {chunk.index + 1}/{chunk.total_chunks}: ~{chunk.metadata.estimated_tokens} tokens")
        
        if output:
            out_dir = Path(output)
            out_dir.mkdir(parents=True, exist_ok=True)
            
            for chunk in chunks:
                chunk_file = out_dir / f"chunk_{chunk.index}.json"
                chunk_file.write_text(chunk.to_json())
            
            console.print(f"[green]Saved to {output}/[/green]")
    
    asyncio.run(run())


@app.command()
def sample(
    source_id: str,
    entity: str,
    n: int = typer.Option(5, "--n", "-n", help="Number of samples"),
):
    """Sample data from a source."""
    connector = get_connector()
    
    async def run():
        samples = await connector.sample(source_id, entity, n)
        
        if not samples:
            console.print("[yellow]No data[/yellow]")
            return
        
        table = Table()
        for col in samples[0].keys():
            table.add_column(col)
        
        for row in samples:
            table.add_row(*[str(v)[:50] for v in row.values()])
        
        console.print(table)
    
    asyncio.run(run())


@app.command()
def health():
    """Check health of all sources."""
    connector = get_connector()
    
    async def run():
        health = await connector.health_check()
        
        table = Table(title="Health Status")
        table.add_column("Source")
        table.add_column("Status")
        table.add_column("Latency")
        table.add_column("Message")
        
        for source_id, status in health.items():
            status_str = "[green]✓ Healthy[/green]" if status.healthy else "[red]✗ Unhealthy[/red]"
            table.add_row(
                source_id,
                status_str,
                f"{status.latency_ms:.1f}ms",
                status.message or "",
            )
        
        console.print(table)
    
    asyncio.run(run())


def main():
    app()


if __name__ == "__main__":
    main()
```

---

## 9. Usage Examples

### 9.1 Basic SQL Discovery

```python
import asyncio
from cgc import ConnectorBuilder

async def main():
    # Build connector
    connector = (
        ConnectorBuilder()
        .add_postgres("main", "postgresql://localhost/myapp")
        .with_cache(".cgc/cache.db")
        .build()
    )
    
    async with connector:
        # Discover schema
        schema = await connector.discover("main")
        
        print(f"Tables: {len(schema.entities)}")
        for entity in schema.entities:
            print(f"  {entity.name}: {len(entity.fields)} columns, {entity.row_count} rows")
        
        # Get relationship graph
        graph = await connector.graph()
        print(f"\nRelationships: {len(graph.relationships)}")
        for rel in graph.relationships:
            print(f"  {rel.from_field} -> {rel.to_field}")

asyncio.run(main())
```

### 9.2 Multi-Source with Chunking

```python
import asyncio
from cgc import ConnectorBuilder
from cgc.core.chunk import FixedRowsStrategy, FixedTokensStrategy

async def main():
    connector = (
        ConnectorBuilder()
        .add_postgres("db", "postgresql://localhost/app")
        .add_filesystem("logs", "/var/log/app")
        .add_qdrant("vectors", "http://localhost:6333")
        .build()
    )
    
    async with connector:
        # Discover all
        schemas = await connector.discover_all()
        print(connector.summary())
        
        # Chunk database table
        db_chunks = await connector.chunk(
            "db", 
            "orders",
            FixedRowsStrategy(rows_per_chunk=1000)
        )
        print(f"\nOrders chunked into {len(db_chunks)} pieces")
        
        # Chunk log file
        log_chunks = await connector.chunk(
            "logs",
            "access.log",
            FixedTokensStrategy(tokens_per_chunk=50_000)
        )
        print(f"Logs chunked into {len(log_chunks)} pieces")
        
        # Each chunk is ready for LLM processing
        for chunk in db_chunks[:3]:
            print(f"  Chunk {chunk.index}: {chunk.metadata.estimated_tokens} tokens")

asyncio.run(main())
```

### 9.3 RLM-Style Integration

```python
# This is what an RLM agent would write in a Python REPL

from cgc import ConnectorBuilder
from cgc.core.chunk import FixedRowsStrategy
from cgc.core.query import SqlQuery

# Initialize connector (done once at REPL start)
cgc = (
    ConnectorBuilder()
    .add_postgres("db", "postgresql://localhost/app")
    .add_filesystem("docs", "./documents")
    .build()
)

# Agent probes schema
async def probe():
    schema = await cgc.discover("db")
    print(schema.to_compact())
    return schema

# Agent queries data
async def find_users(status):
    result = await cgc.sql("db", f"SELECT * FROM users WHERE status = '{status}'")
    return result.to_dicts()

# Agent chunks large table
async def process_orders():
    chunks = await cgc.chunk("db", "orders", FixedRowsStrategy(1000))
    
    results = []
    for chunk in chunks:
        # This is where the RLM would call llm_query()
        # result = llm_query(f"Analyze these orders: {chunk.to_json()}")
        # results.append(result)
        print(f"Processing chunk {chunk.index + 1}/{chunk.total_chunks}")
    
    return results

# Agent finds related data
async def find_user_data(user_id):
    from cgc.core.schema import FieldId
    
    field = FieldId("db", "users", "id")
    related = await cgc.find_related(field, user_id)
    
    for item in related:
        print(f"Found in {item['entity']}: {item['record']}")

# Run in REPL
import asyncio
asyncio.run(probe())
```

---

## 10. Build Order & Milestones

### Phase 1: Foundation (Week 1)

- [x] Project setup, pyproject.toml, CI
- [ ] Core types: Schema, Entity, Field, Relationship
- [ ] Query and QueryResult types
- [ ] Chunk and ChunkStrategy types
- [ ] Error types
- [ ] Base DataSource protocol

**Deliverable:** Types defined, empty implementations

### Phase 2: Filesystem Adapter (Week 2)

- [ ] Local filesystem adapter
- [ ] File type detection
- [ ] CSV schema discovery and chunking
- [ ] JSON/JSONL schema discovery and chunking
- [ ] Text file chunking (by tokens, by sections)
- [ ] Unit tests with fixtures

**Deliverable:** Can discover and chunk local files

### Phase 3: SQL Adapter (Week 3)

- [ ] SQLite implementation
- [ ] PostgreSQL implementation
- [ ] MySQL implementation
- [ ] Schema introspection
- [ ] Foreign key discovery
- [ ] Row-based chunking

**Deliverable:** Can discover and chunk SQL databases

### Phase 4: Relationship Discovery (Week 4)

- [ ] RelationshipGraph implementation
- [ ] NamingConventionRule
- [ ] CardinalityMatchRule
- [ ] ValueOverlapRule
- [ ] Cross-source inference
- [ ] Graph export (DOT format)

**Deliverable:** Automatic relationship graph

### Phase 5: Vector & Document Adapters (Week 5)

- [ ] Qdrant adapter
- [ ] MongoDB adapter
- [ ] Vector search integration
- [ ] Document schema inference

**Deliverable:** Full adapter coverage

### Phase 6: CLI & Polish (Week 6)

- [ ] Full CLI implementation
- [ ] Config file support
- [ ] SQLite cache layer
- [ ] Documentation
- [ ] Examples
- [ ] Publish to PyPI

**Deliverable:** v0.1.0 release

---

## 11. Testing Strategy

### Unit Tests

```python
# tests/test_adapters/test_filesystem.py

import pytest
from pathlib import Path
from cgc.adapters.filesystem import FilesystemAdapter
from cgc.core.chunk import FixedRowsStrategy

@pytest.fixture
def csv_file(tmp_path):
    csv_content = "id,name,email\n1,Alice,alice@example.com\n2,Bob,bob@example.com\n"
    path = tmp_path / "users.csv"
    path.write_text(csv_content)
    return tmp_path

@pytest.mark.asyncio
async def test_discover_csv(csv_file):
    adapter = FilesystemAdapter("test", str(csv_file))
    schema = await adapter.discover_schema()
    
    assert len(schema.entities) == 1
    entity = schema.entities[0]
    assert entity.name == "users.csv"
    assert len(entity.fields) == 3
    assert entity.fields[0].name == "id"

@pytest.mark.asyncio
async def test_chunk_csv(csv_file):
    adapter = FilesystemAdapter("test", str(csv_file))
    chunks = await adapter.chunk("users.csv", FixedRowsStrategy(1))
    
    assert len(chunks) == 2
    assert chunks[0].data[0]["name"] == "Alice"
    assert chunks[1].data[0]["name"] == "Bob"
```

### Integration Tests

```python
# tests/integration/test_sql.py

import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:15") as pg:
        yield pg.get_connection_url()

@pytest.mark.asyncio
async def test_postgres_discovery(postgres):
    from cgc.adapters.sql import SqlAdapter
    
    adapter = SqlAdapter("test", postgres)
    
    # Create test table
    await adapter.query(SqlQuery(
        sql="CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT)"
    ))
    
    schema = await adapter.discover_schema()
    assert any(e.name == "users" for e in schema.entities)
```

---

## Appendix: Open Questions

1. **Async vs Sync API**: Should we provide both? Current spec is async-first.

2. **Embedding integration**: For semantic chunking and vector search, should CGC include optional embedding support, or require external embedders?

3. **Config file format**: TOML vs YAML vs JSON?

4. **Plugin system**: Should custom adapters be loadable as plugins?

---

*End of Python specification.*
