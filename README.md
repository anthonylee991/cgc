# Context Graph Connector (CGC)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Programmatic data access layer for LLM agents — navigate context, don't memorize it.**

CGC connects AI agents to your databases, files, and vector stores. Instead of stuffing everything into the context window, your agent explores data on-demand: discovering schemas, sampling rows, chunking documents, extracting knowledge graphs, and querying across sources.

---

## Features

- **Connect** to PostgreSQL, MySQL, SQLite, filesystems, Qdrant, Pinecone, pgvector, MongoDB
- **Discover** schemas and structure automatically
- **Sample** data to understand what's in each table or file
- **Chunk** large documents into LLM-friendly pieces
- **Search** across files and databases with pattern matching
- **Extract** knowledge graphs from text and structured data (GLiNER2 unified model + 17 industry packs)
- **Store** extracted triplets in Neo4j, PostgreSQL AGE, or KuzuDB
- **Query** graph sinks with Cypher
- **MCP server** for Claude Desktop / Claude Code / Cursor / Windsurf
- **HTTP API** for integration with any tool or platform
- **CLI** for quick tasks and scripting

## Quick Start

### Prerequisites

- [Python 3.10+](https://www.python.org/downloads/) must be installed on your system

### Install

```bash
pip install context-graph-connector
```

With graph extraction (GLiNER2 — requires ML models):

```bash
pip install context-graph-connector[extraction]
```

With legacy v1 extraction (GliNER + GLiREL + spaCy):

```bash
pip install context-graph-connector[extraction-v1]
```

With everything:

```bash
pip install context-graph-connector[all]
```

### CLI

```bash
# Discover what's in a database
cgc discover sqlite ./mydata.db

# Sample rows from a table
cgc sample sqlite ./mydata.db users --n 10

# Run a SQL query
cgc sql sqlite ./mydata.db "SELECT * FROM orders WHERE total > 100"

# Extract knowledge graph from text
cgc extract "Steve Jobs co-founded Apple with Steve Wozniak in 1976"

# Extract from a file and store in a graph database
cgc extract-file ./report.pdf --sink kuzudb://./my_graph

# Chunk a large PDF for processing
cgc chunk filesystem ./docs report.pdf --strategy tokens:2000

# Start the HTTP API server
cgc serve

# Start the MCP server (for Claude integration)
cgc mcp
```

### MCP Integration (use CGC with AI assistants)

**Claude Code (VS Code / CLI):**
```bash
claude mcp add cgc -s global -- python -m cgc.mcp.server
```

**Claude Desktop / Cursor / Windsurf** — add to your config file ([locations](docs/MCP.md)):
```json
{
  "mcpServers": {
    "cgc": {
      "command": "python",
      "args": ["-m", "cgc.mcp.server"]
    }
  }
}
```

See the [MCP Reference](docs/MCP.md) for step-by-step setup instructions for each editor.

### Python API

```python
from cgc import Connector

connector = Connector()

# Add a data source
from cgc.adapters.sql import SqlAdapter
connector.add_source(SqlAdapter("mydb", "sqlite:///data.db"))

# Discover schema
schema = await connector.discover("mydb")

# Sample data
rows = await connector.sample("mydb", "users", 5)

# Extract triplets
triplets = connector.extract_triplets("Elon Musk founded SpaceX in 2002")
```

## Optional Dependencies

CGC has a minimal core with optional extras for specific integrations:

| Extra | What it adds |
|-------|-------------|
| `extraction` | GLiNER2 — unified NER + relation extraction (default, recommended) |
| `extraction-v1` | GliNER v1, GLiREL, spaCy, sentence-transformers (legacy pipeline) |
| `postgres` | asyncpg, pgvector (PostgreSQL support) |
| `mysql` | aiomysql (MySQL support) |
| `vector` | qdrant-client, pinecone-client, pymongo, motor (vector DB support) |
| `graph` | kuzu (embedded graph database) |
| `all` | Everything above |
| `dev` | pytest, ruff, mypy (development) |

## Architecture

```
cgc/
├── connector.py          # Main interface — Connector class
├── core/                 # Types: Schema, Query, Chunk, Triplet, Graph
├── adapters/
│   ├── sql.py            # PostgreSQL, MySQL, SQLite
│   ├── filesystem.py     # Local files (PDF, DOCX, CSV, etc.)
│   ├── vector/           # Qdrant, Pinecone, pgvector, MongoDB
│   └── graph/            # Neo4j, PostgreSQL AGE, KuzuDB (sinks)
├── discovery/            # Schema inference, relationship detection
│   ├── extractor.py      # Triplet extraction orchestrator (v1/v2 pipeline)
│   ├── gliner2.py        # GLiNER2 unified NER + relation extraction (v2, default)
│   ├── gliner.py         # GliNER v1 NER integration (legacy)
│   ├── glirel.py         # GLiREL relation extraction (legacy)
│   ├── router.py         # Industry pack routing (E5 embeddings, v1 only)
│   ├── industry_packs.py # 17 domain-specific extraction configs
│   └── structured.py     # Hub-and-spoke structured data extraction
├── cli/                  # Typer CLI
├── api/                  # FastAPI HTTP server
├── mcp/                  # Model Context Protocol server
├── session/              # Session tracking
└── security/             # API key auth, rate limiting
```

## Documentation

| Document | Description |
|----------|-------------|
| [API Reference](docs/API.md) | HTTP API endpoints |
| [CLI Reference](docs/CLI.md) | Command-line interface |
| [MCP Reference](docs/MCP.md) | Model Context Protocol for Claude |
| [Security Guide](docs/SECURITY.md) | API keys, rate limiting, data protection |
| [Technical Details](docs/TECHNICAL.md) | Architecture and internals |

## Contributing

Contributions are welcome but this project is maintained on a best-effort basis. PRs may not be reviewed immediately. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
