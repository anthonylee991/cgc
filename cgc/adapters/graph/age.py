"""PostgreSQL Apache AGE adapter for triplet storage."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text

from cgc.adapters.graph.base import GraphSink, GraphStats, StorageResult
from cgc.core.triplet import Triplet


class AgeAdapter(GraphSink):
    """PostgreSQL Apache AGE graph adapter.

    Apache AGE (A Graph Extension) adds graph database functionality
    to PostgreSQL, allowing Cypher queries on relational data.

    Stores triplets as:
    - Subject/Object -> Vertex with label 'Entity' (or specific label)
    - Predicate -> Edge between vertices

    Example:
        adapter = AgeAdapter(
            sink_id="mygraph",
            connection="postgresql://user:pass@localhost:5432/mydb",
            graph_name="knowledge_graph"
        )
        await adapter.store_triplets(triplets)
    """

    def __init__(
        self,
        sink_id: str,
        connection: str,
        graph_name: str = "cgc_graph",
    ):
        """Initialize AGE adapter.

        Args:
            sink_id: Unique identifier for this sink
            connection: PostgreSQL connection string
            graph_name: Name of the graph to use/create
        """
        self._sink_id = sink_id
        self._connection = connection
        self._graph_name = graph_name
        self._engine = None
        self._graph_initialized = False

    @property
    def sink_id(self) -> str:
        return self._sink_id

    @property
    def sink_type(self) -> str:
        return "age"

    async def _get_engine(self):
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            try:
                from sqlalchemy.ext.asyncio import create_async_engine
            except ImportError:
                raise ImportError(
                    "sqlalchemy[asyncio] required for AGE adapter. "
                    "Install with: pip install sqlalchemy[asyncio] asyncpg"
                )

            # Convert to async connection string
            conn = self._connection
            if conn.startswith("postgresql://"):
                conn = conn.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif not conn.startswith("postgresql+asyncpg://"):
                conn = f"postgresql+asyncpg://{conn}"

            self._engine = create_async_engine(conn)
        return self._engine

    async def connect(self) -> None:
        """Initialize the database engine."""
        await self._get_engine()

    async def _ensure_graph(self, conn) -> None:
        """Ensure AGE extension is loaded and graph exists.

        Note: LOAD 'age' must run on every connection, not just once per adapter.
        The search_path also needs to be set per-connection.
        """
        # Load AGE extension - must happen on every connection
        await conn.execute(text("LOAD 'age';"))
        await conn.execute(text("SET search_path = ag_catalog, \"$user\", public;"))

        # Create graph if it doesn't exist (only need to check once)
        if not self._graph_initialized:
            result = await conn.execute(
                text(f"SELECT * FROM ag_catalog.ag_graph WHERE name = '{self._graph_name}'")
            )
            if not result.fetchone():
                await conn.execute(text(f"SELECT create_graph('{self._graph_name}');"))
            self._graph_initialized = True

    async def store_triplets(
        self,
        triplets: list[Triplet],
        graph_name: str | None = None,
        merge: bool = True,
    ) -> StorageResult:
        """Store triplets in AGE graph.

        Uses Cypher MERGE for deduplication or CREATE for new entries.
        """
        start = time.time()
        result = StorageResult()

        if not triplets:
            return result

        gname = graph_name or self._graph_name
        engine = await self._get_engine()

        async with engine.connect() as conn:
            await self._ensure_graph(conn)

            for triplet in triplets:
                try:
                    # Sanitize predicate for edge label
                    edge_label = self._sanitize_label(triplet.predicate)
                    subject_label = triplet.subject_label or "Entity"
                    object_label = triplet.object_label or "Entity"

                    # Escape single quotes in strings
                    subject = triplet.subject.replace("'", "''")
                    obj = triplet.object.replace("'", "''")
                    predicate = triplet.predicate.replace("'", "''")
                    source_text = (triplet.source_text or "").replace("'", "''")

                    if merge:
                        # Use MERGE to avoid duplicates
                        cypher = f"""
                        SELECT * FROM cypher('{gname}', $$
                            MERGE (s:{subject_label} {{name: '{subject}'}})
                            MERGE (o:{object_label} {{name: '{obj}'}})
                            MERGE (s)-[r:{edge_label} {{
                                predicate: '{predicate}',
                                confidence: {triplet.confidence},
                                source_text: '{source_text}'
                            }}]->(o)
                            RETURN s, r, o
                        $$) as (s agtype, r agtype, o agtype);
                        """
                        result.nodes_merged += 2
                        result.relationships_merged += 1
                    else:
                        # Use CREATE for new entries
                        cypher = f"""
                        SELECT * FROM cypher('{gname}', $$
                            CREATE (s:{subject_label} {{name: '{subject}'}})
                            CREATE (o:{object_label} {{name: '{obj}'}})
                            CREATE (s)-[r:{edge_label} {{
                                predicate: '{predicate}',
                                confidence: {triplet.confidence},
                                source_text: '{source_text}'
                            }}]->(o)
                            RETURN s, r, o
                        $$) as (s agtype, r agtype, o agtype);
                        """
                        result.nodes_created += 2
                        result.relationships_created += 1

                    await conn.execute(text(cypher))

                except Exception as e:
                    result.errors.append(f"Error storing triplet {triplet}: {e}")

            await conn.commit()

        result.execution_time_ms = (time.time() - start) * 1000
        return result

    def _sanitize_label(self, label: str) -> str:
        """Convert string to valid AGE label.

        AGE labels should be alphanumeric with underscores, starting with letter.
        """
        sanitized = label.replace(" ", "_").replace("-", "_")
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "_")
        if sanitized and not sanitized[0].isalpha():
            sanitized = "rel_" + sanitized
        return sanitized or "related_to"

    async def get_stats(self, graph_name: str | None = None) -> GraphStats:
        """Get graph statistics."""
        gname = graph_name or self._graph_name
        engine = await self._get_engine()

        async with engine.connect() as conn:
            await self._ensure_graph(conn)

            # Count vertices
            node_result = await conn.execute(text(f"""
                SELECT * FROM cypher('{gname}', $$
                    MATCH (n) RETURN count(n) as cnt
                $$) as (cnt agtype);
            """))
            node_row = node_result.fetchone()
            node_count = int(str(node_row[0])) if node_row else 0

            # Count edges
            edge_result = await conn.execute(text(f"""
                SELECT * FROM cypher('{gname}', $$
                    MATCH ()-[r]->() RETURN count(r) as cnt
                $$) as (cnt agtype);
            """))
            edge_row = edge_result.fetchone()
            edge_count = int(str(edge_row[0])) if edge_row else 0

        return GraphStats(
            node_count=node_count,
            edge_count=edge_count,
            node_labels=["Entity"],  # AGE doesn't have easy label introspection
            relationship_types=[],
        )

    async def query_graph(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
        graph_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute Cypher query via AGE.

        Note: AGE uses a different parameter syntax. This method wraps
        the query in the cypher() function call.
        """
        gname = graph_name or self._graph_name
        engine = await self._get_engine()

        # Substitute parameters into query (AGE doesn't support $params directly)
        query = cypher
        if params:
            for key, value in params.items():
                if isinstance(value, str):
                    value = f"'{value.replace(chr(39), chr(39)+chr(39))}'"
                query = query.replace(f"${key}", str(value))

        async with engine.connect() as conn:
            await self._ensure_graph(conn)

            # Wrap in cypher() function
            # We need to determine return columns - use generic approach
            sql = f"""
                SELECT * FROM cypher('{gname}', $${query}$$) as result(data agtype);
            """

            try:
                result = await conn.execute(text(sql))
                rows = result.fetchall()
                return [{"data": str(row[0])} for row in rows]
            except Exception as e:
                # If column mismatch, try without specifying columns
                return [{"error": str(e)}]

    async def find_by_entity(
        self,
        entity: str,
        graph_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find all triplets involving an entity."""
        gname = graph_name or self._graph_name
        engine = await self._get_engine()
        entity_escaped = entity.replace("'", "''")

        async with engine.connect() as conn:
            await self._ensure_graph(conn)

            sql = f"""
                SELECT * FROM cypher('{gname}', $$
                    MATCH (s)-[r]->(o)
                    WHERE s.name = '{entity_escaped}' OR o.name = '{entity_escaped}'
                    RETURN s.name, type(r), o.name, r.confidence
                    LIMIT {limit}
                $$) as (subject agtype, predicate agtype, object agtype, confidence agtype);
            """

            result = await conn.execute(text(sql))
            rows = result.fetchall()

            return [
                {
                    "subject": str(row[0]).strip('"'),
                    "predicate": str(row[1]).strip('"'),
                    "object": str(row[2]).strip('"'),
                    "confidence": float(str(row[3])) if row[3] else 1.0,
                }
                for row in rows
            ]

    async def health_check(self) -> bool:
        """Check PostgreSQL/AGE connectivity."""
        try:
            engine = await self._get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1;"))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None


def age(
    sink_id: str,
    connection: str,
    graph_name: str = "cgc_graph",
) -> AgeAdapter:
    """Create an Apache AGE adapter (convenience function)."""
    return AgeAdapter(sink_id, connection, graph_name)
