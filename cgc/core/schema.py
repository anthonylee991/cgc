"""Schema types for representing data source structure."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class SourceType(Enum):
    """Type of data source."""

    # SQL databases
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SQLITE = "sqlite"

    # Vector databases
    PGVECTOR = "pgvector"
    QDRANT = "qdrant"
    PINECONE = "pinecone"

    # Document stores
    MONGODB = "mongodb"

    # File systems
    FILESYSTEM = "filesystem"
    S3 = "s3"
    GCS = "gcs"

    # APIs
    API = "api"


class EntityType(Enum):
    """Type of entity within a data source."""

    TABLE = "table"
    VIEW = "view"
    COLLECTION = "collection"
    FILE = "file"
    DIRECTORY = "directory"
    ENDPOINT = "endpoint"
    INDEX = "index"  # Vector index


class DataType(Enum):
    """Normalized data types across all sources."""

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


@dataclass(frozen=True)
class FieldId:
    """Unique identifier for a field across all sources."""

    source_id: str
    entity: str
    field: str

    def __hash__(self) -> int:
        return hash((self.source_id, self.entity, self.field))

    def __str__(self) -> str:
        return f"{self.source_id}.{self.entity}.{self.field}"


@dataclass
class Cardinality:
    """Statistics about a field's value distribution."""

    unique_count: int
    null_count: int
    total_count: int

    @property
    def uniqueness_ratio(self) -> float:
        """Ratio of unique values to total values."""
        if self.total_count == 0:
            return 0.0
        return self.unique_count / self.total_count

    @property
    def null_ratio(self) -> float:
        """Ratio of null values to total values."""
        if self.total_count == 0:
            return 0.0
        return self.null_count / self.total_count

    @property
    def is_likely_primary_key(self) -> bool:
        """Heuristic: likely a PK if all values are unique and non-null."""
        return self.uniqueness_ratio == 1.0 and self.null_count == 0


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
        """Create a FieldId for this field."""
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
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_field(self, name: str) -> Field | None:
        """Get a field by name."""
        return next((f for f in self.fields if f.name == name), None)

    @property
    def primary_keys(self) -> list[Field]:
        """Get all primary key fields."""
        return [f for f in self.fields if f.is_primary_key]

    @property
    def foreign_keys(self) -> list[Field]:
        """Get all foreign key fields."""
        return [f for f in self.fields if f.is_foreign_key]

    @property
    def field_names(self) -> list[str]:
        """Get list of field names."""
        return [f.name for f in self.fields]


@dataclass
class SchemaStats:
    """Summary statistics for a schema."""

    total_entities: int
    total_fields: int
    total_rows: int | None = None
    estimated_size_bytes: int | None = None


@dataclass
class Schema:
    """Complete schema for a data source."""

    source_id: str
    source_type: SourceType
    entities: list[Entity]
    relationships: list[Any] = field(default_factory=list)  # Relationship type defined in graph.py
    summary: str = ""
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    stats: SchemaStats | None = None

    def get_entity(self, name: str) -> Entity | None:
        """Get an entity by name."""
        return next((e for e in self.entities if e.name == name), None)

    @property
    def entity_names(self) -> list[str]:
        """Get list of entity names."""
        return [e.name for e in self.entities]

    # Above this threshold, to_compact() uses directory-tree summarization
    # instead of listing every entity individually
    COMPACT_ENTITY_THRESHOLD: int = 200

    def to_compact(self) -> str:
        """Generate compact summary for LLM context.

        For schemas with many entities (>200), produces a directory-tree
        summary with file counts per directory instead of listing every
        file individually. This prevents output token explosion.
        """
        lines = [f"Source: {self.source_id} ({self.source_type.value})"]

        if len(self.entities) <= self.COMPACT_ENTITY_THRESHOLD:
            # Small schema: list every entity
            for entity in self.entities:
                fields_str = ", ".join(f.name for f in entity.fields[:5])
                if len(entity.fields) > 5:
                    fields_str += f", ... (+{len(entity.fields) - 5} more)"
                rows = f" ({entity.row_count:,} rows)" if entity.row_count else ""
                lines.append(f"  {entity.name}{rows}: {fields_str}")
        else:
            # Large schema: summarize by directory tree
            lines.append(f"  ({len(self.entities):,} entities - showing directory summary)")
            lines.append("")
            dir_counts: dict[str, dict[str, int]] = {}
            extensions: dict[str, int] = {}

            for entity in self.entities:
                if entity.entity_type == EntityType.DIRECTORY:
                    continue
                parts = entity.name.replace("\\", "/").split("/")
                top_dir = parts[0] if len(parts) > 1 else "."
                ext = Path(entity.name).suffix.lower() or "(no ext)"

                if top_dir not in dir_counts:
                    dir_counts[top_dir] = {"files": 0, "dirs": 0}
                dir_counts[top_dir]["files"] += 1
                extensions[ext] = extensions.get(ext, 0) + 1

            for entity in self.entities:
                if entity.entity_type == EntityType.DIRECTORY:
                    parts = entity.name.replace("\\", "/").split("/")
                    top_dir = parts[0]
                    if top_dir in dir_counts:
                        dir_counts[top_dir]["dirs"] += 1

            # Sort by file count descending
            for dir_name, counts in sorted(
                dir_counts.items(), key=lambda x: x[1]["files"], reverse=True
            )[:30]:
                lines.append(
                    f"  {dir_name}/ ({counts['files']} files, {counts['dirs']} subdirs)"
                )

            if len(dir_counts) > 30:
                lines.append(f"  ... and {len(dir_counts) - 30} more directories")

            # Show extension breakdown
            lines.append("")
            lines.append("  File types:")
            for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:15]:
                lines.append(f"    {ext}: {count}")
            if len(extensions) > 15:
                lines.append(f"    ... and {len(extensions) - 15} more types")

        if self.stats:
            lines.append(f"\nTotal: {self.stats.total_entities} entities, {self.stats.total_fields} fields")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "entities": [
                {
                    "name": e.name,
                    "type": e.entity_type.value,
                    "fields": [
                        {
                            "name": f.name,
                            "type": f.data_type.value,
                            "nullable": f.nullable,
                            "is_pk": f.is_primary_key,
                            "is_fk": f.is_foreign_key,
                        }
                        for f in e.fields
                    ],
                    "row_count": e.row_count,
                }
                for e in self.entities
            ],
            "relationships": len(self.relationships),
            "discovered_at": self.discovered_at.isoformat(),
        }
