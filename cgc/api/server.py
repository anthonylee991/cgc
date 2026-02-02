"""FastAPI server for Context Graph Connector.

Provides HTTP API for:
- Schema discovery
- Querying
- Chunking
- Relationship graph
- Triplet extraction

Run with: uvicorn cgc.api.server:app --reload
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cgc.connector import Connector
from cgc.core.chunk import FixedRowsStrategy, FixedTokensStrategy, BySectionsStrategy


# === Request/Response Models ===

class SourceConfig(BaseModel):
    """Configuration for adding a data source."""
    source_id: str
    source_type: str  # postgres, mysql, sqlite, filesystem, qdrant, pinecone, pgvector, mongodb
    connection: str  # connection string or path
    options: dict[str, Any] = Field(default_factory=dict)


class SqlQueryRequest(BaseModel):
    """SQL query request."""
    source_id: str
    sql: str
    params: dict[str, Any] = Field(default_factory=dict)


class SampleRequest(BaseModel):
    """Sample data request."""
    source_id: str
    entity: str
    n: int = 5


class ChunkRequest(BaseModel):
    """Chunk data request."""
    source_id: str
    entity: str
    strategy: str = "rows:1000"  # rows:N, tokens:N, sections


class SearchRequest(BaseModel):
    """Search request."""
    source_id: str
    query: str
    entity: str | None = None  # Optional for filesystem (searches all files)
    field: str | None = None   # Optional for filesystem (not applicable)
    fuzzy_fallback: bool = True


class VectorSearchRequest(BaseModel):
    """Vector similarity search request."""
    source_id: str
    collection: str
    query_vector: list[float]
    top_k: int = 10
    threshold: float | None = None
    filter: dict[str, Any] | None = None


class TripletRequest(BaseModel):
    """Triplet extraction request."""
    text: str
    use_gliner: bool = True
    domain: str | None = None  # Industry pack ID for domain-specific extraction


class StructuredExtractionRequest(BaseModel):
    """Structured data extraction request."""
    data: list[dict[str, Any]]


class ChunkedExtractionRequest(BaseModel):
    """Chunk-then-extract workflow request."""
    source_id: str
    entity: str
    strategy: str = "tokens:4000"
    use_gliner: bool = True
    domain: str | None = None


class DomainDetectionRequest(BaseModel):
    """Domain detection request."""
    text: str


class FindRelatedRequest(BaseModel):
    """Find related records request."""
    source_id: str
    entity: str
    field: str
    value: Any


# === Global Connector ===

_connector: Connector | None = None


def get_connector() -> Connector:
    """Get the global connector instance."""
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector


def _normalize_path(path: str) -> str:
    """Normalize file paths for cross-platform compatibility."""
    # Replace backslashes with forward slashes
    path = path.replace("\\", "/")
    # Remove any double slashes
    while "//" in path:
        path = path.replace("//", "/")
    return path


def _normalize_entity(source_id: str, entity: str) -> str:
    """Normalize entity name, stripping source_id prefix if present."""
    entity = entity.strip()
    # Strip source_id prefix if accidentally included (e.g., "my_docs/file.txt" -> "file.txt")
    if entity.startswith(source_id + "/"):
        entity = entity[len(source_id) + 1:]
    elif entity.startswith(source_id + "\\"):
        entity = entity[len(source_id) + 1:]
    # Normalize path separators
    entity = _normalize_path(entity)
    return entity


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage connector lifecycle."""
    yield
    # Cleanup on shutdown
    global _connector
    if _connector:
        await _connector.close()
        _connector = None


# === FastAPI App ===

app = FastAPI(
    title="Context Graph Connector API",
    description="Programmatic data access for LLM agents",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_app() -> FastAPI:
    """Create a new FastAPI app instance."""
    return app


# === Endpoints ===

@app.get("/")
async def root():
    """API root."""
    return {
        "name": "Context Graph Connector",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check."""
    connector = get_connector()
    if connector.sources:
        statuses = await connector.health_check()
        return {
            "status": "healthy",
            "sources": {
                sid: {"healthy": s.healthy, "latency_ms": s.latency_ms}
                for sid, s in statuses.items()
            },
        }
    return {"status": "healthy", "sources": {}}


# === Source Management ===

@app.get("/sources")
async def list_sources():
    """List connected sources."""
    connector = get_connector()
    return {"sources": connector.sources}


@app.post("/sources")
async def add_source(config: SourceConfig):
    """Add a data source."""
    connector = get_connector()

    # Normalize connection path for filesystem and sqlite sources
    connection = config.connection
    if config.source_type in ("filesystem", "sqlite"):
        connection = _normalize_path(connection)

    try:
        if config.source_type == "postgres":
            from cgc.adapters.sql import SqlAdapter
            connector.add_source(SqlAdapter(config.source_id, connection, **config.options))
        elif config.source_type == "mysql":
            from cgc.adapters.sql import SqlAdapter
            connector.add_source(SqlAdapter(config.source_id, connection, **config.options))
        elif config.source_type == "sqlite":
            from cgc.adapters.sql import SqlAdapter
            conn = connection if connection.startswith("sqlite") else f"sqlite:///{connection}"
            connector.add_source(SqlAdapter(config.source_id, conn, **config.options))
        elif config.source_type == "filesystem":
            from cgc.adapters.filesystem import FilesystemAdapter
            connector.add_source(FilesystemAdapter(config.source_id, connection, **config.options))
        elif config.source_type == "qdrant":
            from cgc.adapters.vector.qdrant import QdrantAdapter
            connector.add_source(QdrantAdapter(config.source_id, config.connection, **config.options))
        elif config.source_type == "pinecone":
            from cgc.adapters.vector.pinecone import PineconeAdapter
            api_key = config.options.pop("api_key", "")
            connector.add_source(PineconeAdapter(config.source_id, api_key, config.connection, **config.options))
        elif config.source_type == "pgvector":
            from cgc.adapters.vector.pgvector import PgVectorAdapter
            connector.add_source(PgVectorAdapter(config.source_id, config.connection, **config.options))
        elif config.source_type == "mongodb":
            from cgc.adapters.vector.mongodb import MongoVectorAdapter
            database = config.options.pop("database", "default")
            connector.add_source(MongoVectorAdapter(config.source_id, config.connection, database, **config.options))
        else:
            raise HTTPException(400, f"Unknown source type: {config.source_type}")

        return {"status": "added", "source_id": config.source_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/sources/{source_id}")
async def remove_source(source_id: str):
    """Remove a data source."""
    connector = get_connector()
    if connector.remove_source(source_id):
        return {"status": "removed", "source_id": source_id}
    raise HTTPException(404, f"Source not found: {source_id}")


# === Schema Discovery ===

@app.get("/sources/{source_id}/schema")
async def discover_schema(source_id: str, refresh: bool = False):
    """Discover schema for a source."""
    connector = get_connector()

    if not connector.has_source(source_id):
        raise HTTPException(404, f"Source not found: {source_id}")

    try:
        schema = await connector.discover(source_id, refresh=refresh)
        return schema.to_dict()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/sources/{source_id}/schema/{entity}")
async def get_entity_schema(source_id: str, entity: str):
    """Get schema for a specific entity."""
    connector = get_connector()

    if not connector.has_source(source_id):
        raise HTTPException(404, f"Source not found: {source_id}")

    try:
        schema = await connector.discover(source_id)
        entity_obj = schema.get_entity(entity)
        if not entity_obj:
            raise HTTPException(404, f"Entity not found: {entity}")
        return entity_obj.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/schemas")
async def discover_all_schemas(refresh: bool = False):
    """Discover schemas for all sources."""
    connector = get_connector()

    try:
        schemas = await connector.discover_all(refresh=refresh)
        return {sid: s.to_dict() for sid, s in schemas.items()}
    except Exception as e:
        raise HTTPException(500, str(e))


# === Querying ===

@app.post("/query/sql")
async def execute_sql(request: SqlQueryRequest):
    """Execute a SQL query."""
    connector = get_connector()

    if not connector.has_source(request.source_id):
        raise HTTPException(404, f"Source not found: {request.source_id}")

    try:
        result = await connector.sql(request.source_id, request.sql, **request.params)
        return {
            "rows": result.to_dicts(),
            "row_count": result.total_count,
            "columns": result.columns,
            "execution_time_ms": result.execution_time_ms,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/query/search")
async def execute_search(request: SearchRequest):
    """Execute a pattern search. For databases uses ILIKE, for filesystems uses grep-style search."""
    connector = get_connector()

    if not connector.has_source(request.source_id):
        raise HTTPException(404, f"Source not found: {request.source_id}")

    try:
        source = connector.get_source(request.source_id)
        source_type = type(source).__name__

        # Handle filesystem sources with PatternQuery
        if source_type == "FilesystemAdapter":
            from cgc.core.query import PatternQuery

            # If no entity specified, search across all files
            if not request.entity:
                from cgc.core.schema import EntityType

                # Get all files and search each one
                schema = await source.discover_schema()
                all_results = []
                total_time = 0

                # Filter to only file entities (not directories)
                file_entities = [e for e in schema.entities if e.entity_type == EntityType.FILE]

                for file_entity in file_entities:
                    try:
                        query = PatternQuery(
                            entity=file_entity.name,
                            pattern=request.query,
                            case_sensitive=False,
                            fuzzy_fallback=request.fuzzy_fallback,
                        )
                        result = await connector.query(request.source_id, query)
                        # Add filename to each result
                        has_similarity = len(result.columns) > 2 and "similarity" in result.columns
                        for row in result.rows:
                            row_dict = {
                                "file": file_entity.name,
                                "line_number": row[0],
                                "content": row[1],
                            }
                            if has_similarity:
                                row_dict["similarity"] = row[2]
                            all_results.append(row_dict)
                        total_time += result.execution_time_ms
                    except Exception:
                        # Skip files that can't be searched (binary, etc.)
                        continue

                # Sort by similarity if present
                if all_results and "similarity" in all_results[0]:
                    all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)

                return {
                    "rows": all_results,
                    "row_count": len(all_results),
                    "execution_time_ms": total_time,
                }
            else:
                # Search specific file
                entity = _normalize_entity(request.source_id, request.entity)
                query = PatternQuery(
                    entity=entity,
                    pattern=request.query,
                    case_sensitive=False,
                    fuzzy_fallback=request.fuzzy_fallback,
                )
                result = await connector.query(request.source_id, query)
                has_similarity = len(result.columns) > 2 and "similarity" in result.columns
                rows = []
                for r in result.rows:
                    row_dict = {"line_number": r[0], "content": r[1]}
                    if has_similarity:
                        row_dict["similarity"] = r[2]
                    rows.append(row_dict)
                return {
                    "rows": rows,
                    "row_count": result.total_count,
                    "execution_time_ms": result.execution_time_ms,
                }
        else:
            # Database sources use SearchQuery
            if not request.entity or not request.field:
                raise HTTPException(400, "entity and field are required for database searches")

            from cgc.core.query import SearchQuery
            query = SearchQuery(
                entity=request.entity,
                field=request.field,
                query=request.query,
                fuzzy_fallback=request.fuzzy_fallback,
            )
            result = await connector.query(request.source_id, query)
            return {
                "rows": result.to_dicts(),
                "row_count": result.total_count,
                "execution_time_ms": result.execution_time_ms,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/query/vector")
async def execute_vector_search(request: VectorSearchRequest):
    """Execute a vector similarity search."""
    connector = get_connector()

    if not connector.has_source(request.source_id):
        raise HTTPException(404, f"Source not found: {request.source_id}")

    try:
        result = await connector.vector_search(
            request.source_id,
            request.collection,
            request.query_vector,
            request.top_k,
            request.threshold,
            request.filter,
        )
        return {
            "rows": result.to_dicts(),
            "row_count": result.total_count,
            "execution_time_ms": result.execution_time_ms,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# === Sampling ===

@app.post("/sample")
async def sample_data(request: SampleRequest):
    """Sample data from an entity."""
    connector = get_connector()

    if not connector.has_source(request.source_id):
        raise HTTPException(404, f"Source not found: {request.source_id}")

    # Normalize entity name
    entity = _normalize_entity(request.source_id, request.entity)

    try:
        samples = await connector.sample(request.source_id, entity, request.n)
        return {"samples": samples, "count": len(samples)}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/sources/{source_id}/sample/{entity:path}")
async def sample_entity(source_id: str, entity: str, n: int = Query(default=5)):
    """Sample data from an entity (GET convenience endpoint)."""
    connector = get_connector()

    if not connector.has_source(source_id):
        raise HTTPException(404, f"Source not found: {source_id}")

    # Normalize entity name
    entity = _normalize_entity(source_id, entity)

    try:
        samples = await connector.sample(source_id, entity, n)
        return {"samples": samples, "count": len(samples)}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# === Chunking ===

@app.post("/chunk")
async def chunk_data(request: ChunkRequest):
    """Chunk data from an entity."""
    connector = get_connector()

    if not connector.has_source(request.source_id):
        raise HTTPException(404, f"Source not found: {request.source_id}")

    # Validate entity is provided
    if not request.entity or not request.entity.strip():
        raise HTTPException(400, "entity is required - please specify a filename to chunk")

    # Normalize entity name
    entity = _normalize_entity(request.source_id, request.entity)

    # Parse strategy
    if request.strategy.startswith("rows:"):
        n = int(request.strategy.split(":")[1])
        strategy = FixedRowsStrategy(rows_per_chunk=n)
    elif request.strategy.startswith("tokens:"):
        n = int(request.strategy.split(":")[1])
        strategy = FixedTokensStrategy(tokens_per_chunk=n)
    elif request.strategy == "sections":
        strategy = BySectionsStrategy()
    else:
        raise HTTPException(400, f"Unknown strategy: {request.strategy}. Use 'rows:N', 'tokens:N', or 'sections'")

    try:
        chunks = await connector.chunk(request.source_id, entity, strategy)
        return {
            "chunks": [
                {
                    "id": c.id,
                    "index": c.index,
                    "total_chunks": c.total_chunks,
                    "content": c.to_text(),  # Use to_text() method to convert data to string
                    "metadata": {
                        "estimated_tokens": c.metadata.estimated_tokens,
                        "row_range": c.metadata.row_range,
                        "byte_range": c.metadata.byte_range,
                    },
                }
                for c in chunks
            ],
            "total_chunks": len(chunks),
        }
    except ValueError as e:
        # Handle "Cannot chunk a directory" and similar validation errors
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# === Relationship Graph ===

@app.get("/graph")
async def get_graph(refresh: bool = False):
    """Get relationship graph across all sources."""
    connector = get_connector()

    try:
        graph = await connector.graph(refresh=refresh)
        return graph.to_dict()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/graph/find-related")
async def find_related(request: FindRelatedRequest):
    """Find related records across sources."""
    connector = get_connector()

    try:
        from cgc.core.schema import FieldId
        field_id = FieldId(request.source_id, request.entity, request.field)
        related = await connector.find_related(field_id, request.value)
        return {"related": related, "count": len(related)}
    except Exception as e:
        raise HTTPException(500, str(e))


# === Triplet Extraction ===

@app.post("/extract/triplets")
async def extract_triplets(request: TripletRequest):
    """Extract triplets from text.

    Supports pattern-only (fast) or hybrid GliNER+GliREL extraction (higher recall).
    Optionally force an industry pack via the `domain` parameter.
    """
    connector = get_connector()

    try:
        triplets = connector.extract_triplets(
            request.text, use_gliner=request.use_gliner, domain=request.domain
        )
        return {
            "triplets": [
                {
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "confidence": t.confidence,
                    "source_text": t.source_text,
                    "subject_label": t.metadata.get("subject_label") if t.metadata else None,
                    "object_label": t.metadata.get("object_label") if t.metadata else None,
                }
                for t in triplets
            ],
            "count": len(triplets),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/extract/structured")
async def extract_structured(request: StructuredExtractionRequest):
    """Extract triplets from structured data using hub-and-spoke model.

    Classifies columns (primary entity, foreign key, property, etc.)
    and builds entity relationships automatically.
    """
    connector = get_connector()

    try:
        triplets = connector.extract_triplets_structured(request.data)
        return {
            "triplets": [
                {
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "confidence": t.confidence,
                }
                for t in triplets
            ],
            "count": len(triplets),
            "rows_processed": len(request.data),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/extract/file")
async def extract_file(
    file: UploadFile = File(...),
    domain: str | None = Form(default=None),
    use_gliner: bool = Form(default=True),
):
    """Extract triplets from an uploaded file.

    Supports structured formats (CSV, JSON, XLS, XLSX) via hub-and-spoke extraction,
    and unstructured formats (text, PDF, Markdown, etc.) via pattern + ML extraction.
    """
    from cgc.adapters.parsers import parse_file

    try:
        content = await file.read()
        parsed = parse_file(content, file.filename or "unknown")

        connector = get_connector()

        if parsed.rows:
            triplets = connector.extract_triplets_structured(parsed.rows)
            file_type = "structured"
        else:
            triplets = connector.extract_triplets(parsed.text, use_gliner=use_gliner, domain=domain)
            file_type = "unstructured"

        return {
            "triplets": [
                {
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "confidence": t.confidence,
                    "source_text": t.source_text if hasattr(t, "source_text") else None,
                    "subject_label": t.metadata.get("subject_label") if t.metadata else None,
                    "object_label": t.metadata.get("object_label") if t.metadata else None,
                }
                for t in triplets
            ],
            "count": len(triplets),
            "file_type": file_type,
            "filename": file.filename,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/extract/chunked")
async def extract_chunked(request: ChunkedExtractionRequest):
    """Chunk a file then extract triplets from each chunk.

    Designed for unstructured data (PDFs, docs, large text files) where
    chunking before extraction improves results. Requires a connected
    filesystem source.
    """
    connector = get_connector()

    if not connector.has_source(request.source_id):
        raise HTTPException(404, f"Source not found: {request.source_id}")

    # Parse strategy
    if request.strategy.startswith("rows:"):
        n = int(request.strategy.split(":")[1])
        strategy = FixedRowsStrategy(rows_per_chunk=n)
    elif request.strategy.startswith("tokens:"):
        n = int(request.strategy.split(":")[1])
        strategy = FixedTokensStrategy(tokens_per_chunk=n)
    elif request.strategy == "sections":
        strategy = BySectionsStrategy()
    else:
        raise HTTPException(400, f"Unknown strategy: {request.strategy}. Use 'rows:N', 'tokens:N', or 'sections'")

    # Normalize entity
    entity = _normalize_entity(request.source_id, request.entity)

    try:
        result = await connector.extract_chunked(
            request.source_id, entity, strategy,
            use_gliner=request.use_gliner, domain=request.domain,
        )

        # Serialize triplets within each chunk
        for chunk_result in result["chunks"]:
            chunk_result["triplets"] = [
                {
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "confidence": t.confidence,
                    "source_text": t.source_text if hasattr(t, "source_text") else None,
                }
                for t in chunk_result["triplets"]
            ]

        return result
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/detect/domain")
async def detect_domain(request: DomainDetectionRequest):
    """Detect the industry domain of text for optimized extraction.

    Uses E5 embeddings to route text to the best-matching industry pack.
    """
    connector = get_connector()

    try:
        result = connector.detect_domain(request.text)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/packs")
async def list_packs():
    """List all available industry packs for domain-specific extraction."""
    from cgc.discovery.industry_packs import get_all_packs

    packs = get_all_packs()
    return {
        "packs": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "entity_labels": p.entity_labels,
                "relation_labels": p.relation_labels,
            }
            for p in packs
        ],
        "count": len(packs),
    }


# === Summary ===

@app.get("/summary")
async def get_summary():
    """Get compact summary of all connected sources (for LLM context)."""
    connector = get_connector()
    return {
        "summary": connector.summary(),
        "sources": connector.sources,
        "schemas_discovered": list(connector._schemas.keys()),
    }


@app.get("/context")
async def get_context():
    """Get full context state as dictionary."""
    connector = get_connector()
    return connector.to_dict()


def main():
    """Run the API server."""
    import uvicorn
    uvicorn.run("cgc.api.server:app", host="0.0.0.0", port=8420, reload=True)


if __name__ == "__main__":
    main()
