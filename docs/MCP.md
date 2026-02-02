# CGC MCP Reference

This guide explains how to connect CGC to Claude Desktop, Claude Code, or other AI assistants that support the Model Context Protocol (MCP).

---

## Table of Contents

- [What is MCP?](#what-is-mcp)
- [Setup for Claude Desktop](#setup-for-claude-desktop)
- [Setup for Claude Code (VS Code)](#setup-for-claude-code-vs-code)
- [Available Tools](#available-tools)
- [Free vs Pro Tools](#free-vs-pro-tools)
- [Example Conversations](#example-conversations)
- [Session Tracking](#session-tracking)
- [Troubleshooting](#troubleshooting)

---

## What is MCP?

MCP (Model Context Protocol) is a way for AI assistants to use external tools. Think of it as giving Claude "superpowers" - the ability to connect to your databases, read your files, and work with your data directly.

**Without MCP:**
- You copy data and paste it into the chat
- Claude can only see what you show it
- You manually run queries and share results

**With MCP + CGC:**
- Claude can explore your databases directly
- Claude asks for data when it needs it
- You have a natural conversation about your data

---

## Setup for Claude Desktop

Claude Desktop is the standalone application for Windows, Mac, and Linux.

### Step 1: Locate the Config File

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```
Usually: `C:\Users\YourName\AppData\Roaming\Claude\claude_desktop_config.json`

**Mac:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### Step 2: Edit the Config File

Open the file in a text editor (like Notepad). If the file doesn't exist, create it.

**Using the CGC MCP Executable (Recommended):**

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

Replace `C:\\path\\to\\cgc_mcp.exe` with the actual path to your executable.

> **Note:** The MCP server uses a separate, lightweight executable (`cgc_mcp.exe`) optimized for fast startup. It provides all context extension tools (discover, sample, chunk, search, SQL) without requiring ML libraries. Graph extraction is available via the CLI or API.

**Example (Windows):**
```json
{
  "mcpServers": {
    "cgc": {
      "command": "C:\\Users\\John\\Tools\\cgc_mcp.exe",
      "args": []
    }
  }
}
```

**Using Python (if installed via pip):**

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

### Step 3: Restart Claude Desktop

Close and reopen Claude Desktop for the changes to take effect.

### Step 4: Verify Connection

Ask Claude:
```
Can you see what CGC tools are available?
```

Claude should respond with a list of available tools like `cgc_add_source`, `cgc_discover`, etc.

---

## Setup for Claude Code (VS Code)

Claude Code is the VS Code extension for using Claude in your editor.

### Step 1: Locate the MCP Settings

The settings file is located at:

**Windows:**
```
C:\Users\YourName\.claude\settings.json
```

**Mac/Linux:**
```
~/.claude/settings.json
```

### Step 2: Edit the Settings

**Using the Executable:**
```json
{
  "mcpServers": {
    "cgc": {
      "command": "C:\\Users\\John\\Tools\\cgc_mcp.exe",
      "args": []
    }
  }
}
```

**Using Python:**
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

### Step 3: Restart VS Code

Close and reopen VS Code for the changes to take effect.

---

## Available Tools

Once connected, Claude has access to these tools:

### Data Source Management

| Tool | What it does |
|------|--------------|
| `cgc_add_source` | Connect a database, folder, or vector store |
| `cgc_remove_source` | Disconnect a data source |
| `cgc_list_sources` | See all connected sources |

### Data Exploration

| Tool | What it does |
|------|--------------|
| `cgc_discover` | See tables, columns, files in a source |
| `cgc_discover_all` | Discover schemas for all connected sources |
| `cgc_sample` | Get sample rows from a table or file |
| `cgc_sql` | Run SQL queries on databases |
| `cgc_search` | Search for text patterns |

### Data Processing

| Tool | What it does |
|------|--------------|
| `cgc_chunk` | Break large data into smaller pieces |

### Context and Relationships

| Tool | What it does |
|------|--------------|
| `cgc_summary` | Get a compact overview of all data |
| `cgc_graph` | See how tables/entities relate to each other |
| `cgc_find_related` | Find connected records across sources |

### Vector Search (for vector databases)

| Tool | What it does |
|------|--------------|
| `cgc_vector_search` | Find similar items using AI embeddings |

### Session Management

| Tool | What it does |
|------|--------------|
| `cgc_session_new` | Start tracking a work session |
| `cgc_session_log` | Log important decisions or files |
| `cgc_session_summary` | Get a summary of what was done |
| `cgc_session_save` | Save session for later |
| `cgc_session_load` | Resume a previous session |
| `cgc_session_stats` | Check session health and size usage |
| `cgc_session_list` | List all sessions (including archived) |

---

## Free vs Pro Tools

All MCP tools are available on the free tier. The MCP server provides context extension -- connecting to data, exploring schemas, sampling, chunking, searching, and running SQL queries. These features work without a license.

**Graph extraction** (converting text into knowledge graph triplets) is available via the CLI (`cgc extract`, `cgc extract-file`) or the HTTP API (`POST /extract/*`). Extraction requires an active trial or Pro license.

| MCP (all tiers) | CLI/API (Trial/Pro only) |
|------------------|--------------------------|
| Connect to data sources | Extract triplets from text |
| Discover schemas | Extract from files (CSV, Excel, JSON) |
| Sample data | Chunk-then-extract workflow |
| Run SQL queries | Domain detection |
| Search text patterns | Industry pack routing |
| Chunk large files | |
| Find relationships | |
| Session tracking | |

---

## Example Conversations

Here are examples of how to interact with Claude once CGC is connected.

### Example 1: Exploring a Database

**You:** Connect to my PostgreSQL database at localhost. The username is admin, password is secret123, and the database is called company_db.

**Claude:** I'll connect to your PostgreSQL database.

*[Uses cgc_add_source tool]*

Connected successfully! The database is now available as "company_db".

**You:** What tables are in there?

**Claude:** Let me discover the schema.

*[Uses cgc_discover tool]*

I found 5 tables:
- **users** (1,523 rows) - id, email, name, created_at
- **orders** (8,291 rows) - id, user_id, total, status, created_at
- **products** (156 rows) - id, name, price, category
- **categories** (12 rows) - id, name
- **reviews** (2,847 rows) - id, user_id, product_id, rating, text

**You:** Show me some sample orders

**Claude:** *[Uses cgc_sample tool]*

Here are 5 sample orders:

| id | user_id | total | status | created_at |
|----|---------|-------|--------|------------|
| 1 | 42 | $150.00 | completed | 2024-01-15 |
| 2 | 17 | $89.99 | pending | 2024-01-15 |
| ... | ... | ... | ... | ... |

**You:** How many orders are pending?

**Claude:** *[Uses cgc_sql tool]*

There are 234 pending orders with a total value of $18,456.50.

---

### Example 2: Analyzing Documents

**You:** Connect to my reports folder at C:\Users\John\Documents\Reports

**Claude:** *[Uses cgc_add_source tool]*

Connected to your Reports folder. I found 23 files including PDFs, Word documents, and Excel spreadsheets.

**You:** I need to analyze the Q4 financial report. It's a big PDF.

**Claude:** *[Uses cgc_discover tool to find the file]*
*[Uses cgc_chunk tool to break it into pieces]*

I found "Q4_Financial_Report.pdf" (743 pages). I've broken it into 61 chunks of about 2,000 tokens each for analysis.

Would you like me to:
1. Summarize the entire report (I'll read through each chunk)
2. Look for specific information
3. Extract key financial figures

**You:** Summarize the executive summary section

**Claude:** *[Uses cgc_chunk with sections strategy]*

Here's the executive summary:

The Q4 results exceeded expectations with revenue of $12.4M (+15% YoY)...

---

### Example 3: Finding Relationships

**You:** Find all data related to user 42

**Claude:** *[Uses cgc_find_related tool]*

Here's everything related to user 42 (John Smith):

**User Profile:**
- Email: john@example.com
- Joined: January 15, 2024

**Orders (12 total):**
- Order #1001: $150.00 (completed)
- Order #1089: $275.50 (completed)
- Order #1234: $89.99 (pending)
- ...

**Reviews (3 total):**
- Product: "Wireless Headphones" - 5 stars
- Product: "USB Cable" - 4 stars
- Product: "Phone Case" - 3 stars

---

### Example 4: Vector Search

**You:** Search my knowledge base for information about refund policies

**Claude:** *[Uses cgc_vector_search tool]*

I found 5 relevant documents:

1. **Refund_Policy_2024.pdf** (98% match)
   - Covers standard refund procedures

2. **Customer_Service_FAQ.docx** (92% match)
   - Section on handling refund requests

3. **Training_Manual.pdf** (85% match)
   - Chapter 7: Processing Returns

Would you like me to read any of these in detail?

---

## Session Tracking

Sessions help Claude remember what was done, even if the conversation gets too long.

### Starting a Session

**You:** Let's start a new session called "database-audit"

**Claude:** *[Uses cgc_session_new tool]*

Started session "database-audit". I'll track all important decisions and files we work with.

### During Work

As you work, Claude automatically logs:
- Files created or modified
- Important decisions made
- Data sources used
- Key findings

### Getting a Summary

**You:** What have we done so far in this session?

**Claude:** *[Uses cgc_session_summary tool]*

**Session: database-audit**
Started: 2024-01-15 10:30 AM

**Files Modified:**
- Created: audit_report.md
- Modified: queries.sql

**Decisions Made:**
- Chose to focus on orders table first
- Decided to exclude archived records

**Key Findings:**
- Found 234 pending orders
- Identified 3 duplicate customer records

### Saving for Later

**You:** Save this session so we can continue later

**Claude:** *[Uses cgc_session_save tool]*

Session saved! You can resume it anytime by asking me to load the "database-audit" session.

### Checking Session Health

**You:** How big is our current session?

**Claude:** *[Uses cgc_session_stats tool]*

```
Session Statistics: database-audit

Entries:
  Work items: 45/500
  Decisions:  12/100
  Notes:      8/200
  TODOs:      3/100
  Context:    5/50

Size:
  Current:    125,340 bytes
  Limit:      5,000,000 bytes
  Usage:      2.5%

Status: OK Healthy
```

### Session Safeguards

CGC includes automatic safeguards to prevent sessions from growing too large during long agent runs:

**Size Limits:**
| Item | Limit | Description |
|------|-------|-------------|
| Work items | 500 max | Files created/modified/analyzed |
| Decisions | 100 max | Logged decisions |
| Notes | 200 max | General notes |
| TODOs | 100 max | Task items |
| Context keys | 50 max | Arbitrary key-value storage |
| Entry text | 10KB max | Individual description/note length |
| Session size | 5MB max | Total session file size |

**Auto-Pruning:**
When limits are exceeded, older entries are automatically removed to make room for new ones. The most recent entries are always preserved.

**Session Rotation:**
When a session reaches the 5MB size limit:
1. The current session is archived (compressed)
2. A new continuation session is created
3. TODOs and recent context are carried forward
4. A note is added explaining the rotation

**Compression:**
All sessions are automatically saved with gzip compression, typically reducing file size by 5-10x.

### Listing All Sessions

**You:** What sessions do I have saved?

**Claude:** *[Uses cgc_session_list tool]*

```
Available Sessions:

[Z] 20260124_103042 - 12.5KB - 2026-01-24T10:30:42
[Z] 20260123_142215 - 8.2KB - 2026-01-23T14:22:15
[Z] 20260122_091530 - 45.1KB - 2026-01-22T09:15:30

Archived Sessions:

[A] 20260120_080000 - 1.2MB - 2026-01-20T08:00:00
```

---

## Troubleshooting

### "CGC tools not available"

Claude doesn't see the CGC tools.

**Solutions:**

1. **Check the config file path**
   - Make sure you're editing the correct file
   - Windows Claude Desktop: `%APPDATA%\Claude\claude_desktop_config.json`
   - Claude Code: `~/.claude/settings.json`

2. **Check the executable path**
   - Use the full path to cgc_mcp.exe
   - Use double backslashes in Windows paths: `C:\\Users\\...`
   - Args should be empty: `[]`

3. **Restart the application**
   - Close completely (check system tray)
   - Reopen

4. **Check for JSON errors**
   - Make sure your config file is valid JSON
   - Watch for missing commas or brackets

### "Connection failed" or "Source not found"

Can't connect to a database or file.

**Solutions:**

1. **For databases:**
   - Is the database server running?
   - Is the connection string correct?
   - Can you connect with another tool?

2. **For files:**
   - Does the path exist?
   - Do you have read permissions?
   - Is the path spelled correctly?

### "Tool execution failed"

A tool runs but returns an error.

**Solutions:**

1. **Check the error message**
   - Claude will show what went wrong
   - Often it's a typo in a name or path

2. **Try a simpler request**
   - Start with `cgc_list_sources` to verify connection
   - Then try `cgc_discover` to see available data

3. **Check data source**
   - Is the source still accessible?
   - Has anything changed since you connected?

### Claude Doesn't Use CGC

You mention data but Claude doesn't use the tools.

**Solutions:**

1. **Be explicit**
   - Say "Use CGC to connect to..." instead of just "connect to..."
   - Say "Query the database" instead of "get the data"

2. **Check tools are available**
   - Ask "What CGC tools do you have access to?"
   - If none, there's a configuration issue

3. **Restart the conversation**
   - Sometimes starting fresh helps

### Performance Issues

CGC seems slow.

**Solutions:**

1. **For large files:**
   - Use chunking instead of loading everything
   - Ask for samples instead of full data

2. **For databases:**
   - Add LIMIT to SQL queries
   - Index frequently-queried columns

3. **For vector search:**
   - Reduce the number of results (top_k)
   - Use filters to narrow the search

---

## Advanced Configuration

### Adding Multiple MCP Servers

You can use CGC alongside other MCP tools:

```json
{
  "mcpServers": {
    "cgc": {
      "command": "C:\\Tools\\cgc_mcp.exe",
      "args": []
    },
    "another-tool": {
      "command": "C:\\Tools\\other_mcp.exe",
      "args": []
    }
  }
}
```

### Environment Variables

Pass environment variables to CGC:

```json
{
  "mcpServers": {
    "cgc": {
      "command": "C:\\Tools\\cgc_mcp.exe",
      "args": [],
      "env": {
        "CGC_LOG_LEVEL": "debug"
      }
    }
  }
}
```

---

## Next Steps

- [API Reference](API.md) - Use CGC with automation tools
- [CLI Reference](CLI.md) - Command-line usage
- [Security Guide](SECURITY.md) - Securing your CGC installation
