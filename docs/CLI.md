# CGC Command Line Reference

This guide explains all the commands you can run from your terminal or command prompt.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Quick Reference](#quick-reference)
- [Commands in Detail](#commands-in-detail)
  - [cgc serve](#cgc-serve)
  - [cgc mcp](#cgc-mcp)
  - [cgc discover](#cgc-discover)
  - [cgc sample](#cgc-sample)
  - [cgc sql](#cgc-sql)
  - [cgc chunk](#cgc-chunk)
  - [cgc extract](#cgc-extract)
  - [cgc health](#cgc-health)
  - [cgc version](#cgc-version)
- [Tips and Tricks](#tips-and-tricks)

---

## Getting Started

### Opening the Command Line

**Windows:**
1. Press `Windows key + R`
2. Type `cmd` and press Enter
3. Or search for "Command Prompt" in the Start menu

**Mac:**
1. Press `Cmd + Space`
2. Type `Terminal` and press Enter

**Linux:**
1. Press `Ctrl + Alt + T`
2. Or find Terminal in your applications

### Running Commands

After installation, type `cgc` followed by a command:

**Windows PowerShell (from the cgc.exe folder):**
```
.\cgc.exe --help
```

**Windows Command Prompt (from the cgc.exe folder):**
```
cgc.exe --help
```

**Pip installation (any platform):**
```
cgc --help
```

This shows all available commands.

**Note:** In PowerShell, you must use `.\` before the executable name when running from the current folder. This is a Windows security feature.

---

## Quick Reference

| Command | What it does | Example |
|---------|--------------|---------|
| `cgc serve` | Start the API server | `cgc serve` |
| `cgc serve --secure` | Start secure API server | `cgc serve --secure` |
| `cgc mcp` | Start the MCP server | `cgc mcp` |
| `cgc discover` | See what's in a source | `cgc discover mydb` |
| `cgc sample` | View sample data | `cgc sample mydb users 5` |
| `cgc sql` | Run a SQL query | `cgc sql mydb "SELECT * FROM users"` |
| `cgc chunk` | Break data into pieces | `cgc chunk mydb report.pdf` |
| `cgc extract` | Extract relationships | `cgc extract "John works at Apple"` |
| `cgc health` | Check connection | `cgc health mydb` |
| `cgc version` | Show version | `cgc version` |

---

## Commands in Detail

### cgc serve

Start the HTTP API server. This is how other tools (n8n, Make.com, etc.) connect to CGC.

**Format:**
```
cgc serve [options]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--secure` or `-s` | Enable security features (API keys, rate limiting) | Off |
| `--host` or `-h` | IP address to listen on | `127.0.0.1` |
| `--port` or `-p` | Port number | `8420` |

**Examples:**

Start the basic server (for local testing):
```
cgc serve
```

Start the secure server (for production or remote access):
```
cgc serve --secure
```

Start on a specific port:
```
cgc serve --port 9000
```

Allow connections from other machines:
```
cgc serve --host 0.0.0.0
```

Combine options:
```
cgc serve --secure --host 0.0.0.0 --port 9000
```

**Output:**
```
Starting CGC API server on 127.0.0.1:8420
API docs available at http://localhost:8420/docs
```

**Notes:**
- The regular server (no `--secure`) has no authentication - use only for local testing
- The secure server requires API keys and includes rate limiting
- API documentation is available at `http://localhost:8420/docs`

---

### cgc mcp

Start the MCP (Model Context Protocol) server for Claude integration.

**Format:**
```
cgc mcp
```

This command has no options - it starts the MCP server in stdio mode for communication with Claude Desktop or Claude Code.

**Example:**
```
cgc mcp
```

**Notes:**
- This command is typically not run manually
- Configure it in Claude Desktop or Claude Code settings
- See [MCP Reference](MCP.md) for setup instructions

---

### cgc discover

See what's inside a data source.

**Format:**
```
cgc discover <source_name>
```

**Arguments:**
- `source_name` - The name you gave when adding the source via the API

**What it shows:**

For databases:
- Table names
- Column names and types
- Number of rows
- Primary keys and relationships

For file folders:
- File names
- File types
- File sizes
- Folder structure

**Example:**
```
cgc discover mydb
```

**Output:**
```
Source: mydb (postgres)
Tables: 4

  users
    - id (integer, primary key)
    - email (varchar, not null)
    - name (varchar)
    - created_at (timestamp)
    Rows: 1,523

  orders
    - id (integer, primary key)
    - user_id (integer) -> users.id
    - total (decimal)
    - status (varchar)
    Rows: 8,291

  ...
```

**Options:**
- `--refresh` - Force a fresh scan (ignore cached data)

```
cgc discover mydb --refresh
```

---

### cgc sample

View sample rows from a table or file.

**Format:**
```
cgc sample <source_name> <entity> [count]
```

**Arguments:**
- `source_name` - The name of your data source
- `entity` - Table name (for databases) or file name (for filesystems)
- `count` (optional) - How many samples to show (default: 5)

**Examples:**

Show 5 sample users:
```
cgc sample mydb users
```

Show 10 sample orders:
```
cgc sample mydb orders 10
```

Show sample from a file:
```
cgc sample documents report.pdf 3
```

**Output:**
```
Samples from mydb.users (5 of 1,523 rows):

┌────┬─────────────────────┬────────┬─────────────────────┐
│ id │ email               │ name   │ created_at          │
├────┼─────────────────────┼────────┼─────────────────────┤
│ 1  │ john@example.com    │ John   │ 2024-01-15 09:30:00 │
│ 2  │ jane@example.com    │ Jane   │ 2024-01-16 14:22:00 │
│ 3  │ bob@example.com     │ Bob    │ 2024-01-17 11:45:00 │
│ 4  │ alice@example.com   │ Alice  │ 2024-01-18 16:00:00 │
│ 5  │ charlie@example.com │ Charlie│ 2024-01-19 08:15:00 │
└────┴─────────────────────┴────────┴─────────────────────┘
```

---

### cgc sql

Run a SQL query on a database.

**Format:**
```
cgc sql <source_name> "<query>"
```

**Arguments:**
- `source_name` - The name of your database source
- `query` - Your SQL query (in quotes)

**Examples:**

Get all users:
```
cgc sql mydb "SELECT * FROM users"
```

Filter with conditions:
```
cgc sql mydb "SELECT * FROM orders WHERE total > 100"
```

Join tables:
```
cgc sql mydb "SELECT users.name, orders.total FROM users JOIN orders ON users.id = orders.user_id"
```

Count records:
```
cgc sql mydb "SELECT COUNT(*) as total FROM orders"
```

**Important Notes:**
- Always put your query in quotes
- Only SELECT queries are allowed (for safety)
- Results are limited to 10,000 rows by default

**Output:**
```
Query executed in 45ms
Rows returned: 3

┌─────────┬────────┐
│ name    │ total  │
├─────────┼────────┤
│ John    │ 150.00 │
│ Jane    │ 275.50 │
│ Bob     │ 89.99  │
└─────────┴────────┘
```

---

### cgc chunk

Break large data into smaller pieces that AI can process.

**Format:**
```
cgc chunk <source_name> <entity> [options]
```

**Arguments:**
- `source_name` - The name of your data source
- `entity` - Table or file name to chunk

**Options:**
- `--strategy` - How to split the data (see below)

**Strategy Options:**

| Strategy | Best For | Example |
|----------|----------|---------|
| `rows:N` | Database tables | `--strategy rows:500` |
| `tokens:N` | AI processing | `--strategy tokens:2000` |
| `sections` | Documents with headers | `--strategy sections` |

**Examples:**

Chunk by rows (good for databases):
```
cgc chunk mydb large_table --strategy rows:1000
```

Chunk by tokens (good for AI):
```
cgc chunk documents report.pdf --strategy tokens:2000
```

Chunk by sections (good for structured documents):
```
cgc chunk documents manual.md --strategy sections
```

**Output:**
```
Chunking: documents/report.pdf
Strategy: tokens:2000

Created 15 chunks:
  Chunk 0: ~1,985 tokens (pages 1-4)
  Chunk 1: ~2,010 tokens (pages 5-8)
  Chunk 2: ~1,920 tokens (pages 9-12)
  ...
  Chunk 14: ~1,540 tokens (pages 57-60)

Use 'cgc chunk mydb report.pdf --get 0' to view a specific chunk.
```

**View a specific chunk:**
```
cgc chunk documents report.pdf --get 5
```

---

### cgc extract

Extract relationships (subject-predicate-object) from text.

**Format:**
```
cgc extract "<text>" [options]
```

**Arguments:**
- `text` - The text to analyze (in quotes)

**Options:**
- `--gliner` - Use AI-powered extraction (more accurate, slower)

**Examples:**

Basic extraction:
```
cgc extract "Apple was founded by Steve Jobs in Cupertino, California."
```

With AI enhancement:
```
cgc extract "Apple was founded by Steve Jobs in Cupertino, California." --gliner
```

**Output:**
```
Extracted 3 relationships:

┌──────────────┬─────────────────┬─────────────────────┬────────────┐
│ Subject      │ Predicate       │ Object              │ Confidence │
├──────────────┼─────────────────┼─────────────────────┼────────────┤
│ Apple        │ was founded by  │ Steve Jobs          │ 0.95       │
│ Apple        │ founded in      │ Cupertino           │ 0.87       │
│ Cupertino    │ located in      │ California          │ 0.82       │
└──────────────┴─────────────────┴─────────────────────┴────────────┘
```

**Use Cases:**
- Building knowledge graphs
- Understanding document content
- Finding connections in text

---

### cgc health

Check if a data source is accessible.

**Format:**
```
cgc health <source_name>
```

**Arguments:**
- `source_name` - The name of your data source

**Example:**
```
cgc health mydb
```

**Output (Success):**
```
✓ Source 'mydb' is healthy
  Type: postgres
  Status: Connected
  Response time: 12ms
```

**Output (Failure):**
```
✗ Source 'mydb' is not accessible
  Error: Connection refused
  Check: Is the database server running?
```

---

### cgc version

Display the current version of CGC.

**Format:**
```
cgc version
```

**Example:**
```
cgc version
```

**Output:**
```
CGC (Context Graph Connector) v1.0.0
```

---

## Tips and Tricks

### Using Environment Variables

Set defaults using environment variables:

**Windows (Command Prompt):**
```
set CGC_BIND_HOST=0.0.0.0
set CGC_BIND_PORT=9000
cgc serve
```

**Windows (PowerShell):**
```
$env:CGC_BIND_HOST = "0.0.0.0"
$env:CGC_BIND_PORT = "9000"
cgc serve
```

**Mac/Linux:**
```
export CGC_BIND_HOST=0.0.0.0
export CGC_BIND_PORT=9000
cgc serve
```

### Available Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CGC_REQUIRE_AUTH` | Require API keys | `true` (secure), `false` (regular) |
| `CGC_BIND_HOST` | Server IP address | `127.0.0.1` |
| `CGC_BIND_PORT` | Server port | `8420` |
| `CGC_RATE_LIMIT_REQUESTS` | Requests per window | `100` |
| `CGC_RATE_LIMIT_WINDOW` | Window size (seconds) | `60` |
| `CGC_SQL_MAX_ROWS` | Max rows returned | `10000` |

### Handling Paths with Spaces

Always use quotes around paths that contain spaces:

```
cgc sample "my database" users 5
```

### Output Formats

Some commands support different output formats:

```
cgc discover mydb --format json
cgc sample mydb users --format csv
```

### Quiet Mode

Suppress extra output:

```
cgc sample mydb users --quiet
```

---

## Common Issues

### "Command not found"

The `cgc` command isn't recognized.

**Solutions:**
1. Make sure CGC is installed: `pip install context-graph-connector`
2. If using the executable, use the full path: `C:\path\to\cgc.exe`
3. Try closing and reopening your terminal

### "Connection refused"

Can't connect to a database.

**Solutions:**
1. Is the database server running?
2. Check the connection string for typos
3. Make sure the port is correct
4. Check firewall settings

### "Permission denied"

Can't access a file or folder.

**Solutions:**
1. Make sure the file/folder exists
2. Check you have read permissions
3. Try running as administrator (Windows) or with sudo (Mac/Linux)

### "Source not found"

Trying to use a source that doesn't exist.

**Solutions:**
1. List your sources via the API: `GET /sources`
2. Add the source first via the API: `POST /sources`
3. See [API Reference](API.md) for details

---

## Next Steps

- [API Reference](API.md) - Use CGC with n8n, Make.com, or any HTTP client
- [MCP Reference](MCP.md) - Connect CGC to Claude Desktop
- [Technical Overview](TECHNICAL.md) - Learn how CGC works
