"""Unified CLI for Context Graph Connector.

This is the single entry point for all CGC functionality:
- CLI commands (discover, sample, chunk, etc.)
- MCP server (for Claude integration)
- API server (HTTP API)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from cgc.connector import Connector
from cgc.core.chunk import FixedRowsStrategy, FixedTokensStrategy, BySectionsStrategy

# Main app
app = typer.Typer(
    name="cgc",
    help="Context Graph Connector - Programmatic data access for LLM agents",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def run_async(coro):
    """Run an async function."""
    return asyncio.run(coro)


# =============================================================================
# Server Commands
# =============================================================================

@app.command()
def serve(
    secure: bool = typer.Option(False, "--secure", "-s", help="Enable security features (auth, rate limiting)"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8420, "--port", "-p", help="Port to bind to"),
):
    """Start the HTTP API server.

    Examples:
        cgc serve                    # Start dev server on localhost:8420
        cgc serve --secure           # Start with authentication required
        cgc serve --host 0.0.0.0     # Allow network access
        cgc serve --port 9000        # Use different port
    """
    import uvicorn

    if secure:
        from cgc.api.secure_server import app as api_app
        from cgc.security.config import get_security_config

        config = get_security_config()
        console.print(f"[bold green]Starting secure CGC API server[/bold green]")
        console.print(f"  Host: {host}")
        console.print(f"  Port: {port}")
        console.print(f"  Authentication: [yellow]REQUIRED[/yellow]")
        console.print(f"  Rate limiting: [green]ENABLED[/green]")
        console.print()
        console.print("[dim]To create an API key, temporarily set CGC_REQUIRE_AUTH=false[/dim]")

        uvicorn.run(
            "cgc.api.secure_server:app",
            host=host,
            port=port,
            reload=False,
        )
    else:
        from cgc.api.server import app as api_app

        console.print(f"[bold green]Starting CGC API server[/bold green]")
        console.print(f"  Host: {host}")
        console.print(f"  Port: {port}")
        console.print(f"  Docs: http://{host}:{port}/docs")
        console.print()
        console.print("[yellow]Warning: No authentication - use --secure for production[/yellow]")

        uvicorn.run(
            "cgc.api.server:app",
            host=host,
            port=port,
            reload=False,
        )


@app.command()
def mcp():
    """Start the MCP server (for Claude integration).

    This runs the Model Context Protocol server over stdio.
    Configure in Claude Desktop or Claude Code settings.

    Example Claude config:
        {
            "mcpServers": {
                "cgc": {
                    "command": "path/to/cgc.exe",
                    "args": ["mcp"]
                }
            }
        }
    """
    # Import and run MCP server
    from cgc.mcp.server import serve as mcp_serve
    asyncio.run(mcp_serve())


# =============================================================================
# Data Source Commands
# =============================================================================

@app.command()
def init():
    """Initialize a new CGC configuration file."""
    config = '''# CGC Configuration
# Add your data sources here

[cache]
path = ".cgc/cache.db"

# Example sources:
#
# [[sources]]
# id = "main_db"
# type = "postgres"
# connection = "postgresql://user:pass@localhost/myapp"
#
# [[sources]]
# id = "logs"
# type = "filesystem"
# path = "./logs"
#
# [[sources]]
# id = "vectors"
# type = "qdrant"
# url = "http://localhost:6333"
'''
    config_path = Path("cgc.toml")

    if config_path.exists():
        console.print("[yellow]cgc.toml already exists[/yellow]")
        return

    config_path.write_text(config)
    console.print("[green]Created cgc.toml[/green]")

    # Create cache directory
    cache_dir = Path(".cgc")
    cache_dir.mkdir(exist_ok=True)
    console.print("[green]Created .cgc/ directory[/green]")


@app.command()
def discover(
    source_type: str = typer.Argument(..., help="Source type: postgres, sqlite, mysql, filesystem"),
    connection: str = typer.Argument(..., help="Connection string or path"),
    source_id: str = typer.Option("default", "--id", "-i", help="Source ID"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (JSON)"),
):
    """Discover schema for a data source.

    Examples:
        cgc discover postgres "postgresql://localhost/mydb"
        cgc discover sqlite ./data.db
        cgc discover filesystem ./documents
    """

    async def run():
        connector = Connector()

        # Add source based on type
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
        else:
            console.print(f"[red]Unknown source type: {source_type}[/red]")
            raise typer.Exit(1)

        try:
            schema = await connector.discover(source_id)

            if output:
                data = schema.to_dict()
                Path(output).write_text(json.dumps(data, indent=2))
                console.print(f"[green]Saved to {output}[/green]")
            else:
                # Display schema
                console.print(f"\n[bold]{schema.source_id}[/bold] ({schema.source_type.value})")
                console.print(f"Discovered at: {schema.discovered_at.isoformat()}")

                if schema.stats:
                    console.print(
                        f"Total: {schema.stats.total_entities} entities, "
                        f"{schema.stats.total_fields} fields"
                    )

                console.print()

                # Table of entities
                table = Table(title="Entities")
                table.add_column("Name")
                table.add_column("Type")
                table.add_column("Rows")
                table.add_column("Fields")

                for entity in schema.entities[:20]:
                    table.add_row(
                        entity.name,
                        entity.entity_type.value,
                        str(entity.row_count or "-"),
                        str(len(entity.fields)),
                    )

                if len(schema.entities) > 20:
                    table.add_row("...", f"+{len(schema.entities) - 20} more", "", "")

                console.print(table)

                # Relationships
                if schema.relationships:
                    console.print(f"\n[bold]Relationships:[/bold] {len(schema.relationships)}")
                    for rel in schema.relationships[:10]:
                        console.print(f"  {rel}")

        finally:
            await connector.close()

    run_async(run())


@app.command()
def sample(
    source_type: str = typer.Argument(..., help="Source type"),
    connection: str = typer.Argument(..., help="Connection string or path"),
    entity: str = typer.Argument(..., help="Entity name (table or file)"),
    n: int = typer.Option(5, "--n", "-n", help="Number of samples"),
    source_id: str = typer.Option("default", "--id", "-i", help="Source ID"),
):
    """Sample data from an entity.

    Examples:
        cgc sample postgres "postgresql://localhost/mydb" users
        cgc sample sqlite ./data.db orders --n 10
        cgc sample filesystem ./docs report.pdf
    """

    async def run():
        connector = Connector()

        if source_type in ("postgres", "mysql"):
            from cgc.adapters.sql import SqlAdapter
            connector.add_source(SqlAdapter(source_id, connection))
        elif source_type == "sqlite":
            from cgc.adapters.sql import SqlAdapter
            conn = connection if connection.startswith("sqlite") else f"sqlite:///{connection}"
            connector.add_source(SqlAdapter(source_id, conn))
        elif source_type == "filesystem":
            from cgc.adapters.filesystem import FilesystemAdapter
            connector.add_source(FilesystemAdapter(source_id, connection))
        else:
            console.print(f"[red]Unknown source type: {source_type}[/red]")
            raise typer.Exit(1)

        try:
            samples = await connector.sample(source_id, entity, n)

            if not samples:
                console.print("[yellow]No data[/yellow]")
                return

            # Display as table
            table = Table(title=f"Sample from {entity}")
            for col in samples[0].keys():
                table.add_column(str(col))

            for row in samples:
                table.add_row(*[str(v)[:50] for v in row.values()])

            console.print(table)

        finally:
            await connector.close()

    run_async(run())


@app.command()
def sql(
    source_type: str = typer.Argument(..., help="Source type: postgres, mysql, sqlite"),
    connection: str = typer.Argument(..., help="Connection string"),
    query: str = typer.Argument(..., help="SQL query to execute"),
    source_id: str = typer.Option("default", "--id", "-i", help="Source ID"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (JSON)"),
):
    """Execute a SQL query.

    Examples:
        cgc sql postgres "postgresql://localhost/mydb" "SELECT * FROM users LIMIT 10"
        cgc sql sqlite ./data.db "SELECT COUNT(*) FROM orders"
    """

    async def run():
        connector = Connector()

        if source_type in ("postgres", "mysql"):
            from cgc.adapters.sql import SqlAdapter
            connector.add_source(SqlAdapter(source_id, connection))
        elif source_type == "sqlite":
            from cgc.adapters.sql import SqlAdapter
            conn = connection if connection.startswith("sqlite") else f"sqlite:///{connection}"
            connector.add_source(SqlAdapter(source_id, conn))
        else:
            console.print(f"[red]Unknown source type: {source_type}[/red]")
            raise typer.Exit(1)

        try:
            result = await connector.sql(source_id, query)

            if output:
                Path(output).write_text(json.dumps(result.to_dicts(), indent=2, default=str))
                console.print(f"[green]Saved {result.total_count} rows to {output}[/green]")
            else:
                rows = result.to_dicts()

                if not rows:
                    console.print("[yellow]No results[/yellow]")
                    return

                table = Table(title=f"Query Results ({result.total_count} rows, {result.execution_time_ms:.1f}ms)")
                for col in result.columns:
                    table.add_column(str(col))

                for row in rows[:50]:
                    table.add_row(*[str(v)[:50] for v in row.values()])

                if len(rows) > 50:
                    console.print(f"[dim]Showing first 50 of {len(rows)} rows[/dim]")

                console.print(table)

        finally:
            await connector.close()

    run_async(run())


@app.command()
def chunk(
    source_type: str = typer.Argument(..., help="Source type"),
    connection: str = typer.Argument(..., help="Connection string or path"),
    entity: str = typer.Argument(..., help="Entity name"),
    strategy: str = typer.Option("rows:1000", "--strategy", "-s", help="Strategy: rows:N, tokens:N, sections"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    source_id: str = typer.Option("default", "--id", "-i", help="Source ID"),
    get: Optional[int] = typer.Option(None, "--get", "-g", help="Get specific chunk content by index"),
):
    """Chunk data from an entity.

    Examples:
        cgc chunk filesystem ./docs report.pdf --strategy tokens:2000
        cgc chunk postgres "postgresql://localhost/mydb" users --strategy rows:500
        cgc chunk filesystem ./docs report.pdf --get 0   # Get first chunk content
    """

    async def run():
        connector = Connector()

        if source_type in ("postgres", "mysql"):
            from cgc.adapters.sql import SqlAdapter
            connector.add_source(SqlAdapter(source_id, connection))
        elif source_type == "sqlite":
            from cgc.adapters.sql import SqlAdapter
            conn = connection if connection.startswith("sqlite") else f"sqlite:///{connection}"
            connector.add_source(SqlAdapter(source_id, conn))
        elif source_type == "filesystem":
            from cgc.adapters.filesystem import FilesystemAdapter
            connector.add_source(FilesystemAdapter(source_id, connection))
        else:
            console.print(f"[red]Unknown source type: {source_type}[/red]")
            raise typer.Exit(1)

        # Parse strategy
        if strategy.startswith("rows:"):
            n = int(strategy.split(":")[1])
            strat = FixedRowsStrategy(rows_per_chunk=n)
        elif strategy.startswith("tokens:"):
            n = int(strategy.split(":")[1])
            strat = FixedTokensStrategy(tokens_per_chunk=n)
        elif strategy == "sections":
            strat = BySectionsStrategy()
        else:
            console.print(f"[red]Unknown strategy: {strategy}[/red]")
            raise typer.Exit(1)

        try:
            chunks = await connector.chunk(source_id, entity, strat)

            # If --get is specified, show that chunk's content
            if get is not None:
                if get < 0 or get >= len(chunks):
                    console.print(f"[red]Invalid chunk index. Available: 0-{len(chunks)-1}[/red]")
                    raise typer.Exit(1)

                chunk = chunks[get]
                console.print(f"[bold]Chunk {get + 1}/{len(chunks)}[/bold]")
                console.print(f"Estimated tokens: ~{chunk.metadata.estimated_tokens:,}")
                console.print()
                console.print(chunk.to_text())
                return

            console.print(f"Created [bold]{len(chunks)}[/bold] chunks")

            table = Table(title="Chunks")
            table.add_column("Index")
            table.add_column("ID")
            table.add_column("Tokens (est)")
            table.add_column("Range")

            for chunk in chunks[:20]:
                range_str = ""
                if chunk.metadata.row_range:
                    range_str = f"rows {chunk.metadata.row_range[0]}-{chunk.metadata.row_range[1]}"
                elif chunk.metadata.byte_range:
                    range_str = f"bytes {chunk.metadata.byte_range[0]}-{chunk.metadata.byte_range[1]}"

                table.add_row(
                    f"{chunk.index + 1}/{chunk.total_chunks}",
                    chunk.id,
                    f"~{chunk.metadata.estimated_tokens:,}",
                    range_str,
                )

            if len(chunks) > 20:
                table.add_row("...", f"+{len(chunks) - 20} more", "", "")

            console.print(table)
            console.print(f"\n[dim]Use --get N to view a specific chunk's content[/dim]")

            if output:
                out_dir = Path(output)
                out_dir.mkdir(parents=True, exist_ok=True)

                for chunk in chunks:
                    chunk_file = out_dir / f"chunk_{chunk.index}.json"
                    chunk_file.write_text(chunk.to_json())

                console.print(f"[green]Saved to {output}/[/green]")

        finally:
            await connector.close()

    run_async(run())


@app.command()
def extract(
    text: str = typer.Argument(..., help="Text to extract triplets from"),
    gliner: bool = typer.Option(True, "--gliner/--no-gliner", help="Use GliNER for NER"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (JSON)"),
):
    """Extract triplets (relationships) from text.

    Examples:
        cgc extract "Apple was founded by Steve Jobs in California"
        cgc extract "The user John placed order #123" --no-gliner
    """
    from cgc.discovery.extractor import extract_triplets

    triplets = extract_triplets(text, use_gliner=gliner)

    if not triplets:
        console.print("[yellow]No triplets found[/yellow]")
        return

    if output:
        data = [{"subject": t.subject, "predicate": t.predicate, "object": t.object, "confidence": t.confidence} for t in triplets]
        Path(output).write_text(json.dumps(data, indent=2))
        console.print(f"[green]Saved {len(triplets)} triplets to {output}[/green]")
    else:
        table = Table(title="Extracted Triplets")
        table.add_column("Subject")
        table.add_column("Predicate")
        table.add_column("Object")
        table.add_column("Confidence")

        for t in triplets:
            table.add_row(
                t.subject,
                t.predicate,
                t.object,
                f"{t.confidence:.2f}",
            )

        console.print(table)


@app.command()
def health(
    source_type: str = typer.Argument(..., help="Source type"),
    connection: str = typer.Argument(..., help="Connection string or path"),
    source_id: str = typer.Option("default", "--id", "-i", help="Source ID"),
):
    """Check health of a data source.

    Examples:
        cgc health postgres "postgresql://localhost/mydb"
        cgc health qdrant "http://localhost:6333"
    """

    async def run():
        connector = Connector()

        if source_type in ("postgres", "mysql"):
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
        else:
            console.print(f"[red]Unknown source type: {source_type}[/red]")
            raise typer.Exit(1)

        try:
            status = await connector.health_check_source(source_id)

            if status.healthy:
                console.print(f"[green]✓ Healthy[/green] ({status.latency_ms:.1f}ms)")
            else:
                console.print(f"[red]✗ Unhealthy[/red]: {status.message}")
                raise typer.Exit(1)

        finally:
            await connector.close()

    run_async(run())


@app.command()
def version():
    """Show version information."""
    try:
        from cgc import __version__
        ver = __version__
    except ImportError:
        ver = "0.1.0"

    console.print(f"[bold]Context Graph Connector[/bold] v{ver}")
    console.print()
    console.print("Commands:")
    console.print("  cgc serve          Start HTTP API server")
    console.print("  cgc serve --secure Start secure API server")
    console.print("  cgc mcp            Start MCP server (for Claude)")
    console.print("  cgc discover       Discover data source schema")
    console.print("  cgc sample         Sample data from entity")
    console.print("  cgc sql            Execute SQL query")
    console.print("  cgc chunk          Chunk data for AI processing")
    console.print("  cgc extract        Extract triplets from text")
    console.print("  cgc health         Check data source health")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
