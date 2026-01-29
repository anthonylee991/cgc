"""PostgreSQL + pgvector adapter for vector similarity search."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from cgc.adapters.base import DiscoveryOptions, FirstN, HealthStatus, SampleStrategy
from cgc.adapters.vector.base import VectorSource
from cgc.adapters.sql import to_async_url
from cgc.core.chunk import Chunk, ChunkMetadata, ChunkStrategy, FixedRowsStrategy
from cgc.core.query import Query, QueryResult, SemanticQuery, SqlQuery
from cgc.core.schema import (
    DataType,
    Entity,
    EntityType,
    Field,
    Schema,
    SchemaStats,
    SourceType,
)


class PgVectorAdapter(VectorSource):
    """PostgreSQL with pgvector extension for vector similarity search.

    Benefits:
    - Vectors live alongside structured data
    - ACID transactions include vectors
    - Use existing PostgreSQL tooling and infrastructure
    - Supports multiple distance metrics: L2, inner product, cosine
    """

    def __init__(
        self,
        source_id: str,
        connection_string: str,
        default_vector_column: str = "embedding",
        schema_name: str | None = None,
    ):
        """Initialize pgvector adapter.

        Args:
            source_id: Unique identifier for this source
            connection_string: PostgreSQL connection URL
            default_vector_column: Default column name for vectors
            schema_name: Optional schema name
        """
        self._source_id = source_id
        self._connection_string = connection_string
        self._default_vector_col = default_vector_column
        self._schema_name = schema_name
        self._engine: AsyncEngine | None = None

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
        return SourceType.PGVECTOR

    async def discover_schema(
        self,
        options: DiscoveryOptions | None = None,
    ) -> Schema:
        """Discover tables with vector columns."""
        options = options or DiscoveryOptions()
        engine = await self._get_engine()

        entities = []

        async with engine.connect() as conn:
            # Find all tables with vector columns
            sql = """
                SELECT
                    c.table_name,
                    c.column_name,
                    c.udt_name,
                    c.is_nullable
                FROM information_schema.columns c
                WHERE c.udt_name = 'vector'
            """
            if self._schema_name:
                sql += f" AND c.table_schema = '{self._schema_name}'"

            result = await conn.execute(text(sql))
            vector_columns = result.fetchall()

            # Group by table
            tables_with_vectors: dict[str, list[str]] = {}
            for row in vector_columns:
                table_name = row[0]
                col_name = row[1]
                tables_with_vectors.setdefault(table_name, []).append(col_name)

            # Get schema for each table
            for table_name, vector_cols in tables_with_vectors.items():
                if options.entities and table_name not in options.entities:
                    continue

                entity = await self._discover_entity(conn, table_name, vector_cols, options)
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
            summary=f"pgvector database with {len(entities)} vector-enabled tables",
            stats=stats,
        )

    async def _discover_entity(
        self,
        conn,
        table_name: str,
        vector_columns: list[str],
        options: DiscoveryOptions,
    ) -> Entity:
        """Discover a single table with vectors."""
        # Get all columns
        sql = f"""
            SELECT column_name, udt_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
        """
        if self._schema_name:
            sql += f" AND table_schema = '{self._schema_name}'"

        result = await conn.execute(text(sql))
        columns = result.fetchall()

        fields = []
        for col in columns:
            col_name, udt_name, nullable = col
            if col_name in vector_columns:
                dtype = DataType.VECTOR
            elif udt_name in ("int4", "int8", "serial", "bigserial"):
                dtype = DataType.INTEGER
            elif udt_name in ("float4", "float8", "numeric"):
                dtype = DataType.FLOAT
            elif udt_name == "bool":
                dtype = DataType.BOOLEAN
            elif udt_name in ("json", "jsonb"):
                dtype = DataType.JSON
            elif udt_name in ("timestamp", "timestamptz"):
                dtype = DataType.TIMESTAMP
            else:
                dtype = DataType.STRING

            fields.append(Field(
                name=col_name,
                data_type=dtype,
                nullable=nullable == "YES",
                original_type=udt_name,
            ))

        # Get row count
        row_count = None
        try:
            result = await conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            row_count = result.scalar()
        except Exception:
            pass

        return Entity(
            name=table_name,
            entity_type=EntityType.TABLE,
            fields=fields,
            row_count=row_count,
            metadata={"vector_columns": vector_columns},
        )

    async def query(self, query: Query) -> QueryResult:
        """Execute a query."""
        engine = await self._get_engine()
        start = time.time()

        if isinstance(query, SemanticQuery):
            return await self.vector_search(
                collection=query.collection or "",
                query_vector=query.query_vector,
                top_k=query.top_k,
                threshold=query.threshold,
                filter=query.filter,
            )

        elif isinstance(query, SqlQuery):
            async with engine.connect() as conn:
                result = await conn.execute(text(query.sql), query.params)
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

        else:
            raise ValueError(f"Unsupported query type: {type(query)}")

    async def vector_search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        threshold: float | None = None,
        filter: dict[str, Any] | None = None,
        vector_column: str | None = None,
        distance_metric: str = "cosine",
    ) -> QueryResult:
        """Similarity search using pgvector.

        Args:
            collection: Table name
            query_vector: Query embedding
            top_k: Max results
            threshold: Min similarity (optional)
            filter: WHERE clause conditions (optional)
            vector_column: Column containing vectors (default: self._default_vector_col)
            distance_metric: "cosine", "l2", or "inner_product"
        """
        engine = await self._get_engine()
        start = time.time()

        vec_col = vector_column or self._default_vector_col

        # Distance operators: <-> L2, <#> inner product, <=> cosine
        distance_ops = {
            "l2": "<->",
            "inner_product": "<#>",
            "cosine": "<=>",
        }
        op = distance_ops.get(distance_metric, "<=>")

        # Build vector string
        vec_str = f"[{','.join(map(str, query_vector))}]"

        # Build SQL
        where_clauses = []
        if threshold is not None:
            # For cosine, lower is better (0 = identical)
            where_clauses.append(f'"{vec_col}" {op} \'{vec_str}\' < {1 - threshold}')

        if filter:
            for key, value in filter.items():
                if isinstance(value, str):
                    where_clauses.append(f'"{key}" = \'{value}\'')
                else:
                    where_clauses.append(f'"{key}" = {value}')

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f'''
            SELECT *, ("{vec_col}" {op} '{vec_str}') as _distance
            FROM "{collection}"
            {where_sql}
            ORDER BY "{vec_col}" {op} '{vec_str}'
            LIMIT {top_k}
        '''

        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
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

    async def get_vector_dimensions(self, collection: str) -> int:
        """Get vector dimensionality for a table."""
        engine = await self._get_engine()

        async with engine.connect() as conn:
            # Get dimension from first row
            sql = f'''
                SELECT vector_dims("{self._default_vector_col}")
                FROM "{collection}"
                LIMIT 1
            '''
            result = await conn.execute(text(sql))
            dim = result.scalar()
            return dim or 0

    async def upsert_vectors(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert or update vectors."""
        engine = await self._get_engine()

        async with engine.begin() as conn:
            for i, (id_, vector) in enumerate(zip(ids, vectors)):
                vec_str = f"[{','.join(map(str, vector))}]"
                payload = payloads[i] if payloads else {}

                # Build column list and values
                columns = ["id", self._default_vector_col]
                values = [f"'{id_}'", f"'{vec_str}'"]

                for key, value in payload.items():
                    columns.append(f'"{key}"')
                    if isinstance(value, str):
                        values.append(f"'{value}'")
                    else:
                        values.append(str(value))

                sql = f'''
                    INSERT INTO "{collection}" ({', '.join(columns)})
                    VALUES ({', '.join(values)})
                    ON CONFLICT (id) DO UPDATE SET
                        "{self._default_vector_col}" = EXCLUDED."{self._default_vector_col}"
                '''
                await conn.execute(text(sql))

        return len(ids)

    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk vector table data."""
        if not isinstance(strategy, FixedRowsStrategy):
            raise ValueError(f"Unsupported chunk strategy: {type(strategy)}")

        engine = await self._get_engine()
        chunks = []

        async with engine.connect() as conn:
            # Get total count
            result = await conn.execute(text(f'SELECT COUNT(*) FROM "{entity}"'))
            total_rows = result.scalar()
            total_chunks = (total_rows + strategy.rows_per_chunk - 1) // strategy.rows_per_chunk

            for i in range(total_chunks):
                offset = i * strategy.rows_per_chunk
                # Exclude vector column from chunk data (too large)
                sql = f'''
                    SELECT * FROM "{entity}"
                    LIMIT {strategy.rows_per_chunk} OFFSET {offset}
                '''
                result = await conn.execute(text(sql))
                rows = result.fetchall()
                columns = list(result.keys())

                # Convert to dicts, excluding vector column
                data = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    # Remove vector column if present
                    row_dict.pop(self._default_vector_col, None)
                    data.append(row_dict)

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
        """Sample data from a table."""
        n = strategy.n if isinstance(strategy, FirstN) else 5
        engine = await self._get_engine()

        async with engine.connect() as conn:
            result = await conn.execute(text(f'SELECT * FROM "{entity}" LIMIT {n}'))
            rows = result.fetchall()
            columns = list(result.keys())

            # Exclude vector column from samples
            data = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                row_dict.pop(self._default_vector_col, None)
                data.append(row_dict)

            return data

    async def health_check(self) -> HealthStatus:
        """Check database connectivity and pgvector extension."""
        start = time.time()
        try:
            engine = await self._get_engine()
            async with engine.connect() as conn:
                # Check connection
                await conn.execute(text("SELECT 1"))

                # Check pgvector extension
                result = await conn.execute(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                )
                has_pgvector = result.scalar() is not None

            elapsed = (time.time() - start) * 1000

            if has_pgvector:
                return HealthStatus(healthy=True, latency_ms=elapsed)
            else:
                return HealthStatus(
                    healthy=False,
                    latency_ms=elapsed,
                    message="pgvector extension not installed",
                )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=False, latency_ms=elapsed, message=str(e))

    async def close(self) -> None:
        """Close the connection pool."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None


def pgvector(source_id: str, connection_string: str, **kwargs) -> PgVectorAdapter:
    """Create a pgvector adapter (convenience function)."""
    return PgVectorAdapter(source_id, connection_string, **kwargs)
