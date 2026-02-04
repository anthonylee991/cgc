# CGC - Windows Installation Guide

> **Context Graph Connector**
> Programmatic data access layer for LLM agents — navigate context, don't memorize it

---

## What's Included

This folder contains:

```
cgc-windows/
├── cgc.exe           - CLI tool (connect, discover, query, search, chunk, graph)
├── cgc_mcp.exe       - MCP server (for Claude/Cursor/Cline)
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

---

## Quick Start

### Step 1: Open your platform folder

Open PowerShell or Command Prompt and navigate to the CGC folder:

```powershell
cd C:\path\to\cgc-windows
```

Replace `C:\path\to\` with wherever you extracted the bundle (e.g., `C:\Users\YourName\Downloads\`).

### Step 2: Verify it works

**PowerShell:**
```powershell
.\cgc.exe --help
```

**Command Prompt:**
```cmd
cgc.exe --help
```

You should see the CGC CLI help output with available commands.

---

## Usage Options

### Option 1: CLI (Terminal)

Connect to data sources and query them directly:

**PowerShell (use `.\` prefix):**
```powershell
# Connect a PostgreSQL database
.\cgc.exe add mydb postgres "postgresql://user:pass@localhost:5432/dbname"

# Connect a SQLite database
.\cgc.exe add local sqlite "C:\path\to\database.db"

# Connect a filesystem directory
.\cgc.exe add docs filesystem "C:\path\to\documents"

# Connect MongoDB
.\cgc.exe add mongo mongodb "mongodb://localhost:27017/dbname"

# Discover schema
.\cgc.exe discover mydb

# Sample data from a table
.\cgc.exe sample mydb users --n 5

# Execute SQL queries
.\cgc.exe sql mydb "SELECT * FROM users LIMIT 10"

# Search for data
.\cgc.exe search mydb users name "John"

# Chunk data for LLM processing
.\cgc.exe chunk mydb users --strategy rows:100

# View relationship graph
.\cgc.exe graph

# List all connected sources
.\cgc.exe list

# Remove a source
.\cgc.exe remove mydb
```

### Option 2: API Server

Start the REST API server for programmatic access:

```powershell
.\cgc.exe serve
```

This will:
- Start the CGC API server on `http://localhost:8000`
- Open your browser to the API docs (Swagger UI)
- Keep running until you press `Ctrl+C`

Or start manually with options:

```powershell
.\cgc.exe serve --port 8000
```

For authenticated access:

```powershell
.\cgc.exe serve-secure --port 8000
```

See `documentation\API.md` for all endpoints.

### Option 3: MCP Integration (Claude Desktop / Claude Code / Cursor)

The MCP server gives AI assistants direct access to your connected data sources.

**Important:** All paths in MCP configs must be absolute.

#### Claude Desktop

1. Open your config file:
   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```
   (You can paste this path into File Explorer to navigate there)

2. Add the CGC MCP server:
   ```json
   {
     "mcpServers": {
       "cgc": {
         "command": "C:\\Users\\YourUsername\\cgc-windows\\cgc_mcp.exe"
       }
     }
   }
   ```
   Replace `C:\\Users\\YourUsername\\` with your actual path.
   Note the double backslashes (`\\`) in JSON.

3. Restart Claude Desktop.

#### Claude Code

Add to your global settings (`%USERPROFILE%\.claude\settings.json`) or your project's `.claude\settings.json`:

```json
{
  "mcpServers": {
    "cgc": {
      "command": "C:\\Users\\YourUsername\\cgc-windows\\cgc_mcp.exe"
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
%USERPROFILE%\.cgc\sessions\
```

No data is ever sent to external servers. CGC runs entirely locally.

---

## Troubleshooting

### "Windows protected your PC" (SmartScreen)

CGC is unsigned. Windows may show a SmartScreen warning on first run:
1. Click "More info"
2. Click "Run anyway"

This only needs to be done once.

### Connection refused / database errors

Make sure your data source is running and accessible. Test connectivity:
```powershell
# PostgreSQL (if psql is installed)
psql "postgresql://user:pass@localhost:5432/dbname"

# MongoDB (if mongosh is installed)
mongosh "mongodb://localhost:27017/dbname"
```

### MCP server not connecting

- Use the **absolute path** to `cgc_mcp.exe` in your config
- Use **double backslashes** (`\\`) in JSON paths
- Restart Claude Desktop / Cursor completely (quit and reopen)
- Check logs: run `.\cgc_mcp.exe` directly in PowerShell to see any error output

### Port 8000 already in use

```powershell
# Find what's using the port
netstat -ano | findstr :8000

# Kill the process (replace PID with the number from above)
taskkill /PID <PID> /F
```

### pip install alternative

If you prefer Python package installation over binaries:
```powershell
pip install context-graph-connector
cgc --help
```

---

## Documentation

- **CLI Reference:** `documentation\CLI.md`
- **REST API:** `documentation\API.md`
- **MCP Guide:** `documentation\MCP.md`
- **Architecture:** `documentation\TECHNICAL.md`
- **Security:** `documentation\SECURITY.md`
