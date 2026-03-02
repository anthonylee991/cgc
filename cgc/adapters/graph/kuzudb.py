"""KuzuDB embedded graph database adapter for triplet storage."""

from __future__ import annotations

import time
from typing import Any

from cgc.adapters.graph.base import GraphSink, GraphStats, StorageResult
from cgc.core.triplet import Triplet


class KuzudbAdapter(GraphSink):
    """KuzuDB embedded graph database adapter.

    KuzuDB is an embedded graph database (like SQLite for graphs) that
    requires no server — just a local directory. Uses a generic schema
    with a single Entity node table and Relationship rel table.

    Stores triplets as:
    - Subject/Object -> Entity node with name + entity_type properties
    - Predicate -> Relationship edge with predicate + confidence properties

    Example:
        adapter = KuzudbAdapter(
            sink_id="mygraph",
            path="./my_graph_db"
        )
        await adapter.store_triplets(triplets)
    """

    def __init__(self, sink_id: str, path: str):
        """Initialize KuzuDB adapter.

        Args:
            sink_id: Unique identifier for this sink
            path: Directory path for the KuzuDB database
        """
        self._sink_id = sink_id
        self._path = path
        self._db = None
        self._conn = None
        self._schema_initialized = False

    @property
    def sink_id(self) -> str:
        return self._sink_id

    @property
    def sink_type(self) -> str:
        return "kuzudb"

    def _get_connection(self):
        """Get or create KuzuDB database and connection."""
        if self._conn is None:
            try:
                import kuzu
            except ImportError:
                raise ImportError(
                    "kuzu package required for KuzuDB adapter. "
                    "Install with: pip install kuzu"
                )

            self._db = kuzu.Database(self._path)
            self._conn = kuzu.Connection(self._db)
        return self._conn

    def _ensure_schema(self, conn) -> None:
        """Create the generic schema if it doesn't exist."""
        if self._schema_initialized:
            return

        # Create Entity node table
        try:
            conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Entity("
                "name STRING, "
                "entity_type STRING, "
                "metadata STRING, "
                "PRIMARY KEY(name))"
            )
        except Exception:
            pass  # Table may already exist in older kuzu versions without IF NOT EXISTS

        # Create Relationship rel table
        try:
            conn.execute(
                "CREATE REL TABLE IF NOT EXISTS Relationship("
                "FROM Entity TO Entity, "
                "predicate STRING, "
                "confidence DOUBLE, "
                "source STRING)"
            )
        except Exception:
            pass  # Table may already exist

        self._schema_initialized = True

    async def store_triplets(
        self,
        triplets: list[Triplet],
        graph_name: str | None = None,
        merge: bool = True,
    ) -> StorageResult:
        """Store triplets in KuzuDB.

        Creates Entity nodes for subjects and objects, and Relationship
        edges for predicates. Uses MERGE by default to avoid duplicates.
        """
        start = time.time()
        result = StorageResult()

        if not triplets:
            return result

        conn = self._get_connection()
        self._ensure_schema(conn)

        for triplet in triplets:
            try:
                # MERGE subject node
                conn.execute(
                    "MERGE (s:Entity {name: $name}) "
                    "SET s.entity_type = $entity_type",
                    parameters={
                        "name": triplet.subject,
                        "entity_type": triplet.subject_label or "Entity",
                    },
                )

                # MERGE object node
                conn.execute(
                    "MERGE (o:Entity {name: $name}) "
                    "SET o.entity_type = $entity_type",
                    parameters={
                        "name": triplet.object,
                        "entity_type": triplet.object_label or "Entity",
                    },
                )

                # CREATE relationship (KuzuDB doesn't support MERGE on rels)
                conn.execute(
                    "MATCH (s:Entity {name: $subject}), (o:Entity {name: $object}) "
                    "CREATE (s)-[:Relationship {"
                    "predicate: $predicate, "
                    "confidence: $confidence, "
                    "source: $source"
                    "}]->(o)",
                    parameters={
                        "subject": triplet.subject,
                        "object": triplet.object,
                        "predicate": triplet.predicate,
                        "confidence": triplet.confidence,
                        "source": triplet.source_text or "",
                    },
                )

                if merge:
                    result.nodes_merged += 2
                    result.relationships_created += 1
                else:
                    result.nodes_created += 2
                    result.relationships_created += 1

            except Exception as e:
                result.errors.append(f"Error storing triplet {triplet}: {e}")

        result.execution_time_ms = (time.time() - start) * 1000
        return result

    async def get_stats(self, graph_name: str | None = None) -> GraphStats:
        """Get graph statistics."""
        conn = self._get_connection()
        self._ensure_schema(conn)

        # Count nodes
        node_result = conn.execute("MATCH (n:Entity) RETURN count(n) AS cnt")
        node_count = 0
        while node_result.has_next():
            node_count = node_result.get_next()[0]

        # Count relationships
        edge_result = conn.execute(
            "MATCH ()-[r:Relationship]->() RETURN count(r) AS cnt"
        )
        edge_count = 0
        while edge_result.has_next():
            edge_count = edge_result.get_next()[0]

        return GraphStats(
            node_count=node_count,
            edge_count=edge_count,
            node_labels=["Entity"],
            relationship_types=["Relationship"],
        )

    async def query_graph(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
        graph_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query."""
        conn = self._get_connection()
        self._ensure_schema(conn)

        result = conn.execute(cypher, parameters=params or {})
        columns = result.get_column_names()
        rows = []
        while result.has_next():
            row = result.get_next()
            rows.append(dict(zip(columns, row)))
        return rows

    async def find_by_entity(
        self,
        entity: str,
        graph_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find all triplets involving an entity."""
        conn = self._get_connection()
        self._ensure_schema(conn)

        result = conn.execute(
            "MATCH (s:Entity)-[r:Relationship]->(o:Entity) "
            "WHERE s.name = $entity OR o.name = $entity "
            "RETURN s.name AS subject, r.predicate AS predicate, "
            "o.name AS object, r.confidence AS confidence "
            "LIMIT $limit",
            parameters={"entity": entity, "limit": limit},
        )

        columns = result.get_column_names()
        rows = []
        while result.has_next():
            row = result.get_next()
            rows.append(dict(zip(columns, row)))
        return rows

    async def health_check(self) -> bool:
        """Check KuzuDB accessibility."""
        try:
            conn = self._get_connection()
            result = conn.execute("RETURN 1 AS ok")
            while result.has_next():
                result.get_next()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close KuzuDB connection and database."""
        self._conn = None
        self._db = None
        self._schema_initialized = False


def kuzudb(sink_id: str, path: str) -> KuzudbAdapter:
    """Create a KuzuDB adapter (convenience function).

    Args:
        sink_id: Unique identifier for this sink
        path: Directory path for the embedded database

    Returns:
        Configured KuzudbAdapter instance
    """
    return KuzudbAdapter(sink_id, path)
