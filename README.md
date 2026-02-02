# Context Graph Connector (CGC)

**Give your AI assistant the ability to explore and understand your data.**

CGC is a tool that connects AI assistants (like Claude, ChatGPT, or custom agents) to your databases, files, and vector stores. Instead of copying and pasting data into chat windows, your AI can directly explore your data sources, ask questions, and find relationships.

---

## Table of Contents

- [What is CGC?](#what-is-cgc)
- [Who is this for?](#who-is-this-for)
- [Free vs Pro](#free-vs-pro)
- [Getting Started](#getting-started)
  - [Download the Executable](#option-1-download-the-executable-easiest)
  - [Install with pip](#option-2-install-with-pip)
- [Quick Start Guide](#quick-start-guide)
- [Connecting to Your Data](#connecting-to-your-data)
- [Using CGC](#using-cgc)
- [License Management](#license-management)
- [Security](#security)
- [Documentation](#documentation)
- [Support](#support)

---

## What is CGC?

Think of CGC as a "translator" between your AI assistant and your data.

**Without CGC:**
- You manually copy data from your database
- Paste it into a chat window
- Ask your AI to analyze it
- Repeat for every question

**With CGC:**
- Connect your databases once
- Your AI explores the data directly
- Ask unlimited questions
- AI finds relationships across all your data sources

CGC supports:
- **Databases**: PostgreSQL, MySQL, SQLite
- **Files**: PDF, Word, Excel, CSV, JSON, Markdown, code files
- **Vector Databases**: Qdrant, Pinecone, pgvector, MongoDB Atlas

---

## Who is this for?

- **No-code builders** using tools like n8n, Make.com, or Zapier
- **Business users** who want AI assistants to understand their data
- **Developers** building AI-powered applications
- **Anyone** who wants their AI to work with real data instead of copy-paste

---

## Free vs Pro

CGC works out of the box with a generous free tier. Pro unlocks cloud-powered graph extraction.

| Feature | Free | Trial (14 days) | Pro |
|---------|------|-----------------|-----|
| Connect to databases (Postgres, MySQL, SQLite) | Yes | Yes | Yes |
| Connect to files (PDF, Excel, CSV, etc.) | Yes | Yes | Yes |
| Connect to vector databases | Yes | Yes | Yes |
| Schema discovery | Yes | Yes | Yes |
| Data sampling | Yes | Yes | Yes |
| SQL queries | Yes | Yes | Yes |
| Text search | Yes | Yes | Yes |
| Chunking (break large files into pieces) | Yes | Yes | Yes |
| Relationship graph | Yes | Yes | Yes |
| Session tracking | Yes | Yes | Yes |
| MCP integration (Claude Desktop/Code) | Yes | Yes | Yes |
| HTTP API server | Yes | Yes | Yes |
| **Graph extraction (text)** | -- | Yes | Yes |
| **Graph extraction (files)** | -- | Yes | Yes |
| **Structured extraction (CSV, Excel, JSON)** | -- | Yes | Yes |
| **Domain detection (11 industry packs)** | -- | Yes | Yes |
| **Cloud-powered extraction (no ML setup)** | -- | -- | Yes |

**New users get a free 14-day trial** with full access to all extraction features. After the trial, context extension features (connecting, discovering, sampling, chunking, searching) remain free forever.

To purchase a Pro license, visit [https://cgc.dev](https://cgc.dev).

---

## Getting Started

### Option 1: Download the Executable (Easiest)

1. Download from the releases page:
   - `cgc.exe` - Full CLI and API server
   - `cgc_mcp.exe` - Lightweight MCP server for Claude integration
2. Place them somewhere easy to find (like your Desktop or a `tools` folder)
3. You're ready to go!

**Note for Windows users:** When running from the current folder, use `.\cgc.exe` (with the `.\` prefix) in PowerShell, or just `cgc.exe` in Command Prompt.

### Option 2: Install with pip

If you have Python installed (version 3.10 or newer):

```
pip install context-graph-connector
```

To verify installation, open a terminal/command prompt and type:

```
cgc --help
```

You should see a list of available commands.

---

## Quick Start Guide

### Step 1: Start the API Server

The API server lets other tools (like n8n or Make.com) connect to CGC.

**Using the executable (Windows PowerShell):**
```
.\cgc.exe serve
```

**Using the executable (Command Prompt):**
```
cgc.exe serve
```

**Using pip installation:**
```
cgc serve
```

You'll see:
```
Starting CGC API server on 127.0.0.1:8420
API docs available at http://localhost:8420/docs
```

### Step 2: Connect a Data Source

Open a web browser and go to `http://localhost:8420/docs`. This opens the interactive API documentation where you can add data sources.

**To add a SQLite database:**
1. Find the `POST /sources` endpoint
2. Click "Try it out"
3. Enter your source details:
   ```json
   {
     "name": "mydata",
     "type": "sqlite",
     "connection": "C:/path/to/your/database.db"
   }
   ```
4. Click "Execute"

You can also use the CLI tools (like `curl`) or automation platforms to add sources.

### Step 3: Explore Your Data

See what tables exist:
```
cgc discover mydata
```

View sample data from a table:
```
cgc sample mydata customers 5
```

This shows 5 sample rows from the "customers" table.

### Step 4: Extract Relationships (Trial/Pro)

Extract knowledge from text:
```
cgc extract "John Smith is the CEO of Acme Corp in New York."
```

Extract from structured files:
```
cgc extract-file sales_data.csv
```

---

## Connecting to Your Data

CGC can connect to many types of data sources. Use the API (`POST /sources`) to add sources:

### SQLite Database (Local File)

Perfect for small databases or testing.

```json
{
  "name": "mydata",
  "type": "sqlite",
  "connection": "C:/Users/John/Documents/sales.db"
}
```

### PostgreSQL Database

For production databases.

```json
{
  "name": "company",
  "type": "postgres",
  "connection": "postgresql://admin:secret123@localhost:5432/company_db"
}
```

### MySQL Database

```json
{
  "name": "mydata",
  "type": "mysql",
  "connection": "mysql://username:password@hostname:3306/database_name"
}
```

### Local Files and Folders

Connect to a folder containing documents:

```json
{
  "name": "reports",
  "type": "filesystem",
  "connection": "C:/Users/John/Documents/Reports"
}
```

CGC can read:
- PDF files
- Word documents (.docx)
- Excel spreadsheets (.xlsx, .xls)
- CSV files
- JSON files
- Markdown files
- Text files
- Code files

### Vector Databases

For AI-powered semantic search:

**Qdrant:**
```json
{
  "name": "vectors",
  "type": "qdrant",
  "connection": "http://localhost:6333"
}
```

**Pinecone:**
```json
{
  "name": "vectors",
  "type": "pinecone",
  "connection": "your-api-key",
  "options": {"index": "my-index"}
}
```

---

## Using CGC

There are three ways to use CGC:

### 1. Command Line (CLI)

Best for: Quick tasks and testing

```
cgc discover mydata          # See what's in your data
cgc sample mydata users 10   # View 10 sample rows
cgc sql mydata "SELECT * FROM orders WHERE total > 100"
cgc extract "Steve Jobs founded Apple"       # Extract relationships (Trial/Pro)
cgc extract-file data.csv                    # Extract from files (Trial/Pro)
```

[Full CLI Reference](docs/CLI.md)

### 2. HTTP API

Best for: Connecting to automation tools (n8n, Make.com, Zapier)

Start the server:
```
cgc serve
```

Then make requests to `http://localhost:8420`

[Full API Reference](docs/API.md)

### 3. MCP (Model Context Protocol)

Best for: Direct integration with Claude Desktop or Claude Code

Use `cgc_mcp.exe` (a lightweight, fast-starting executable) for MCP integration. Add it to your Claude settings and Claude can use your data directly.

```json
{
  "mcpServers": {
    "cgc": {
      "command": "C:\\path\\to\\cgc_mcp.exe",
      "args": []
    }
  }
}
```

[Full MCP Reference](docs/MCP.md)

---

## License Management

CGC uses a tiered licensing model:

### Checking Your License

```
cgc license
```

This shows your current tier, expiration date (for trials), and license key status.

### Activating a Pro License

After purchasing at [https://cgc.dev](https://cgc.dev), you'll receive a license key (UUID format). Activate it:

```
cgc activate your-license-key-here
```

You'll see:
```
License activated successfully!
Tier: Pro

Graph extraction is now available.
```

### Deactivating a License

To remove your license (for example, to transfer to another machine):

```
cgc deactivate
```

This reverts CGC to the free tier. Your license key can be reactivated on another machine.

### How the Trial Works

When you first use CGC, a 14-day trial starts automatically. During the trial, you have full access to all extraction features. After 14 days:
- Context extension features (connect, discover, sample, chunk, search, SQL) remain free forever
- Graph extraction requires a Pro license

---

## Security

CGC includes security features to protect your data:

- **API Keys**: Require authentication for all requests
- **Rate Limiting**: Prevent abuse with request limits
- **SQL Protection**: Block dangerous queries (DROP, DELETE, etc.)
- **Path Protection**: Prevent access to system files
- **Encrypted License Storage**: License keys are encrypted with AES-256-GCM

### Enabling Security (Recommended for Remote Access)

If you're exposing CGC over the internet (via ngrok, for example), enable security:

**Start the secure server:**
```
cgc serve --secure
```

**Creating your first API key:**

1. Temporarily disable auth:
   ```
   set CGC_REQUIRE_AUTH=false
   cgc serve --secure
   ```

2. Go to `http://localhost:8420/docs`

3. Use the `/admin/api-keys` endpoint to create a key

4. Restart with auth enabled:
   ```
   cgc serve --secure
   ```

**Using the API key:**

Add to all requests:
- Header: `X-API-Key: your-key-here`
- Or query parameter: `?api_key=your-key-here`

[Full Security Guide](docs/SECURITY.md)

---

## Documentation

| Document | Description |
|----------|-------------|
| [API Reference](docs/API.md) | HTTP API endpoints with n8n and Make.com examples |
| [CLI Reference](docs/CLI.md) | Command-line interface commands |
| [MCP Reference](docs/MCP.md) | Model Context Protocol for Claude integration |
| [Security Guide](docs/SECURITY.md) | API keys, rate limiting, and data protection |

---

## Common Questions

### Q: Do I need to know how to code?

**No!** CGC is designed for everyone. The executable works out of the box, and you can use visual tools like n8n or Make.com to build workflows.

### Q: Is my data sent to the cloud?

**Context extension features (discover, sample, chunk, search, SQL) are 100% local.** Your data never leaves your machine. Graph extraction (Pro) sends text to our secure cloud relay for processing, but no data is stored on our servers.

### Q: Can I use this with ChatGPT?

**Yes!** Use the HTTP API to connect CGC to any AI service. See the [API Reference](docs/API.md) for examples.

### Q: What happens when my trial expires?

All context extension features keep working forever. Only graph extraction (the `extract`, `extract-file`, and related commands) requires a Pro license after the trial.

### Q: Can I run extraction locally instead of using the cloud?

**Yes.** Use the `--local` flag with extract commands. This requires installing the ML dependencies separately: `pip install cgc[extraction]`. The cloud relay is the default because it requires no ML setup.

### Q: Can multiple people use the same CGC server?

**Yes!** Start the server once, and multiple users can connect. Use different API keys for each user to track usage and set permissions.

---

## Getting Help

- **Website**: [https://cgc.dev](https://cgc.dev)
- **Issues**: Report bugs at [GitHub Issues](https://github.com/anthonylee991/cgc/issues)
- **Documentation**: See the [docs folder](docs/)

---

## License

Apache 2.0 License - Free for personal and commercial use.
