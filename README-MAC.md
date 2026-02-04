# CGC - Mac Installation Guide

> **Context Graph Connector**
> Programmatic data access layer for LLM agents — navigate context, don't memorize it

---

## What's Included

This folder contains:

```
cgc-mac-aarch64/  (or cgc-mac-x86_64/)
├── cgc               - CLI tool (connect, discover, query, search, chunk, graph)
├── cgc_mcp           - MCP server (for Claude/Cursor/Cline)
├── launch_cgc.sh     - API server launcher (starts server + opens browser)
├── README.md         - This file
└── documentation/
    ├── CLI.md        - CLI command reference
    ├── API.md        - REST API endpoints
    ├── MCP.md        - MCP integration guide
    ├── TECHNICAL.md  - Architecture overview
    ├── SECURITY.md   - Security documentation
    ├── LICENSE
    └── THIRD_PARTY_NOTICES.md
```

**Which download do I need?**
- **cgc-mac-aarch64.zip** — Apple Silicon (M1, M2, M3, M4)
- **cgc-mac-x86_64.zip** — Intel Macs

Not sure? Run `uname -m` in Terminal. If it says `arm64`, use aarch64. If it says `x86_64`, use x86_64.

---

## Quick Start

### Step 1: Open your platform folder

Open Terminal and navigate to the correct folder for your Mac:

```bash
# Apple Silicon (M1/M2/M3/M4):
cd /path/to/cgc-mac-aarch64

# Intel Mac:
cd /path/to/cgc-mac-x86_64
```

Replace `/path/to/` with wherever you extracted the bundle (e.g., `~/Downloads/`).

### Step 2: Bypass macOS Gatekeeper

CGC is unsigned. macOS will block the binaries on first run. Remove the quarantine attribute:

```bash
xattr -cr .
chmod +x cgc cgc_mcp launch_cgc.sh
```

This only needs to be done once after extracting.

### Step 3: Verify it works

```bash
./cgc --help
```

You should see the CGC CLI help output with available commands.

---

## Usage Options

### Option 1: CLI (Terminal)

Connect to data sources and query them directly:

```bash
# Connect a PostgreSQL database
./cgc add mydb postgres "postgresql://user:pass@localhost:5432/dbname"

# Connect a SQLite database
./cgc add local sqlite "/path/to/database.db"

# Connect a filesystem directory
./cgc add docs filesystem "/path/to/documents"

# Connect MongoDB
./cgc add mongo mongodb "mongodb://localhost:27017/dbname"

# Discover schema
./cgc discover mydb

# Sample data from a table
./cgc sample mydb users --n 5

# Execute SQL queries
./cgc sql mydb "SELECT * FROM users LIMIT 10"

# Search for data
./cgc search mydb users name "John"

# Chunk data for LLM processing
./cgc chunk mydb users --strategy rows:100

# View relationship graph
./cgc graph

# List all connected sources
./cgc list

# Remove a source
./cgc remove mydb
```

### Option 2: API Server

Start the REST API server for programmatic access:

```bash
./launch_cgc.sh
```

This will:
- Start the CGC API server on `http://localhost:8000`
- Open your browser to the API docs (Swagger UI)
- Keep running until you press `Ctrl+C`

Or start manually with options:

```bash
./cgc serve --port 8000
```

For authenticated access:

```bash
./cgc serve-secure --port 8000
```

See `documentation/API.md` for all endpoints.

### Option 3: MCP Integration (Claude Desktop / Claude Code / Cursor)

The MCP server gives AI assistants direct access to your connected data sources.

**Important:** All paths in MCP configs must be absolute. Replace the example paths below with the actual location of your CGC folder.

#### Claude Desktop

1. Open your config file:
   ```bash
   nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

2. Add the CGC MCP server (Apple Silicon example):
   ```json
   {
     "mcpServers": {
       "cgc": {
         "command": "/Users/YourUsername/cgc-mac-aarch64/cgc_mcp"
       }
     }
   }
   ```
   Replace `/Users/YourUsername/` with your actual home directory.
   Use `cgc-mac-x86_64` instead if you're on an Intel Mac.

3. Restart Claude Desktop.

#### Claude Code

Add to `~/.claude/settings.json` or your project's `.claude/settings.json`:

```json
{
  "mcpServers": {
    "cgc": {
      "command": "/Users/YourUsername/cgc-mac-aarch64/cgc_mcp"
    }
  }
}
```

#### Cursor / Cline / Windsurf

Add the same configuration to your IDE's MCP settings. The command is identical.

---

## Where is my data stored?

CGC connects to *external* data sources — it does not store your data itself. Session state is stored locally:

```
~/.cgc/sessions/
```

No data is ever sent to external servers. CGC runs entirely locally.

---

## Troubleshooting

### "cgc" cannot be opened because it is from an unidentified developer

Run the quarantine removal from Step 2:
```bash
cd /path/to/cgc-mac-aarch64
xattr -cr .
chmod +x cgc cgc_mcp launch_cgc.sh
```

### Connection refused / database errors

Make sure your data source is running and accessible. Test connectivity:
```bash
# PostgreSQL
psql "postgresql://user:pass@localhost:5432/dbname"

# MongoDB
mongosh "mongodb://localhost:27017/dbname"
```

### MCP server not connecting

- Use the **absolute path** to `cgc_mcp` in your config (no `~` or `$HOME` — spell out `/Users/YourUsername/...`)
- Verify the binary is executable: `chmod +x cgc_mcp`
- Restart Claude Desktop / Cursor completely (quit and reopen)
- Check logs: run `./cgc_mcp` directly in Terminal to see any error output

### Port 8000 already in use

```bash
lsof -ti:8000 | xargs kill -9
```

### pip install alternative

If you prefer Python package installation over binaries:
```bash
pip install context-graph-connector
cgc --help
```

---

## Documentation

- **CLI Reference:** `documentation/CLI.md`
- **REST API:** `documentation/API.md`
- **MCP Guide:** `documentation/MCP.md`
- **Architecture:** `documentation/TECHNICAL.md`
- **Security:** `documentation/SECURITY.md`
