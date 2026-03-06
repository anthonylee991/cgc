"""SQL adapter for relational databases (PostgreSQL, MySQL, SQLite)."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cgc.adapters.base import (
    DataSource,
    DiscoveryOptions,
    FirstN,
    HealthStatus,
    RandomSample,
    SampleStrategy,
)
from cgc.core.chunk import (
    Chunk,
    ChunkMetadata,
    ChunkStrategy,
    FixedRowsStrategy,
)
from cgc.core.errors import QueryError
from cgc.core.graph import (
    Confidence,
    InferenceMethod,
    Relationship,
    RelationshipType,
)
from cgc.core.query import (
    GetQuery,
    Query,
    QueryResult,
    SearchQuery,
    SqlQuery,
)
from cgc.core.schema import (
    Cardinality,
    DataType,
    Entity,
    EntityType,
    Field,
    FieldId,
    Schema,
    SchemaStats,
    SourceType,
)

# Map SQLAlchemy types to our DataType enum
TYPE_MAP = {
    "INTEGER": DataType.INTEGER,
    "BIGINT": DataType.INTEGER,
    "SMALLINT": DataType.INTEGER,
    "SERIAL": DataType.INTEGER,
    "BIGSERIAL": DataType.INTEGER,
    "FLOAT": DataType.FLOAT,
    "REAL": DataType.FLOAT,
    "DOUBLE": DataType.FLOAT,
    "DOUBLE PRECISION": DataType.FLOAT,
    "NUMERIC": DataType.DECIMAL,
    "DECIMAL": DataType.DECIMAL,
    "BOOLEAN": DataType.BOOLEAN,
    "BOOL": DataType.BOOLEAN,
    "VARCHAR": DataType.STRING,
    "CHAR": DataType.STRING,
    "CHARACTER VARYING": DataType.STRING,
    "TEXT": DataType.TEXT,
    "DATE": DataType.DATE,
    "TIME": DataType.TIME,
    "DATETIME": DataType.DATETIME,
    "TIMESTAMP": DataType.TIMESTAMP,
    "TIMESTAMP WITHOUT TIME ZONE": DataType.TIMESTAMP,
    "TIMESTAMP WITH TIME ZONE": DataType.TIMESTAMP,
    "BLOB": DataType.BYTES,
    "BYTEA": DataType.BYTES,
    "JSON": DataType.JSON,
    "JSONB": DataType.JSON,
    "ARRAY": DataType.ARRAY,
    "UUID": DataType.STRING,
    "VECTOR": DataType.VECTOR,
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

    new_scheme = driver_map.get(scheme)
    if new_scheme is None:
        return connection_string

    return connection_string.replace(parsed.scheme, new_scheme, 1)


class SqlAdapter(DataSource):
    """Adapter for SQL databases (PostgreSQL, MySQL, SQLite).

    Features:
    - Schema discovery via introspection
    - Foreign key relationship detection
    - ILIKE search with trigram fallback (PostgreSQL)
    - Intelligent chunking by rows
    """

    def __init__(
        self,
        source_id: str,
        connection_string: str,
        schema_name: str | None = None,
    ):
        """Initialize SQL adapter.

        Args:
            source_id: Unique identifier for this source
            connection_string: Database connection URL
            schema_name: Optional schema name (default: public for Postgres)
        """
        self._source_id = source_id
        self._connection_string = connection_string
        self._source_type = detect_dialect(connection_string)
        self._schema_name = schema_name
        self._engine: AsyncEngine | None = None
        self._trigram_available: bool | None = None

    async def _get_engine(self) -> AsyncEngine:
        """Get or create async engine."""
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

    async def _check_trigram_extension(self, conn) -> bool:
        """Check if pg_trgm extension is available (PostgreSQL only)."""
        if self._trigram_available is not None:
            return self._trigram_available

        if self._source_type != SourceType.POSTGRES:
            self._trigram_available = False
            return False

        try:
            result = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
            )
            self._trigram_available = result.scalar() is not None
        except Exception:
            self._trigram_available = False

        return self._trigram_available

    async def discover_schema(
        self,
        options: DiscoveryOptions | None = None,
    ) -> Schema:
        """Discover database schema."""
        options = options or DiscoveryOptions()
        engine = await self._get_engine()

        entities = []
        relationships = []

        async with engine.connect() as conn:
            # Use run_sync for SQLAlchemy inspection (it's not async-native)
            def sync_inspect(sync_conn):
                inspector = inspect(sync_conn)
                return {
                    "tables": inspector.get_table_names(schema=self._schema_name),
                    "views": inspector.get_view_names(schema=self._schema_name),
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

        def sync_get_columns(sync_conn):
            inspector = inspect(sync_conn)
            columns = inspector.get_columns(name, schema=self._schema_name)
            pk_constraint = inspector.get_pk_constraint(name, schema=self._schema_name)
            pk_columns = pk_constraint.get("constrained_columns", []) if pk_constraint else []
            fk_constraints = inspector.get_foreign_keys(name, schema=self._schema_name)

            return columns, pk_columns, fk_constraints

        columns, pk_columns, fk_constraints = await conn.run_sync(sync_get_columns)

        # Build FK lookup
        fk_lookup = {}
        for fk in fk_constraints:
            for local_col, remote_col in zip(
                fk["constrained_columns"],
                fk["referred_columns"],
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
            type_str = str(col["type"]).upper().split("(")[0].strip()
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
            # Use quoted identifier for safety
            result = await conn.execute(text(f'SELECT COUNT(*) FROM "{name}"'))
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
        n: int,
    ) -> list[dict[str, Any]]:
        """Get sample rows from an entity."""
        try:
            result = await conn.execute(text(f'SELECT * FROM "{name}" LIMIT {n}'))
            rows = result.fetchall()
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in rows]
        except Exception:
            return []

    async def _get_cardinality(
        self,
        conn,
        table: str,
        column: str,
    ) -> Cardinality | None:
        """Get cardinality statistics for a column."""
        try:
            query = text(f'''
                SELECT
                    COUNT(DISTINCT "{column}") as unique_count,
                    SUM(CASE WHEN "{column}" IS NULL THEN 1 ELSE 0 END) as null_count,
                    COUNT(*) as total_count
                FROM "{table}"
            ''')
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
        n: int = 5,
    ) -> list[Any]:
        """Get sample distinct values for a column."""
        try:
            query = text(f'''
                SELECT DISTINCT "{column}"
                FROM "{table}"
                WHERE "{column}" IS NOT NULL
                LIMIT {n}
            ''')
            result = await conn.execute(query)
            return [row[0] for row in result.fetchall()]
        except Exception:
            return []

    async def _discover_relationships(
        self,
        conn,
        entities: list[Entity],
    ) -> list[Relationship]:
        """Discover relationships from foreign keys."""
        relationships = []

        for entity in entities:
            for field in entity.fields:
                if field.is_foreign_key and field.foreign_key_ref:
                    rel = Relationship(
                        id=f"{self._source_id}:{entity.name}.{field.name}->{field.foreign_key_ref}",
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
        relationships: list[Relationship],
    ) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Database ({self._source_type.value}) with {len(entities)} tables/views "
            f"and {len(relationships)} relationships.",
            "",
            "Tables:",
        ]
        for e in entities[:10]:
            lines.append(
                f"  - {e.name} ({e.row_count or '?'} rows, {len(e.fields)} columns)"
            )
        if len(entities) > 10:
            lines.append(f"  ... and {len(entities) - 10} more")

        return "\n".join(lines)

    async def query(self, query: Query) -> QueryResult:
        """Execute a query."""
        engine = await self._get_engine()
        start = time.time()

        async with engine.connect() as conn:
            if isinstance(query, SqlQuery):
                return await self._execute_sql(conn, query, start)

            elif isinstance(query, GetQuery):
                return await self._execute_get(conn, query, start)

            elif isinstance(query, SearchQuery):
                return await self._execute_search(conn, query, start)

            else:
                raise ValueError(f"Unsupported query type: {type(query)}")

    async def _execute_sql(
        self,
        conn,
        query: SqlQuery,
        start: float,
    ) -> QueryResult:
        """Execute raw SQL query."""
        try:
            result = await conn.execute(text(query.sql), query.params)
            rows = result.fetchall()
            columns = list(result.keys())
        except Exception as e:
            raise QueryError(self._source_id, query.sql, str(e))

        elapsed = (time.time() - start) * 1000

        return QueryResult(
            columns=columns,
            rows=[list(row) for row in rows],
            total_count=len(rows),
            truncated=False,
            execution_time_ms=elapsed,
            source_id=self._source_id,
        )

    async def _execute_get(
        self,
        conn,
        query: GetQuery,
        start: float,
    ) -> QueryResult:
        """Execute key-value lookup."""
        sql = f'SELECT * FROM "{query.entity}" WHERE "{query.key}" = :value'
        result = await conn.execute(text(sql), {"value": query.value})
        rows = result.fetchall()
        columns = list(result.keys())

        elapsed = (time.time() - start) * 1000

        return QueryResult(
            columns=columns,
            rows=[list(row) for row in rows],
            total_count=len(rows),
            execution_time_ms=elapsed,
            source_id=self._source_id,
        )

    async def _execute_search(
        self,
        conn,
        query: SearchQuery,
        start: float,
    ) -> QueryResult:
        """Execute text search with ILIKE and optional trigram fallback."""
        # First try: ILIKE
        ilike_sql = f'''
            SELECT * FROM "{query.entity}"
            WHERE "{query.field}" ILIKE :pattern
            LIMIT 100
        '''
        result = await conn.execute(
            text(ilike_sql),
            {"pattern": f"%{query.query}%"},
        )
        rows = result.fetchall()
        columns = list(result.keys())

        # If no results and fuzzy fallback enabled, try trigram
        if not rows and query.fuzzy_fallback:
            has_trigram = await self._check_trigram_extension(conn)

            if has_trigram:
                trgm_sql = f'''
                    SELECT *, similarity("{query.field}", :query) as _similarity
                    FROM "{query.entity}"
                    WHERE similarity("{query.field}", :query) > :threshold
                    ORDER BY _similarity DESC
                    LIMIT 100
                '''
                result = await conn.execute(
                    text(trgm_sql),
                    {
                        "query": query.query,
                        "threshold": query.similarity_threshold,
                    },
                )
                rows = result.fetchall()
                columns = list(result.keys())

        elapsed = (time.time() - start) * 1000

        return QueryResult(
            columns=columns,
            rows=[list(row) for row in rows],
            total_count=len(rows),
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
        rows_per_chunk: int,
    ) -> list[Chunk]:
        """Chunk by fixed row count."""
        chunks = []

        async with engine.connect() as conn:
            # Get total count
            result = await conn.execute(text(f'SELECT COUNT(*) FROM "{entity}"'))
            total_rows = result.scalar()
            total_chunks = (total_rows + rows_per_chunk - 1) // rows_per_chunk

            for i in range(total_chunks):
                offset = i * rows_per_chunk
                sql = f'SELECT * FROM "{entity}" LIMIT {rows_per_chunk} OFFSET {offset}'
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
                if self._source_type == SourceType.POSTGRES:
                    sql = f'SELECT * FROM "{entity}" ORDER BY RANDOM() LIMIT {strategy.n}'
                elif self._source_type == SourceType.MYSQL:
                    sql = f'SELECT * FROM `{entity}` ORDER BY RAND() LIMIT {strategy.n}'
                else:
                    sql = f'SELECT * FROM "{entity}" ORDER BY RANDOM() LIMIT {strategy.n}'

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
def postgres(source_id: str, connection_string: str, **kwargs) -> SqlAdapter:
    """Create a PostgreSQL adapter."""
    return SqlAdapter(source_id, connection_string, **kwargs)


def mysql(source_id: str, connection_string: str, **kwargs) -> SqlAdapter:
    """Create a MySQL adapter."""
    return SqlAdapter(source_id, connection_string, **kwargs)


def sqlite(source_id: str, path: str, **kwargs) -> SqlAdapter:
    """Create a SQLite adapter."""
    connection_string = f"sqlite:///{path}"
    return SqlAdapter(source_id, connection_string, **kwargs)
