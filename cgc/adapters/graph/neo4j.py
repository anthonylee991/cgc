"""Neo4j graph database adapter for triplet storage."""

from __future__ import annotations

import time
from typing import Any

from cgc.adapters.graph.base import GraphSink, GraphStats, StorageResult
from cgc.core.triplet import Triplet


class Neo4jAdapter(GraphSink):
    """Neo4j graph database adapter.

    Stores triplets as:
    - Subject/Object -> Node with label :Entity (or specific label if provided)
    - Predicate -> Relationship between nodes

    Example:
        adapter = Neo4jAdapter(
            sink_id="mygraph",
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password"
        )
        await adapter.store_triplets(triplets)
    """

    def __init__(
        self,
        sink_id: str,
        uri: str,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ):
        """Initialize Neo4j adapter.

        Args:
            sink_id: Unique identifier for this sink
            uri: Neo4j connection URI (bolt://host:port)
            user: Username for authentication
            password: Password for authentication
            database: Database name (default: neo4j)
        """
        self._sink_id = sink_id
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database or "neo4j"
        self._driver = None

    @property
    def sink_id(self) -> str:
        return self._sink_id

    @property
    def sink_type(self) -> str:
        return "neo4j"

    def _get_driver(self):
        """Get or create Neo4j driver."""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError:
                raise ImportError(
                    "neo4j package required for Neo4j adapter. "
                    "Install with: pip install neo4j"
                )

            auth = (self._user, self._password) if self._user else None
            self._driver = GraphDatabase.driver(self._uri, auth=auth)
        return self._driver

    async def store_triplets(
        self,
        triplets: list[Triplet],
        graph_name: str | None = None,
        merge: bool = True,
    ) -> StorageResult:
        """Store triplets in Neo4j.

        Creates nodes for subjects and objects, and relationships for predicates.
        Uses MERGE by default to avoid duplicates.
        """
        start = time.time()
        result = StorageResult()

        if not triplets:
            return result

        driver = self._get_driver()

        # Build batch query for efficiency
        operation = "MERGE" if merge else "CREATE"

        with driver.session(database=self._database) as session:
            for triplet in triplets:
                try:
                    # Sanitize predicate for relationship type (Neo4j requires uppercase, no spaces)
                    rel_type = self._sanitize_rel_type(triplet.predicate)

                    # Build labels
                    subject_label = triplet.subject_label or "Entity"
                    object_label = triplet.object_label or "Entity"

                    # Cypher query with dynamic relationship type
                    query = f"""
                    {operation} (s:{subject_label} {{name: $subject}})
                    {operation} (o:{object_label} {{name: $object}})
                    {operation} (s)-[r:{rel_type} {{
                        predicate: $predicate,
                        confidence: $confidence,
                        source_text: $source_text
                    }}]->(o)
                    RETURN
                        CASE WHEN s.created IS NULL THEN 1 ELSE 0 END as s_new,
                        CASE WHEN o.created IS NULL THEN 1 ELSE 0 END as o_new,
                        CASE WHEN r.created IS NULL THEN 1 ELSE 0 END as r_new
                    """

                    params = {
                        "subject": triplet.subject,
                        "object": triplet.object,
                        "predicate": triplet.predicate,
                        "confidence": triplet.confidence,
                        "source_text": triplet.source_text or "",
                    }

                    res = session.run(query, params)
                    record = res.single()

                    if merge:
                        # For MERGE, count as merged (we can't easily tell if new)
                        result.nodes_merged += 2
                        result.relationships_merged += 1
                    else:
                        result.nodes_created += 2
                        result.relationships_created += 1

                except Exception as e:
                    result.errors.append(f"Error storing triplet {triplet}: {e}")

        result.execution_time_ms = (time.time() - start) * 1000
        return result

    def _sanitize_rel_type(self, predicate: str) -> str:
        """Convert predicate to valid Neo4j relationship type.

        Neo4j relationship types should be uppercase with underscores.
        """
        # Replace spaces and special chars with underscores
        sanitized = predicate.upper().replace(" ", "_").replace("-", "_")
        # Remove any remaining invalid characters
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "_")
        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "REL_" + sanitized
        return sanitized or "RELATED_TO"

    async def get_stats(self, graph_name: str | None = None) -> GraphStats:
        """Get graph statistics."""
        driver = self._get_driver()

        with driver.session(database=self._database) as session:
            # Count nodes
            node_result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = node_result.single()["count"]

            # Count relationships
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = rel_result.single()["count"]

            # Get labels
            label_result = session.run("CALL db.labels() YIELD label RETURN collect(label) as labels")
            labels = label_result.single()["labels"]

            # Get relationship types
            rel_type_result = session.run(
                "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types"
            )
            rel_types = rel_type_result.single()["types"]

        return GraphStats(
            node_count=node_count,
            edge_count=rel_count,
            node_labels=labels,
            relationship_types=rel_types,
        )

    async def query_graph(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
        graph_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute Cypher query."""
        driver = self._get_driver()

        with driver.session(database=self._database) as session:
            result = session.run(cypher, params or {})
            return [dict(record) for record in result]

    async def find_by_entity(
        self,
        entity: str,
        graph_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find all triplets involving an entity."""
        cypher = """
        MATCH (s)-[r]->(o)
        WHERE s.name = $entity OR o.name = $entity
        RETURN s.name as subject, type(r) as predicate, o.name as object,
               r.confidence as confidence
        LIMIT $limit
        """
        return await self.query_graph(cypher, {"entity": entity, "limit": limit})

    async def health_check(self) -> bool:
        """Check Neo4j connectivity."""
        try:
            driver = self._get_driver()
            with driver.session(database=self._database) as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None


def neo4j(
    sink_id: str,
    uri: str,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
) -> Neo4jAdapter:
    """Create a Neo4j adapter (convenience function)."""
    return Neo4jAdapter(sink_id, uri, user, password, database)
