"""Main Connector class - the primary interface for Context Graph Connector."""

from __future__ import annotations

import asyncio
from typing import Any

from cgc.adapters.base import DataSource, DiscoveryOptions, FirstN, HealthStatus
from cgc.adapters.graph.base import GraphSink, StorageResult
from cgc.core.chunk import Chunk, ChunkStrategy
from cgc.core.errors import SourceNotFoundError
from cgc.core.graph import RelationshipGraph
from cgc.core.query import Query, QueryResult, SqlQuery, SemanticQuery
from cgc.core.schema import FieldId, Schema
from cgc.core.triplet import Triplet
from cgc.discovery.engine import RelationshipDiscoveryEngine


class SinkNotFoundError(Exception):
    """Raised when a graph sink is not found."""

    def __init__(self, sink_id: str):
        self.sink_id = sink_id
        super().__init__(f"Graph sink not found: {sink_id}")
# NOTE: extract_triplets is imported lazily in the method to avoid loading torch/spacy at startup


class Connector:
    """Main interface for Context Graph Connector.

    The Connector manages multiple data sources and provides a unified
    interface for:
    - Schema discovery
    - Querying
    - Chunking
    - Relationship graph construction
    - Cross-source operations

    Example:
        ```python
        async with Connector() as cgc:
            cgc.add_source(SqlAdapter("db", "postgresql://localhost/app"))
            cgc.add_source(FilesystemAdapter("docs", "./documents"))

            # Discover schemas
            await cgc.discover_all()

            # Query data
            result = await cgc.sql("db", "SELECT * FROM users LIMIT 10")

            # Get relationship graph
            graph = await cgc.graph()
        ```
    """

    def __init__(self, cache_path: str | None = None):
        """Initialize Connector.

        Args:
            cache_path: Optional path for SQLite cache (not yet implemented)
        """
        self._sources: dict[str, DataSource] = {}
        self._sinks: dict[str, GraphSink] = {}
        self._schemas: dict[str, Schema] = {}
        self._graph: RelationshipGraph | None = None
        self._discovery_engine = RelationshipDiscoveryEngine()
        self._cache_path = cache_path

    # === Source Management ===

    def add_source(self, source: DataSource) -> "Connector":
        """Add a data source.

        Args:
            source: DataSource instance to add

        Returns:
            Self for chaining
        """
        self._sources[source.source_id] = source
        # Invalidate graph cache
        self._graph = None
        return self

    def remove_source(self, source_id: str) -> bool:
        """Remove a data source.

        Args:
            source_id: ID of source to remove

        Returns:
            True if source was removed, False if not found
        """
        if source_id in self._sources:
            del self._sources[source_id]
            self._schemas.pop(source_id, None)
            self._graph = None
            return True
        return False

    @property
    def sources(self) -> list[str]:
        """List connected source IDs."""
        return list(self._sources.keys())

    def get_source(self, source_id: str) -> DataSource:
        """Get a specific source by ID.

        Args:
            source_id: Source identifier

        Returns:
            DataSource instance

        Raises:
            SourceNotFoundError: If source not found
        """
        if source_id not in self._sources:
            raise SourceNotFoundError(source_id)
        return self._sources[source_id]

    def has_source(self, source_id: str) -> bool:
        """Check if a source exists."""
        return source_id in self._sources

    # === Graph Sink Management ===

    def add_sink(self, sink: GraphSink) -> "Connector":
        """Add a graph sink for triplet storage.

        Args:
            sink: GraphSink instance to add

        Returns:
            Self for chaining
        """
        self._sinks[sink.sink_id] = sink
        return self

    def remove_sink(self, sink_id: str) -> bool:
        """Remove a graph sink.

        Args:
            sink_id: ID of sink to remove

        Returns:
            True if sink was removed, False if not found
        """
        if sink_id in self._sinks:
            del self._sinks[sink_id]
            return True
        return False

    @property
    def sinks(self) -> list[str]:
        """List connected sink IDs."""
        return list(self._sinks.keys())

    def get_sink(self, sink_id: str) -> GraphSink:
        """Get a specific sink by ID.

        Args:
            sink_id: Sink identifier

        Returns:
            GraphSink instance

        Raises:
            SinkNotFoundError: If sink not found
        """
        if sink_id not in self._sinks:
            raise SinkNotFoundError(sink_id)
        return self._sinks[sink_id]

    def has_sink(self, sink_id: str) -> bool:
        """Check if a sink exists."""
        return sink_id in self._sinks

    # === Schema Discovery ===

    async def discover(
        self,
        source_id: str,
        options: DiscoveryOptions | None = None,
        refresh: bool = False,
    ) -> Schema:
        """Discover schema for a source.

        Args:
            source_id: Source identifier
            options: Discovery options
            refresh: Force refresh even if cached

        Returns:
            Discovered schema

        Raises:
            asyncio.TimeoutError: If discovery exceeds timeout_seconds
        """
        # Check cache
        if not refresh and source_id in self._schemas:
            return self._schemas[source_id]

        options = options or DiscoveryOptions()

        # Discover with timeout enforcement
        source = self.get_source(source_id)
        timeout = options.timeout_seconds
        if timeout:
            schema = await asyncio.wait_for(
                source.discover_schema(options),
                timeout=float(timeout),
            )
        else:
            schema = await source.discover_schema(options)

        # Cache
        self._schemas[source_id] = schema

        return schema

    async def discover_all(
        self,
        options: DiscoveryOptions | None = None,
        refresh: bool = False,
    ) -> dict[str, Schema]:
        """Discover schemas for all sources.

        Args:
            options: Discovery options (applied to all sources)
            refresh: Force refresh

        Returns:
            Dict mapping source_id to Schema
        """
        tasks = [
            self.discover(source_id, options, refresh)
            for source_id in self._sources
        ]
        schemas = await asyncio.gather(*tasks)
        return dict(zip(self._sources.keys(), schemas))

    async def schema(self, source_id: str) -> Schema:
        """Get schema for a source (discover if needed).

        Convenience method that ensures schema is available.
        """
        return await self.discover(source_id)

    # === Relationship Graph ===

    async def graph(self, refresh: bool = False) -> RelationshipGraph:
        """Get relationship graph across all sources.

        Args:
            refresh: Force re-discovery

        Returns:
            RelationshipGraph with all discovered relationships
        """
        if not refresh and self._graph:
            return self._graph

        # Discover all schemas first
        schemas = await self.discover_all()

        # Run discovery engine
        self._graph = self._discovery_engine.discover(list(schemas.values()))

        return self._graph

    # === Querying ===

    async def query(self, source_id: str, query: Query) -> QueryResult:
        """Execute a query against a source.

        Args:
            source_id: Source identifier
            query: Query object

        Returns:
            QueryResult
        """
        source = self.get_source(source_id)
        return await source.query(query)

    async def sql(self, source_id: str, sql: str, **params) -> QueryResult:
        """Execute a SQL query (convenience method).

        Args:
            source_id: Source identifier
            sql: SQL query string
            **params: Query parameters

        Returns:
            QueryResult
        """
        return await self.query(source_id, SqlQuery(sql=sql, params=params))

    async def vector_search(
        self,
        source_id: str,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        threshold: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a vector similarity search.

        Args:
            source_id: Source identifier (must be a VectorSource)
            collection: Collection/table to search
            query_vector: Query embedding vector
            top_k: Maximum results
            threshold: Minimum similarity score
            filter: Metadata filter

        Returns:
            QueryResult with similarity scores
        """
        return await self.query(
            source_id,
            SemanticQuery(
                collection=collection,
                query_vector=query_vector,
                top_k=top_k,
                threshold=threshold,
                filter=filter,
            ),
        )

    # === Chunking ===

    async def chunk(
        self,
        source_id: str,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk data from a source.

        Args:
            source_id: Source identifier
            entity: Entity (table, file) to chunk
            strategy: Chunking strategy

        Returns:
            List of chunks ready for LLM processing
        """
        source = self.get_source(source_id)
        return await source.chunk(entity, strategy)

    # === Sampling ===

    async def sample(
        self,
        source_id: str,
        entity: str,
        n: int = 5,
    ) -> list[dict[str, Any]]:
        """Sample data from a source.

        Args:
            source_id: Source identifier
            entity: Entity to sample from
            n: Number of samples

        Returns:
            List of sample records
        """
        source = self.get_source(source_id)
        return await source.sample(entity, FirstN(n))

    # === Cross-Source Operations ===

    async def find_related(
        self,
        field_id: FieldId,
        value: Any,
    ) -> list[dict[str, Any]]:
        """Find related records across sources.

        Given a field and value, find all related records via
        the relationship graph.

        Args:
            field_id: Starting field
            value: Value to search for

        Returns:
            List of related records with source info
        """
        graph = await self.graph()
        related = graph.related_to(field_id)

        results = []
        for rel in related:
            other_field = rel.other_side(field_id)
            if not other_field:
                continue

            # Query the related source
            from cgc.core.query import GetQuery

            try:
                source = self.get_source(other_field.source_id)
                result = await source.query(
                    GetQuery(
                        entity=other_field.entity,
                        key=other_field.field,
                        value=value,
                    )
                )

                for row in result.to_dicts():
                    results.append({
                        "source_id": other_field.source_id,
                        "entity": other_field.entity,
                        "relationship": rel.relationship_type.value,
                        "confidence": rel.confidence.value,
                        "record": row,
                    })
            except Exception:
                continue

        return results

    # === Triplet Extraction ===

    def extract_triplets(
        self,
        text: str,
        use_gliner: bool = True,
        domain: str | None = None,
    ) -> list[Triplet]:
        """Extract triplets from text.

        Uses hybrid extraction (patterns + GliNER + GliREL) to find
        subject-predicate-object relationships with domain-specific
        entity and relation labels.

        Args:
            text: Input text
            use_gliner: Whether to use GliNER (higher recall, slower)
            domain: Force a specific industry pack (e.g., "tech_startup",
                    "ecommerce_retail"). None for auto-detection.

        Returns:
            List of extracted triplets
        """
        # Lazy import to avoid loading torch/spacy at startup
        from cgc.discovery.extractor import extract_triplets
        return extract_triplets(text, use_gliner=use_gliner, domain=domain)

    def extract_triplets_structured(
        self,
        data: list[dict[str, Any]],
    ) -> list[Triplet]:
        """Extract triplets from structured data using hub-and-spoke model.

        Classifies columns into types (primary entity, entity, property, etc.)
        and builds relationships between the hub entity and categorical values.

        Args:
            data: List of row dicts (e.g., from CSV or JSON)

        Returns:
            List of extracted triplets
        """
        from cgc.discovery.structured import StructuredExtractor
        extractor = StructuredExtractor()
        return extractor.extract_triplets(data)

    def extract_file(
        self,
        path: str,
        domain: str | None = None,
        use_gliner: bool = True,
    ) -> tuple[list[Triplet], str]:
        """Extract triplets from a file, auto-detecting structured vs unstructured.

        Uses the file parser registry to parse the file, then routes to
        structured extraction (hub-and-spoke) if rows are available, or
        unstructured extraction (patterns + GliNER) otherwise.

        Args:
            path: Path to the file
            domain: Force a specific industry pack (for unstructured only)
            use_gliner: Whether to use GliNER for unstructured extraction

        Returns:
            Tuple of (triplets, file_type) where file_type is "structured" or "unstructured"
        """
        from pathlib import Path as _Path
        from cgc.adapters.parsers import parse_file

        file_path = _Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        content = file_path.read_bytes()
        parsed = parse_file(content, file_path.name)

        if parsed.rows:
            triplets = self.extract_triplets_structured(parsed.rows)
            return triplets, "structured"
        else:
            triplets = self.extract_triplets(parsed.text, use_gliner=use_gliner, domain=domain)
            return triplets, "unstructured"

    async def extract_chunked(
        self,
        source_id: str,
        entity: str,
        strategy: ChunkStrategy,
        use_gliner: bool = True,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Chunk a file then extract triplets from each chunk.

        Designed for unstructured data (PDFs, docs, large text files) where
        chunking is needed before extraction.

        Args:
            source_id: Source containing the file
            entity: File entity name
            strategy: Chunking strategy to use
            use_gliner: Whether to use GliNER for extraction
            domain: Force a specific industry pack

        Returns:
            Dict with per-chunk triplets and aggregate counts
        """
        chunks = await self.chunk(source_id, entity, strategy)

        results = []
        total_triplets = 0

        for chunk in chunks:
            text = chunk.to_text()
            triplets = self.extract_triplets(text, use_gliner=use_gliner, domain=domain)
            results.append({
                "chunk_index": chunk.index,
                "chunk_id": chunk.id,
                "triplets": triplets,
                "triplet_count": len(triplets),
            })
            total_triplets += len(triplets)

        return {
            "chunks": results,
            "total_chunks": len(chunks),
            "total_triplets": total_triplets,
        }

    # === Remote Extraction (via cloud relay) ===

    def extract_remote(
        self,
        text: str,
        use_gliner: bool = True,
        domain: str | None = None,
        store: Any = None,
    ) -> list[Triplet]:
        """Extract triplets via the cloud relay API.

        Args:
            text: Input text
            use_gliner: Whether to use GliNER
            domain: Force a specific industry pack
            store: LicenseStore instance for retrieving the license key

        Returns:
            List of extracted triplets
        """
        import httpx
        from cgc.licensing.validator import RELAY_URL, get_license_key

        license_key = get_license_key(store) if store else None
        if not license_key:
            raise RuntimeError("No license key found. Run 'cgc activate <key>' first.")

        resp = httpx.post(
            f"{RELAY_URL}/v1/extract/text",
            headers={"X-License-Key": license_key},
            json={"text": text, "use_gliner": use_gliner, "domain": domain},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()

        return [
            Triplet(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"],
                confidence=t.get("confidence", 0.0),
                metadata=t.get("metadata"),
            )
            for t in data.get("triplets", [])
        ]

    def extract_file_remote(
        self,
        path: str,
        domain: str | None = None,
        use_gliner: bool = True,
        store: Any = None,
    ) -> tuple[list[Triplet], str]:
        """Extract triplets from a file via the cloud relay API.

        Args:
            path: Path to the file
            domain: Force a specific industry pack
            use_gliner: Whether to use GliNER for unstructured extraction
            store: LicenseStore instance for retrieving the license key

        Returns:
            Tuple of (triplets, file_type)
        """
        import httpx
        from pathlib import Path as _Path
        from cgc.licensing.validator import RELAY_URL, get_license_key

        file_path = _Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        license_key = get_license_key(store) if store else None
        if not license_key:
            raise RuntimeError("No license key found. Run 'cgc activate <key>' first.")

        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            data = {}
            if domain:
                data["domain"] = domain
            data["use_gliner"] = str(use_gliner).lower()

            resp = httpx.post(
                f"{RELAY_URL}/v1/extract/file",
                headers={"X-License-Key": license_key},
                files=files,
                data=data,
                timeout=120.0,
            )
        resp.raise_for_status()
        result = resp.json()

        triplets = [
            Triplet(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"],
                confidence=t.get("confidence", 0.0),
                metadata=t.get("metadata"),
            )
            for t in result.get("triplets", [])
        ]

        return triplets, result.get("file_type", "unstructured")

    def detect_domain(self, text: str) -> dict[str, Any]:
        """Detect the industry domain of text for optimized extraction.

        Routes text to the best-matching industry pack using E5 embeddings.

        Args:
            text: Input text to classify

        Returns:
            Dict with pack_id, pack_name, confidence, and all scores
        """
        from cgc.discovery.router import create_router
        router = create_router()
        result = router.route(text)
        return {
            "pack_id": result.pack.id,
            "pack_name": result.pack.name,
            "confidence": result.confidence,
            "entity_labels": result.pack.entity_labels,
            "relation_labels": result.pack.relation_labels,
            "scores": result.scores,
        }

    # === Triplet Storage (Graph Sinks) ===

    async def store_triplets(
        self,
        sink_id: str,
        triplets: list[Triplet],
        graph_name: str | None = None,
        merge: bool = True,
    ) -> StorageResult:
        """Store triplets in a graph sink.

        Args:
            sink_id: ID of the graph sink to use
            triplets: List of triplets to store
            graph_name: Optional graph name (for AGE, etc.)
            merge: If True, merge with existing nodes/edges

        Returns:
            StorageResult with counts and any errors
        """
        sink = self.get_sink(sink_id)
        return await sink.store_triplets(triplets, graph_name, merge)

    async def extract_and_store(
        self,
        sink_id: str,
        text: str,
        use_gliner: bool = True,
        domain: str | None = None,
        graph_name: str | None = None,
        merge: bool = True,
        use_remote: bool = False,
        store: Any = None,
    ) -> dict[str, Any]:
        """Extract triplets from text and store in a graph sink.

        Combines extraction and storage in one operation.

        Args:
            sink_id: ID of the graph sink to use
            text: Text to extract from
            use_gliner: Whether to use GliNER for extraction
            domain: Force a specific industry pack
            graph_name: Optional graph name (for AGE)
            merge: If True, merge with existing nodes/edges
            use_remote: If True, use cloud relay for extraction
            store: LicenseStore instance for remote extraction

        Returns:
            Dict with triplets and storage result
        """
        # Extract triplets
        if use_remote:
            triplets = self.extract_remote(text, use_gliner, domain, store)
        else:
            triplets = self.extract_triplets(text, use_gliner, domain)

        # Store triplets
        result = await self.store_triplets(sink_id, triplets, graph_name, merge)

        return {
            "triplets": [t.to_dict() for t in triplets],
            "triplet_count": len(triplets),
            "storage_result": {
                "nodes_created": result.nodes_created,
                "nodes_merged": result.nodes_merged,
                "relationships_created": result.relationships_created,
                "relationships_merged": result.relationships_merged,
                "execution_time_ms": result.execution_time_ms,
                "success": result.success,
                "errors": result.errors,
            },
        }

    async def extract_file_and_store(
        self,
        sink_id: str,
        path: str,
        domain: str | None = None,
        use_gliner: bool = True,
        graph_name: str | None = None,
        merge: bool = True,
        use_remote: bool = False,
        store: Any = None,
    ) -> dict[str, Any]:
        """Extract triplets from a file and store in a graph sink.

        Args:
            sink_id: ID of the graph sink to use
            path: Path to file
            domain: Force a specific industry pack
            use_gliner: Whether to use GliNER
            graph_name: Optional graph name (for AGE)
            merge: If True, merge with existing nodes/edges
            use_remote: If True, use cloud relay for extraction
            store: LicenseStore instance for remote extraction

        Returns:
            Dict with triplets, file type, and storage result
        """
        # Extract triplets
        if use_remote:
            triplets, file_type = self.extract_file_remote(path, domain, use_gliner, store)
        else:
            triplets, file_type = self.extract_file(path, domain, use_gliner)

        # Store triplets
        result = await self.store_triplets(sink_id, triplets, graph_name, merge)

        return {
            "triplets": [t.to_dict() for t in triplets],
            "triplet_count": len(triplets),
            "file_type": file_type,
            "storage_result": {
                "nodes_created": result.nodes_created,
                "nodes_merged": result.nodes_merged,
                "relationships_created": result.relationships_created,
                "relationships_merged": result.relationships_merged,
                "execution_time_ms": result.execution_time_ms,
                "success": result.success,
                "errors": result.errors,
            },
        }

    async def query_graph_sink(
        self,
        sink_id: str,
        cypher: str,
        params: dict[str, Any] | None = None,
        graph_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query against a graph sink.

        Args:
            sink_id: ID of the graph sink
            cypher: Cypher query string
            params: Query parameters
            graph_name: Optional graph name (for AGE)

        Returns:
            List of result dictionaries
        """
        sink = self.get_sink(sink_id)
        return await sink.query_graph(cypher, params, graph_name)

    async def find_entity_in_sink(
        self,
        sink_id: str,
        entity: str,
        graph_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find all triplets involving an entity in a graph sink.

        Args:
            sink_id: ID of the graph sink
            entity: Entity name to search for
            graph_name: Optional graph name (for AGE)
            limit: Maximum results

        Returns:
            List of triplet dictionaries
        """
        sink = self.get_sink(sink_id)
        return await sink.find_by_entity(entity, graph_name, limit)

    # === Health Checks ===

    async def health_check(self) -> dict[str, HealthStatus]:
        """Check health of all sources.

        Returns:
            Dict mapping source_id to HealthStatus
        """
        tasks = [source.health_check() for source in self._sources.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        health = {}
        for source_id, result in zip(self._sources.keys(), results):
            if isinstance(result, Exception):
                health[source_id] = HealthStatus(
                    healthy=False,
                    message=str(result),
                )
            else:
                health[source_id] = result

        return health

    async def health_check_source(self, source_id: str) -> HealthStatus:
        """Check health of a specific source."""
        source = self.get_source(source_id)
        return await source.health_check()

    # === Utilities ===

    def summary(self) -> str:
        """Generate compact summary for LLM context.

        Returns summary of all connected sources and their schemas.
        """
        lines = [f"Connected sources: {len(self._sources)}"]

        for source_id, schema in self._schemas.items():
            lines.append(f"\n{schema.to_compact()}")

        if self._graph:
            lines.append(f"\nRelationships: {len(self._graph.relationships)}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert connector state to dictionary."""
        return {
            "sources": list(self._sources.keys()),
            "schemas": {
                sid: schema.to_dict() for sid, schema in self._schemas.items()
            },
            "relationships": (
                self._graph.to_dict() if self._graph else {"relationships": [], "total": 0}
            ),
        }

    async def close(self) -> None:
        """Close all connections."""
        for source in self._sources.values():
            await source.close()
        for sink in self._sinks.values():
            await sink.close()

    async def __aenter__(self) -> "Connector":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


class ConnectorBuilder:
    """Builder for creating Connector instances.

    Provides a fluent interface for adding sources and graph sinks.

    Example:
        ```python
        connector = (
            ConnectorBuilder()
            .add_postgres("db", "postgresql://localhost/app")
            .add_filesystem("docs", "./documents")
            .add_qdrant("vectors", "http://localhost:6333")
            .add_neo4j("graph", "bolt://localhost:7687", "neo4j", "password")
            .build()
        )
        ```
    """

    def __init__(self):
        self._sources: list[DataSource] = []
        self._sinks: list[GraphSink] = []
        self._cache_path: str | None = None

    def add_source(self, source: DataSource) -> "ConnectorBuilder":
        """Add a generic data source."""
        self._sources.append(source)
        return self

    def add_postgres(
        self,
        source_id: str,
        connection_string: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a PostgreSQL source."""
        from cgc.adapters.sql import SqlAdapter

        self._sources.append(SqlAdapter(source_id, connection_string, **kwargs))
        return self

    def add_mysql(
        self,
        source_id: str,
        connection_string: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a MySQL source."""
        from cgc.adapters.sql import SqlAdapter

        self._sources.append(SqlAdapter(source_id, connection_string, **kwargs))
        return self

    def add_sqlite(
        self,
        source_id: str,
        path: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a SQLite source."""
        from cgc.adapters.sql import SqlAdapter

        self._sources.append(SqlAdapter(source_id, f"sqlite:///{path}", **kwargs))
        return self

    def add_filesystem(
        self,
        source_id: str,
        path: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a local filesystem source."""
        from cgc.adapters.filesystem import FilesystemAdapter

        self._sources.append(FilesystemAdapter(source_id, path, **kwargs))
        return self

    def add_pgvector(
        self,
        source_id: str,
        connection_string: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a pgvector source."""
        from cgc.adapters.vector.pgvector import PgVectorAdapter

        self._sources.append(PgVectorAdapter(source_id, connection_string, **kwargs))
        return self

    def add_qdrant(
        self,
        source_id: str,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a Qdrant source."""
        from cgc.adapters.vector.qdrant import QdrantAdapter

        self._sources.append(QdrantAdapter(source_id, url, api_key, **kwargs))
        return self

    def add_pinecone(
        self,
        source_id: str,
        api_key: str,
        index_name: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a Pinecone source."""
        from cgc.adapters.vector.pinecone import PineconeAdapter

        self._sources.append(PineconeAdapter(source_id, api_key, index_name, **kwargs))
        return self

    def add_mongodb_vector(
        self,
        source_id: str,
        connection_string: str,
        database: str,
        **kwargs,
    ) -> "ConnectorBuilder":
        """Add a MongoDB Atlas Vector Search source."""
        from cgc.adapters.vector.mongodb import MongoVectorAdapter

        self._sources.append(
            MongoVectorAdapter(source_id, connection_string, database, **kwargs)
        )
        return self

    def with_cache(self, path: str) -> "ConnectorBuilder":
        """Set cache path for schema caching."""
        self._cache_path = path
        return self

    # === Graph Sinks ===

    def add_sink(self, sink: GraphSink) -> "ConnectorBuilder":
        """Add a generic graph sink."""
        self._sinks.append(sink)
        return self

    def add_neo4j(
        self,
        sink_id: str,
        uri: str,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> "ConnectorBuilder":
        """Add a Neo4j graph sink.

        Args:
            sink_id: Unique identifier for this sink
            uri: Neo4j connection URI (bolt://host:port)
            user: Username for authentication
            password: Password for authentication
            database: Database name (default: neo4j)
        """
        from cgc.adapters.graph.neo4j import Neo4jAdapter

        self._sinks.append(Neo4jAdapter(sink_id, uri, user, password, database))
        return self

    def add_age(
        self,
        sink_id: str,
        connection: str,
        graph_name: str = "cgc_graph",
    ) -> "ConnectorBuilder":
        """Add a PostgreSQL Apache AGE graph sink.

        Args:
            sink_id: Unique identifier for this sink
            connection: PostgreSQL connection string
            graph_name: Name of the graph to use/create
        """
        from cgc.adapters.graph.age import AgeAdapter

        self._sinks.append(AgeAdapter(sink_id, connection, graph_name))
        return self

    def build(self) -> Connector:
        """Build the Connector instance."""
        connector = Connector(cache_path=self._cache_path)
        for source in self._sources:
            connector.add_source(source)
        for sink in self._sinks:
            connector.add_sink(sink)
        return connector
