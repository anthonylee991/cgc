"""MCP (Model Context Protocol) server for Context Graph Connector.

This allows Claude Code and other MCP-compatible clients to use CGC
directly as a tool for managing context and accessing data sources.

Run with: python -m cgc.mcp.server
Or configure in claude_desktop_config.json / .claude/settings.json
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from cgc.connector import Connector
from cgc.core.chunk import FixedRowsStrategy, FixedTokensStrategy, BySectionsStrategy
from cgc.core.schema import FieldId


# Global connector instance
_connector: Connector | None = None


def get_connector() -> Connector:
    """Get or create the global connector."""
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector


def create_server() -> Server:
    """Create the MCP server with CGC tools."""
    server = Server("cgc")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available CGC tools."""
        return [
            Tool(
                name="cgc_add_source",
                description="Add a data source to CGC. Supports: postgres, mysql, sqlite, filesystem, qdrant, pinecone, pgvector, mongodb",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Unique identifier for this source",
                        },
                        "source_type": {
                            "type": "string",
                            "enum": ["postgres", "mysql", "sqlite", "filesystem", "qdrant", "pinecone", "pgvector", "mongodb"],
                            "description": "Type of data source",
                        },
                        "connection": {
                            "type": "string",
                            "description": "Connection string or path",
                        },
                    },
                    "required": ["source_id", "source_type", "connection"],
                },
            ),
            Tool(
                name="cgc_list_sources",
                description="List all connected data sources",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="cgc_remove_source",
                description="Remove a data source",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "ID of source to remove",
                        },
                    },
                    "required": ["source_id"],
                },
            ),
            Tool(
                name="cgc_discover",
                description="Discover schema for a data source. Returns tables/files, fields, relationships.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Source ID to discover",
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Force refresh cached schema",
                            "default": False,
                        },
                    },
                    "required": ["source_id"],
                },
            ),
            Tool(
                name="cgc_discover_all",
                description="Discover schemas for all connected sources",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "refresh": {
                            "type": "boolean",
                            "description": "Force refresh cached schemas",
                            "default": False,
                        },
                    },
                },
            ),
            Tool(
                name="cgc_sample",
                description="Get sample data from an entity (table/file). Use this to understand data before querying.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Source ID",
                        },
                        "entity": {
                            "type": "string",
                            "description": "Entity name (table name, file path)",
                        },
                        "n": {
                            "type": "integer",
                            "description": "Number of samples",
                            "default": 5,
                        },
                    },
                    "required": ["source_id", "entity"],
                },
            ),
            Tool(
                name="cgc_sql",
                description="Execute a SQL query against a database source",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Database source ID",
                        },
                        "sql": {
                            "type": "string",
                            "description": "SQL query to execute",
                        },
                    },
                    "required": ["source_id", "sql"],
                },
            ),
            Tool(
                name="cgc_search",
                description="Search for data using ILIKE pattern matching with trigram fallback",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Source ID",
                        },
                        "entity": {
                            "type": "string",
                            "description": "Entity to search",
                        },
                        "field": {
                            "type": "string",
                            "description": "Field to search in",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                    },
                    "required": ["source_id", "entity", "field", "query"],
                },
            ),
            Tool(
                name="cgc_chunk",
                description="Chunk data for LLM processing. Returns data in manageable pieces.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Source ID",
                        },
                        "entity": {
                            "type": "string",
                            "description": "Entity to chunk",
                        },
                        "strategy": {
                            "type": "string",
                            "description": "Chunking strategy: rows:N, tokens:N, or sections",
                            "default": "rows:100",
                        },
                        "chunk_index": {
                            "type": "integer",
                            "description": "Which chunk to return (0-indexed). If not specified, returns metadata about all chunks.",
                        },
                    },
                    "required": ["source_id", "entity"],
                },
            ),
            Tool(
                name="cgc_graph",
                description="Get relationship graph showing how entities across sources are connected",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "refresh": {
                            "type": "boolean",
                            "description": "Force refresh",
                            "default": False,
                        },
                    },
                },
            ),
            Tool(
                name="cgc_find_related",
                description="Find all records related to a specific value across sources",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Starting source ID",
                        },
                        "entity": {
                            "type": "string",
                            "description": "Starting entity",
                        },
                        "field": {
                            "type": "string",
                            "description": "Starting field",
                        },
                        "value": {
                            "type": "string",
                            "description": "Value to find relations for",
                        },
                    },
                    "required": ["source_id", "entity", "field", "value"],
                },
            ),
            Tool(
                name="cgc_summary",
                description="Get a compact summary of all connected sources and their schemas. Use this to understand available data.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="cgc_health",
                description="Check health/connectivity of all data sources",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            # === Session Tools ===
            Tool(
                name="cgc_session_new",
                description="Start a new session to track work. Use this at the beginning of a task to persist context across resets.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project name or path",
                        },
                        "goal": {
                            "type": "string",
                            "description": "What you're trying to accomplish",
                        },
                    },
                    "required": ["project"],
                },
            ),
            Tool(
                name="cgc_session_log",
                description="Log work done (file created, modified, decision made, etc.). This persists across context resets.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["created", "modified", "deleted", "analyzed", "tested", "decision", "note", "todo"],
                            "description": "Type of action",
                        },
                        "content": {
                            "type": "string",
                            "description": "For files: the path. For decisions/notes/todos: the text.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Additional context (e.g., why a decision was made)",
                        },
                    },
                    "required": ["action", "content"],
                },
            ),
            Tool(
                name="cgc_session_summary",
                description="Get summary of current session. Use this after context reset to understand what was done before.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="cgc_session_save",
                description="Save the current session to disk.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="cgc_session_load",
                description="Load a previous session or the most recent one.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to load. If not provided, loads the most recent.",
                        },
                    },
                },
            ),
            Tool(
                name="cgc_session_stats",
                description="Get session statistics including size, entry counts, and limit usage. Use to monitor session health.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="cgc_session_list",
                description="List all available sessions and archived sessions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_archived": {
                            "type": "boolean",
                            "description": "Include archived sessions in the list",
                        },
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Handle tool calls."""
        connector = get_connector()

        try:
            if name == "cgc_add_source":
                source_id = arguments["source_id"]
                source_type = arguments["source_type"]
                connection = arguments["connection"]

                if source_type == "postgres":
                    from cgc.adapters.sql import SqlAdapter
                    connector.add_source(SqlAdapter(source_id, connection))
                elif source_type == "mysql":
                    from cgc.adapters.sql import SqlAdapter
                    connector.add_source(SqlAdapter(source_id, connection))
                elif source_type == "sqlite":
                    from cgc.adapters.sql import SqlAdapter
                    conn = connection if connection.startswith("sqlite") else f"sqlite:///{connection}"
                    connector.add_source(SqlAdapter(source_id, conn))
                elif source_type == "filesystem":
                    from cgc.adapters.filesystem import FilesystemAdapter
                    connector.add_source(FilesystemAdapter(source_id, connection))
                elif source_type == "qdrant":
                    from cgc.adapters.vector.qdrant import QdrantAdapter
                    connector.add_source(QdrantAdapter(source_id, connection))
                elif source_type == "pinecone":
                    from cgc.adapters.vector.pinecone import PineconeAdapter
                    api_key = arguments.get("api_key", "")
                    connector.add_source(PineconeAdapter(source_id, api_key, connection))
                elif source_type == "pgvector":
                    from cgc.adapters.vector.pgvector import PgVectorAdapter
                    connector.add_source(PgVectorAdapter(source_id, connection))
                elif source_type == "mongodb":
                    from cgc.adapters.vector.mongodb import MongoVectorAdapter
                    database = arguments.get("database", "default")
                    connector.add_source(MongoVectorAdapter(source_id, connection, database))
                else:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Unknown source type: {source_type}")]
                    )

                return CallToolResult(
                    content=[TextContent(type="text", text=f"Added source: {source_id} ({source_type})")]
                )

            elif name == "cgc_list_sources":
                sources = connector.sources
                if not sources:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No sources connected")]
                    )
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Connected sources: {', '.join(sources)}")]
                )

            elif name == "cgc_remove_source":
                source_id = arguments["source_id"]
                if connector.remove_source(source_id):
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Removed source: {source_id}")]
                    )
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Source not found: {source_id}")]
                )

            elif name == "cgc_discover":
                source_id = arguments["source_id"]
                refresh = arguments.get("refresh", False)

                if not connector.has_source(source_id):
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Source not found: {source_id}")]
                    )

                try:
                    schema = await connector.discover(source_id, refresh=refresh)
                except asyncio.TimeoutError:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Discovery timed out for source '{source_id}'. The directory may contain too many files. Try adding exclude patterns or increasing the timeout.")]
                    )
                return CallToolResult(
                    content=[TextContent(type="text", text=schema.to_compact())]
                )

            elif name == "cgc_discover_all":
                refresh = arguments.get("refresh", False)
                results = []
                for sid in connector.sources:
                    try:
                        schema = await connector.discover(sid, refresh=refresh)
                        results.append(schema.to_compact())
                    except asyncio.TimeoutError:
                        results.append(f"Source: {sid}\n  (discovery timed out - directory may contain too many files)")
                return CallToolResult(
                    content=[TextContent(type="text", text="\n\n".join(results))]
                )

            elif name == "cgc_sample":
                source_id = arguments["source_id"]
                entity = arguments["entity"]
                n = arguments.get("n", 5)

                if not connector.has_source(source_id):
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Source not found: {source_id}")]
                    )

                samples = await connector.sample(source_id, entity, n)
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(samples, indent=2, default=str))]
                )

            elif name == "cgc_sql":
                source_id = arguments["source_id"]
                sql = arguments["sql"]

                if not connector.has_source(source_id):
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Source not found: {source_id}")]
                    )

                result = await connector.sql(source_id, sql)
                output = {
                    "rows": result.to_dicts(),
                    "row_count": result.total_count,
                    "columns": result.columns,
                }
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(output, indent=2, default=str))]
                )

            elif name == "cgc_search":
                source_id = arguments["source_id"]
                entity = arguments["entity"]
                field = arguments["field"]
                query = arguments["query"]

                if not connector.has_source(source_id):
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Source not found: {source_id}")]
                    )

                from cgc.core.query import SearchQuery
                search_query = SearchQuery(entity=entity, field=field, query=query, fuzzy_fallback=True)
                result = await connector.query(source_id, search_query)

                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result.to_dicts(), indent=2, default=str))]
                )

            elif name == "cgc_chunk":
                source_id = arguments["source_id"]
                entity = arguments["entity"]
                strategy_str = arguments.get("strategy", "rows:100")
                chunk_index = arguments.get("chunk_index")

                if not connector.has_source(source_id):
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Source not found: {source_id}")]
                    )

                # Parse strategy
                if strategy_str.startswith("rows:"):
                    n = int(strategy_str.split(":")[1])
                    strategy = FixedRowsStrategy(rows_per_chunk=n)
                elif strategy_str.startswith("tokens:"):
                    n = int(strategy_str.split(":")[1])
                    strategy = FixedTokensStrategy(tokens_per_chunk=n)
                elif strategy_str == "sections":
                    strategy = BySectionsStrategy()
                else:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Unknown strategy: {strategy_str}")]
                    )

                chunks = await connector.chunk(source_id, entity, strategy)

                if chunk_index is not None:
                    if 0 <= chunk_index < len(chunks):
                        chunk = chunks[chunk_index]
                        return CallToolResult(
                            content=[TextContent(type="text", text=f"Chunk {chunk_index + 1}/{len(chunks)}:\n\n{chunk.content}")]
                        )
                    else:
                        return CallToolResult(
                            content=[TextContent(type="text", text=f"Invalid chunk index. Available: 0-{len(chunks) - 1}")]
                        )
                else:
                    # Return metadata about chunks
                    summary = f"Total chunks: {len(chunks)}\n\n"
                    for c in chunks[:10]:
                        summary += f"- Chunk {c.index}: ~{c.metadata.estimated_tokens} tokens\n"
                    if len(chunks) > 10:
                        summary += f"... and {len(chunks) - 10} more"
                    summary += "\n\nUse chunk_index to retrieve a specific chunk."
                    return CallToolResult(
                        content=[TextContent(type="text", text=summary)]
                    )

            elif name == "cgc_graph":
                refresh = arguments.get("refresh", False)
                graph = await connector.graph(refresh=refresh)
                data = graph.to_dict()
                summary = f"Relationships: {data['total']}\n\n"
                for rel in data["relationships"][:20]:
                    summary += f"- {rel['from']} -> {rel['to']} ({rel['type']}, {rel['confidence']})\n"
                if data["total"] > 20:
                    summary += f"... and {data['total'] - 20} more"
                return CallToolResult(
                    content=[TextContent(type="text", text=summary)]
                )

            elif name == "cgc_find_related":
                source_id = arguments["source_id"]
                entity = arguments["entity"]
                field = arguments["field"]
                value = arguments["value"]

                field_id = FieldId(source_id, entity, field)
                related = await connector.find_related(field_id, value)

                if not related:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No related records found")]
                    )

                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(related, indent=2, default=str))]
                )

            elif name == "cgc_summary":
                summary = connector.summary()
                return CallToolResult(
                    content=[TextContent(type="text", text=summary or "No sources connected. Use cgc_add_source to add data sources.")]
                )

            elif name == "cgc_health":
                if not connector.sources:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No sources connected")]
                    )

                statuses = await connector.health_check()
                result = "Health check:\n\n"
                for source_id, status in statuses.items():
                    icon = "OK" if status.healthy else "X"
                    result += f"{icon} {source_id}: {'healthy' if status.healthy else status.message}"
                    if status.healthy and status.latency_ms:
                        result += f" ({status.latency_ms:.1f}ms)"
                    result += "\n"
                return CallToolResult(
                    content=[TextContent(type="text", text=result)]
                )

            # === Session Tools ===

            elif name == "cgc_session_new":
                from cgc.session import new_session, save_session
                project = arguments["project"]
                goal = arguments.get("goal", "")

                session = new_session(project, goal)
                save_session(session)

                return CallToolResult(
                    content=[TextContent(type="text", text=f"Started new session: {session.id}\nProject: {project}\nGoal: {goal or '(not set)'}\n\nUse cgc_session_log to track your work.")]
                )

            elif name == "cgc_session_log":
                from cgc.session import get_session, save_session
                action = arguments["action"]
                content = arguments["content"]
                description = arguments.get("description", "")

                session = get_session()
                if session is None:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No active session. Use cgc_session_new to start one.")]
                    )

                if action == "created":
                    session.log_file_created(content, description)
                elif action == "modified":
                    session.log_file_modified(content, description)
                elif action == "deleted":
                    session.log_file_deleted(content, description)
                elif action == "analyzed":
                    session.log_analyzed(content, description)
                elif action == "tested":
                    session.log_tested(content, description)
                elif action == "decision":
                    session.log_decision(content, description)
                elif action == "note":
                    session.add_note(content)
                elif action == "todo":
                    session.add_todo(content)
                else:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Unknown action: {action}")]
                    )

                save_session(session)
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Logged: {action} - {content}")]
                )

            elif name == "cgc_session_summary":
                from cgc.session import get_session

                session = get_session(create_if_missing=False)
                if session is None:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No session found. Use cgc_session_new to start one, or cgc_session_load to load a previous session.")]
                    )

                return CallToolResult(
                    content=[TextContent(type="text", text=session.summary())]
                )

            elif name == "cgc_session_save":
                from cgc.session import get_session, save_session

                session = get_session(create_if_missing=False)
                if session is None:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No active session to save.")]
                    )

                path = save_session(session)
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Session saved to: {path}")]
                )

            elif name == "cgc_session_load":
                from cgc.session import load_session

                session_id = arguments.get("session_id")
                session = load_session(session_id)

                if session is None:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No sessions found.")]
                    )

                return CallToolResult(
                    content=[TextContent(type="text", text=f"Loaded session: {session.id}\n\n{session.summary()}")]
                )

            elif name == "cgc_session_stats":
                from cgc.session import get_session

                session = get_session(create_if_missing=False)
                if session is None:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No active session. Use cgc_session_new to start one.")]
                    )

                stats = session.get_stats()
                result = f"""Session Statistics: {session.id}

Entries:
  Work items: {stats.work_items_count}/{stats.work_items_limit}
  Decisions:  {stats.decisions_count}/{stats.decisions_limit}
  Notes:      {stats.notes_count}/{stats.notes_limit}
  TODOs:      {stats.todos_count}/{stats.todos_limit}
  Context:    {stats.context_keys_count}/{stats.context_limit}

Size:
  Current:    {stats.estimated_size_bytes:,} bytes
  Limit:      {stats.size_limit:,} bytes
  Usage:      {stats.size_percent:.1f}%

Status: {"WARNING: Session will be rotated on next save" if stats.needs_rotation else "OK - Healthy"}"""

                return CallToolResult(
                    content=[TextContent(type="text", text=result)]
                )

            elif name == "cgc_session_list":
                from cgc.session import get_tracker

                tracker = get_tracker()
                include_archived = arguments.get("include_archived", False)

                sessions = tracker.list_sessions()
                result = "Available Sessions:\n\n"

                if not sessions:
                    result += "(No sessions found)\n"
                else:
                    for s in sessions[:20]:  # Show last 20
                        compressed = "[Z]" if s.get("compressed") else "[F]"
                        size_kb = s["size_bytes"] / 1024
                        result += f"{compressed} {s['id']} - {size_kb:.1f}KB - {s['modified']}\n"

                    if len(sessions) > 20:
                        result += f"  ...and {len(sessions) - 20} more\n"

                if include_archived:
                    archived = tracker.list_archived()
                    result += "\nArchived Sessions:\n\n"
                    if not archived:
                        result += "(No archived sessions)\n"
                    else:
                        for s in archived[:10]:
                            size_kb = s["size_bytes"] / 1024
                            result += f"[A] {s['id']} - {size_kb:.1f}KB - {s['modified']}\n"

                        if len(archived) > 10:
                            result += f"  ...and {len(archived) - 10} more\n"

                return CallToolResult(
                    content=[TextContent(type="text", text=result)]
                )

            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")]
                )

        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")]
            )

    return server


async def serve():
    """Run the MCP server."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point."""
    asyncio.run(serve())


if __name__ == "__main__":
    main()
