"""Secure FastAPI server for Context Graph Connector.

This is the hardened version of the API server with:
- API key authentication
- Rate limiting
- Input validation
- SQL injection protection
- Path traversal protection
- Security headers
- Request logging

For development/testing, use server.py with CGC_REQUIRE_AUTH=false
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Annotated

from fastapi import FastAPI, HTTPException, Query, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from cgc.connector import Connector
from cgc.core.chunk import FixedRowsStrategy, FixedTokensStrategy, BySectionsStrategy
from cgc.security.auth import APIKey, APIKeyAuth, verify_api_key, get_key_store
from cgc.security.config import get_security_config, SecurityConfig
from cgc.security.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    RequestSizeLimitMiddleware,
)
from cgc.security.validation import (
    validate_source_id,
    validate_entity_name,
    validate_field_name,
    validate_path,
    validate_connection_string,
    sanitize_sql,
    is_safe_sql,
    mask_credentials,
    SQLValidationError,
    PathValidationError,
    InputValidationError,
)


# === Request/Response Models with Validation ===

class SourceConfig(BaseModel):
    """Configuration for adding a data source."""

    source_id: str = Field(..., min_length=1, max_length=64)
    source_type: str = Field(..., pattern=r'^(postgres|mysql|sqlite|filesystem|qdrant|pinecone|pgvector|mongodb)$')
    connection: str = Field(..., min_length=1, max_length=2048)
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        return validate_source_id(v)

    @field_validator('connection')
    @classmethod
    def validate_connection(cls, v: str, info) -> str:
        # Get source_type from values if available
        source_type = info.data.get('source_type', 'unknown')
        return validate_connection_string(v, source_type)


class SqlQueryRequest(BaseModel):
    """SQL query request."""

    source_id: str = Field(..., min_length=1, max_length=64)
    sql: str = Field(..., min_length=1, max_length=10000)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        return validate_source_id(v)

    @field_validator('sql')
    @classmethod
    def validate_sql(cls, v: str) -> str:
        return sanitize_sql(v)


class SampleRequest(BaseModel):
    """Sample data request."""

    source_id: str = Field(..., min_length=1, max_length=64)
    entity: str = Field(..., min_length=1, max_length=256)
    n: int = Field(default=5, ge=1, le=1000)

    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        return validate_source_id(v)

    @field_validator('entity')
    @classmethod
    def validate_entity(cls, v: str) -> str:
        return validate_entity_name(v)


class ChunkRequest(BaseModel):
    """Chunk data request."""

    source_id: str = Field(..., min_length=1, max_length=64)
    entity: str = Field(..., min_length=1, max_length=256)
    strategy: str = Field(default="rows:1000", pattern=r'^(rows:\d+|tokens:\d+|sections)$')

    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        return validate_source_id(v)

    @field_validator('entity')
    @classmethod
    def validate_entity(cls, v: str) -> str:
        return validate_entity_name(v)


class SearchRequest(BaseModel):
    """Search request."""

    source_id: str = Field(..., min_length=1, max_length=64)
    query: str = Field(..., min_length=1, max_length=1000)
    entity: str | None = Field(default=None, max_length=256)  # Optional for filesystem
    field: str | None = Field(default=None, max_length=128)   # Optional for filesystem
    fuzzy_fallback: bool = True

    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        return validate_source_id(v)

    @field_validator('entity')
    @classmethod
    def validate_entity(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_entity_name(v)
        return v

    @field_validator('field')
    @classmethod
    def validate_field(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_field_name(v)
        return v


class VectorSearchRequest(BaseModel):
    """Vector similarity search request."""

    source_id: str = Field(..., min_length=1, max_length=64)
    collection: str = Field(..., min_length=1, max_length=256)
    query_vector: list[float] = Field(..., min_length=1, max_length=4096)
    top_k: int = Field(default=10, ge=1, le=1000)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    filter: dict[str, Any] | None = None

    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        return validate_source_id(v)


class TripletRequest(BaseModel):
    """Triplet extraction request."""

    text: str = Field(..., min_length=1, max_length=100000)
    use_gliner: bool = True
    domain: str | None = None


class StructuredExtractionRequest(BaseModel):
    """Structured data extraction request."""

    data: list[dict[str, Any]]


class DomainDetectionRequest(BaseModel):
    """Domain detection request."""

    text: str = Field(..., min_length=1, max_length=100000)


class FindRelatedRequest(BaseModel):
    """Find related records request."""

    source_id: str = Field(..., min_length=1, max_length=64)
    entity: str = Field(..., min_length=1, max_length=256)
    field: str = Field(..., min_length=1, max_length=128)
    value: Any

    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        return validate_source_id(v)

    @field_validator('entity')
    @classmethod
    def validate_entity(cls, v: str) -> str:
        return validate_entity_name(v)

    @field_validator('field')
    @classmethod
    def validate_field(cls, v: str) -> str:
        return validate_field_name(v)


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
    # Strip source_id prefix if accidentally included
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
    global _connector
    if _connector:
        await _connector.close()
        _connector = None


# === Create Secure App ===

def create_secure_app(config: SecurityConfig | None = None) -> FastAPI:
    """Create a secure FastAPI app with all security features enabled."""

    if config is None:
        config = get_security_config()

    app = FastAPI(
        title="Context Graph Connector API",
        description="Secure programmatic data access for LLM agents",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not config.require_auth else None,  # Disable docs if auth required
        redoc_url=None,
    )

    # Add security middleware (order matters - first added = last executed)
    app.add_middleware(RequestLoggingMiddleware, mask_credentials=config.mask_credentials)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=config.max_request_size_mb)

    if config.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_window=config.rate_limit_requests,
            window_seconds=config.rate_limit_window_seconds,
        )

    # Restrictive CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=False,  # No credentials with wildcard origins
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["X-API-Key", "Content-Type"],
        max_age=3600,
    )

    return app


# Create the secure app
app = create_secure_app()


# === Error Handlers ===

@app.exception_handler(SQLValidationError)
async def sql_validation_error_handler(request, exc):
    return HTTPException(status_code=400, detail=f"SQL validation error: {exc}")


@app.exception_handler(PathValidationError)
async def path_validation_error_handler(request, exc):
    return HTTPException(status_code=400, detail=f"Path validation error: {exc}")


@app.exception_handler(InputValidationError)
async def input_validation_error_handler(request, exc):
    return HTTPException(status_code=400, detail=f"Input validation error: {exc}")


# === Public Endpoints (no auth) ===

@app.get("/")
async def root():
    """API root."""
    return {
        "name": "Context Graph Connector",
        "version": "0.1.0",
        "secure": True,
    }


@app.get("/health")
async def health():
    """Health check (no auth required)."""
    return {"status": "healthy"}


# === Admin Endpoints ===

@app.post("/admin/api-keys", dependencies=[Security(APIKeyAuth("admin"))])
async def create_api_key(
    name: str = Query(..., min_length=1, max_length=64),
    permissions: str = Query(default="*"),
    expires_days: int = Query(default=None, ge=1, le=365),
):
    """Create a new API key (requires admin permission)."""
    store = get_key_store()
    perms = [p.strip() for p in permissions.split(",")]

    plaintext_key, api_key = store.create_key(
        name=name,
        permissions=perms,
        expires_days=expires_days,
    )

    return {
        "key": plaintext_key,  # Only shown once!
        "name": api_key.name,
        "permissions": api_key.permissions,
        "expires_at": api_key.expires_at,
        "warning": "Save this key! It will not be shown again.",
    }


@app.get("/admin/api-keys", dependencies=[Security(APIKeyAuth("admin"))])
async def list_api_keys():
    """List all API keys (requires admin permission)."""
    store = get_key_store()
    keys = store.list_keys()

    return {
        "keys": [
            {
                "name": k.name,
                "created_at": k.created_at,
                "last_used": k.last_used,
                "expires_at": k.expires_at,
                "permissions": k.permissions,
                "active": k.active,
            }
            for k in keys
        ]
    }


# === Authenticated Endpoints ===

@app.get("/sources", dependencies=[Security(verify_api_key)])
async def list_sources(api_key: APIKey = Security(verify_api_key)):
    """List connected sources."""
    connector = get_connector()

    # Filter sources based on API key permissions
    sources = connector.sources
    if "*" not in api_key.allowed_sources:
        sources = [s for s in sources if s in api_key.allowed_sources]

    return {"sources": sources}


@app.post("/sources", dependencies=[Security(verify_api_key)])
async def add_source(config: SourceConfig, api_key: APIKey = Security(verify_api_key)):
    """Add a data source."""
    connector = get_connector()

    # Check if API key can access this source
    if "*" not in api_key.allowed_sources and config.source_id not in api_key.allowed_sources:
        raise HTTPException(403, f"Not authorized to create source: {config.source_id}")

    try:
        if config.source_type == "postgres":
            from cgc.adapters.sql import SqlAdapter
            connector.add_source(SqlAdapter(config.source_id, config.connection, **config.options))
        elif config.source_type == "mysql":
            from cgc.adapters.sql import SqlAdapter
            connector.add_source(SqlAdapter(config.source_id, config.connection, **config.options))
        elif config.source_type == "sqlite":
            from cgc.adapters.sql import SqlAdapter
            conn = config.connection if config.connection.startswith("sqlite") else f"sqlite:///{config.connection}"
            connector.add_source(SqlAdapter(config.source_id, conn, **config.options))
        elif config.source_type == "filesystem":
            # Additional path validation for filesystem
            security_config = get_security_config()
            validate_path(
                config.connection,
                allowed_paths=security_config.allowed_paths,
                blocked_paths=security_config.blocked_paths,
            )
            from cgc.adapters.filesystem import FilesystemAdapter
            connector.add_source(FilesystemAdapter(config.source_id, config.connection, **config.options))
        elif config.source_type == "qdrant":
            from cgc.adapters.vector.qdrant import QdrantAdapter
            connector.add_source(QdrantAdapter(config.source_id, config.connection, **config.options))
        elif config.source_type == "pinecone":
            from cgc.adapters.vector.pinecone import PineconeAdapter
            api_key_val = config.options.pop("api_key", "")
            connector.add_source(PineconeAdapter(config.source_id, api_key_val, config.connection, **config.options))
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

    except PathValidationError as e:
        raise HTTPException(400, f"Path validation error: {e}")
    except Exception as e:
        # Mask any credentials in error message
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.delete("/sources/{source_id}", dependencies=[Security(verify_api_key)])
async def remove_source(source_id: str, api_key: APIKey = Security(verify_api_key)):
    """Remove a data source."""
    source_id = validate_source_id(source_id)

    if "*" not in api_key.allowed_sources and source_id not in api_key.allowed_sources:
        raise HTTPException(403, f"Not authorized to remove source: {source_id}")

    connector = get_connector()
    if connector.remove_source(source_id):
        return {"status": "removed", "source_id": source_id}
    raise HTTPException(404, f"Source not found: {source_id}")


@app.get("/sources/{source_id}/schema", dependencies=[Security(verify_api_key)])
async def discover_schema(
    source_id: str,
    refresh: bool = False,
    api_key: APIKey = Security(verify_api_key),
):
    """Discover schema for a source."""
    source_id = validate_source_id(source_id)

    if "*" not in api_key.allowed_sources and source_id not in api_key.allowed_sources:
        raise HTTPException(403, f"Not authorized to access source: {source_id}")

    connector = get_connector()

    if not connector.has_source(source_id):
        raise HTTPException(404, f"Source not found: {source_id}")

    try:
        schema = await connector.discover(source_id, refresh=refresh)
        return schema.to_dict()
    except Exception as e:
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.post("/query/sql", dependencies=[Security(verify_api_key)])
async def execute_sql(request: SqlQueryRequest, api_key: APIKey = Security(verify_api_key)):
    """Execute a SQL query (SELECT only by default)."""
    if "*" not in api_key.allowed_sources and request.source_id not in api_key.allowed_sources:
        raise HTTPException(403, f"Not authorized to access source: {request.source_id}")

    # Check SQL permissions
    if not api_key.has_permission("sql:write"):
        is_safe, error = is_safe_sql(request.sql, allow_mutations=False)
        if not is_safe:
            raise HTTPException(400, error)

    connector = get_connector()

    if not connector.has_source(request.source_id):
        raise HTTPException(404, f"Source not found: {request.source_id}")

    try:
        result = await connector.sql(request.source_id, request.sql, **request.params)

        # Enforce max rows
        config = get_security_config()
        rows = result.to_dicts()
        if len(rows) > config.sql_max_rows:
            rows = rows[:config.sql_max_rows]

        total = result.total_count or len(rows)
        return {
            "rows": rows,
            "row_count": min(total, config.sql_max_rows),
            "columns": result.columns,
            "execution_time_ms": result.execution_time_ms,
            "truncated": total > config.sql_max_rows,
        }
    except Exception as e:
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.post("/query/search", dependencies=[Security(verify_api_key)])
async def execute_search(request: SearchRequest, api_key: APIKey = Security(verify_api_key)):
    """Execute a pattern search. For databases uses ILIKE, for filesystems uses grep-style search."""
    if "*" not in api_key.allowed_sources and request.source_id not in api_key.allowed_sources:
        raise HTTPException(403, f"Not authorized to access source: {request.source_id}")

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
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.post("/sample", dependencies=[Security(verify_api_key)])
async def sample_data(request: SampleRequest, api_key: APIKey = Security(verify_api_key)):
    """Sample data from an entity."""
    if "*" not in api_key.allowed_sources and request.source_id not in api_key.allowed_sources:
        raise HTTPException(403, f"Not authorized to access source: {request.source_id}")

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
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.post("/chunk", dependencies=[Security(verify_api_key)])
async def chunk_data(request: ChunkRequest, api_key: APIKey = Security(verify_api_key)):
    """Chunk data from an entity."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Chunk request - source_id: {request.source_id}, entity: {request.entity!r}, strategy: {request.strategy}")

    if "*" not in api_key.allowed_sources and request.source_id not in api_key.allowed_sources:
        raise HTTPException(403, f"Not authorized to access source: {request.source_id}")

    connector = get_connector()

    if not connector.has_source(request.source_id):
        raise HTTPException(404, f"Source not found: {request.source_id}")

    # Validate entity is provided
    if not request.entity or not request.entity.strip():
        raise HTTPException(400, "entity is required - please specify a filename to chunk")

    # Normalize entity name
    entity = _normalize_entity(request.source_id, request.entity)
    logger.info(f"Normalized entity: {entity!r}")

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
        logger.info(f"Starting chunking for {entity}...")
        chunks = await connector.chunk(request.source_id, entity, strategy)
        logger.info(f"Chunking complete: {len(chunks)} chunks created")
        return {
            "chunks": [
                {
                    "id": c.id,
                    "index": c.index,
                    "total_chunks": c.total_chunks,
                    "content": c.to_text(),  # Include the actual content
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
        logger.error(f"ValueError during chunking: {e}")
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError during chunking: {e}")
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Exception during chunking: {e}", exc_info=True)
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.get("/chunk/{source_id}/{entity}/{chunk_index}", dependencies=[Security(verify_api_key)])
async def get_chunk(
    source_id: str,
    entity: str,
    chunk_index: int,
    strategy: str = Query(default="rows:1000"),
    api_key: APIKey = Security(verify_api_key),
):
    """Get a specific chunk by index."""
    source_id = validate_source_id(source_id)
    entity = validate_entity_name(entity)

    if "*" not in api_key.allowed_sources and source_id not in api_key.allowed_sources:
        raise HTTPException(403, f"Not authorized to access source: {source_id}")

    connector = get_connector()

    if not connector.has_source(source_id):
        raise HTTPException(404, f"Source not found: {source_id}")

    # Parse strategy
    if strategy.startswith("rows:"):
        n = int(strategy.split(":")[1])
        strat = FixedRowsStrategy(rows_per_chunk=n)
    elif strategy.startswith("tokens:"):
        n = int(strategy.split(":")[1])
        strat = FixedTokensStrategy(tokens_per_chunk=n)
    else:
        strat = BySectionsStrategy()

    try:
        chunks = await connector.chunk(source_id, entity, strat)

        if chunk_index < 0 or chunk_index >= len(chunks):
            raise HTTPException(400, f"Invalid chunk index. Available: 0-{len(chunks)-1}")

        chunk = chunks[chunk_index]
        return {
            "id": chunk.id,
            "index": chunk.index,
            "total_chunks": chunk.total_chunks,
            "content": chunk.to_text(),
            "metadata": {
                "estimated_tokens": chunk.metadata.estimated_tokens,
                "row_range": chunk.metadata.row_range,
                "byte_range": chunk.metadata.byte_range,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.post("/extract/triplets", dependencies=[Security(verify_api_key)])
async def extract_triplets(request: TripletRequest):
    """Extract triplets from text."""
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
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.post("/extract/structured", dependencies=[Security(verify_api_key)])
async def extract_structured(request: StructuredExtractionRequest):
    """Extract triplets from structured data using hub-and-spoke model."""
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
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.post("/detect/domain", dependencies=[Security(verify_api_key)])
async def detect_domain(request: DomainDetectionRequest):
    """Detect the industry domain of text for optimized extraction."""
    connector = get_connector()

    try:
        result = connector.detect_domain(request.text)
        return result
    except Exception as e:
        error_msg = mask_credentials(str(e))
        raise HTTPException(500, error_msg)


@app.get("/packs", dependencies=[Security(verify_api_key)])
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


@app.get("/summary", dependencies=[Security(verify_api_key)])
async def get_summary(api_key: APIKey = Security(verify_api_key)):
    """Get compact summary of connected sources."""
    connector = get_connector()

    # Filter based on permissions
    sources = connector.sources
    if "*" not in api_key.allowed_sources:
        sources = [s for s in sources if s in api_key.allowed_sources]

    return {
        "sources": sources,
        "summary": connector.summary(),
    }


# === Main ===

def main():
    """Run the secure API server."""
    import uvicorn

    config = get_security_config()

    print(f"Starting secure CGC API server on {config.bind_host}:{config.bind_port}")
    print(f"Authentication: {'REQUIRED' if config.require_auth else 'DISABLED'}")
    print(f"Rate limiting: {'ENABLED' if config.rate_limit_enabled else 'DISABLED'}")

    if config.require_auth:
        print("\nTo create an API key, set CGC_REQUIRE_AUTH=false temporarily and use /admin/api-keys")

    uvicorn.run(
        "cgc.api.secure_server:app",
        host=config.bind_host,
        port=config.bind_port,
        reload=False,  # Don't reload in production
    )


if __name__ == "__main__":
    main()
