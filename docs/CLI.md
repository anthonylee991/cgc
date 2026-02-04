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
  - [cgc extract-file](#cgc-extract-file)
  - [cgc detect-domain](#cgc-detect-domain)
  - [cgc list-packs](#cgc-list-packs)
  - [cgc activate](#cgc-activate)
  - [cgc license](#cgc-license)
  - [cgc deactivate](#cgc-deactivate)
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

### Context Extension (Free)

These commands work on all tiers, no license required.

| Command | What it does | Example |
|---------|--------------|---------|
| `cgc serve` | Start the API server | `cgc serve` |
| `cgc serve --secure` | Start secure API server | `cgc serve --secure` |
| `cgc mcp` | Start the MCP server | `cgc mcp` |
| `cgc discover` | See what's in a source | `cgc discover sqlite ./mydata.db` |
| `cgc sample` | View sample data | `cgc sample sqlite ./mydata.db users 5` |
| `cgc sql` | Run a SQL query | `cgc sql sqlite ./mydata.db "SELECT * FROM users"` |
| `cgc chunk` | Break data into pieces | `cgc chunk filesystem ./docs report.pdf` |
| `cgc health` | Check connection | `cgc health postgres "postgresql://..."` |
| `cgc version` | Show version | `cgc version` |

### Graph Extraction (Trial / Pro)

These commands require an active trial or Pro license.

| Command | What it does | Example |
|---------|--------------|---------|
| `cgc extract` | Extract relationships from text | `cgc extract "John works at Apple"` |
| `cgc extract-file` | Extract from a file | `cgc extract-file data.csv` |
| `cgc detect-domain` | Detect industry domain | `cgc detect-domain "Our Series A..."` |
| `cgc list-packs` | List industry packs | `cgc list-packs` |

### License Management

| Command | What it does | Example |
|---------|--------------|---------|
| `cgc activate` | Activate a Pro license | `cgc activate your-key-here` |
| `cgc license` | Show license status | `cgc license` |
| `cgc deactivate` | Remove license | `cgc deactivate` |

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
cgc discover <source_type> <connection>
```

**Arguments:**
- `source_type` - The type of source: `postgres`, `sqlite`, `mysql`, `filesystem`
- `connection` - Connection string or path

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
cgc discover postgres "postgresql://admin:secret@localhost:5432/company_db"
```

**Output:**
```
Source: postgres
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
cgc discover postgres "postgresql://..." --refresh
```

---

### cgc sample

View sample rows from a table or file.

**Format:**
```
cgc sample <source_type> <connection> <entity> [count]
```

**Arguments:**
- `source_type` - The type of source
- `connection` - Connection string or path
- `entity` - Table name (for databases) or file name (for filesystems)
- `count` (optional) - How many samples to show (default: 5)

**Examples:**

Show 5 sample users:
```
cgc sample postgres "postgresql://..." users
```

Show 10 sample orders:
```
cgc sample sqlite "./mydata.db" orders 10
```

Show sample from a file:
```
cgc sample filesystem "./documents" report.pdf 3
```

**Output:**
```
Samples from users (5 rows):

+----+---------------------+--------+---------------------+
| id | email               | name   | created_at          |
+----+---------------------+--------+---------------------+
| 1  | john@example.com    | John   | 2024-01-15 09:30:00 |
| 2  | jane@example.com    | Jane   | 2024-01-16 14:22:00 |
| 3  | bob@example.com     | Bob    | 2024-01-17 11:45:00 |
| 4  | alice@example.com   | Alice  | 2024-01-18 16:00:00 |
| 5  | charlie@example.com | Charlie| 2024-01-19 08:15:00 |
+----+---------------------+--------+---------------------+
```

---

### cgc sql

Run a SQL query on a database.

**Format:**
```
cgc sql <source_type> <connection> "<query>"
```

**Arguments:**
- `source_type` - The type of database source
- `connection` - Connection string
- `query` - Your SQL query (in quotes)

**Examples:**

Get all users:
```
cgc sql sqlite "./mydata.db" "SELECT * FROM users"
```

Filter with conditions:
```
cgc sql postgres "postgresql://..." "SELECT * FROM orders WHERE total > 100"
```

Join tables:
```
cgc sql postgres "postgresql://..." "SELECT users.name, orders.total FROM users JOIN orders ON users.id = orders.user_id"
```

Count records:
```
cgc sql mysql "mysql://..." "SELECT COUNT(*) as total FROM orders"
```

**Important Notes:**
- Always put your query in quotes
- Only SELECT queries are allowed (for safety)
- Results are limited to 10,000 rows by default

**Output:**
```
Query executed in 45ms
Rows returned: 3

+---------+--------+
| name    | total  |
+---------+--------+
| John    | 150.00 |
| Jane    | 275.50 |
| Bob     | 89.99  |
+---------+--------+
```

---

### cgc chunk

Break large data into smaller pieces that AI can process.

**Format:**
```
cgc chunk <source_type> <connection> <entity> [options]
```

**Arguments:**
- `source_type` - The type of data source
- `connection` - Connection string or path
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
cgc chunk sqlite "./mydata.db" large_table --strategy rows:1000
```

Chunk by tokens (good for AI):
```
cgc chunk filesystem "./documents" report.pdf --strategy tokens:2000
```

Chunk by sections (good for structured documents):
```
cgc chunk filesystem "./documents" manual.md --strategy sections
```

**Output:**
```
Chunking: report.pdf
Strategy: tokens:2000

Created 15 chunks:
  Chunk 0: ~1,985 tokens (pages 1-4)
  Chunk 1: ~2,010 tokens (pages 5-8)
  Chunk 2: ~1,920 tokens (pages 9-12)
  ...
  Chunk 14: ~1,540 tokens (pages 57-60)

Use --get 0 to view a specific chunk.
```

**View a specific chunk:**
```
cgc chunk filesystem "./documents" report.pdf --get 5
```

---

### cgc extract

Extract relationships (subject-predicate-object triplets) from text.

**Requires:** Active trial or Pro license. With Pro, extraction uses the cloud relay (no ML setup needed). During the trial or with `--local`, extraction runs on your machine.

**Format:**
```
cgc extract "<text>" [options]
```

**Arguments:**
- `text` - The text to analyze (in quotes)

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--gliner / --no-gliner` | Use GliNER ML model for enhanced entity recognition | On |
| `--domain` or `-d` | Force an industry pack (e.g., `tech_startup`) | Auto-detect |
| `--output` or `-o` | Save results to a JSON file | Display in terminal |
| `--local` or `-l` | Force local extraction instead of cloud relay | Off (uses cloud for Pro) |
| `--sink` or `-s` | Store triplets to a graph database (Neo4j or AGE) | None |
| `--graph` or `-g` | Graph name for storage (AGE only) | `cgc_graph` |

**Examples:**

Basic extraction:
```
cgc extract "John Smith is the CEO of Acme Corp in New York."
```

Pattern-only extraction (faster, no ML):
```
cgc extract "John Smith is the CEO of Acme Corp." --no-gliner
```

With domain routing:
```
cgc extract "Our CTO built the API in Kubernetes." --domain tech_startup
```

Save to file:
```
cgc extract "Apple was founded by Steve Jobs." --output results.json
```

Force local extraction (requires ML dependencies):
```
cgc extract "some text" --local
```

**Store to Neo4j:**
```
cgc extract "John works at Apple" --sink neo4j://neo4j:password@localhost:7687
```

**Store to PostgreSQL with Apache AGE:**
```
cgc extract "John works at Apple" --sink postgresql://user:pass@localhost:5432/mydb --graph company_graph
```

**Output:**
```
                        Extracted Triplets
+-------------+-----------+--------------------+------------+
| Subject     | Predicate | Object             | Confidence |
+-------------+-----------+--------------------+------------+
| John Smith  | is        | CEO of Acme Corp   | 0.90       |
+-------------+-----------+--------------------+------------+
```

**Notes:**
- Pro users get cloud-powered extraction by default -- no ML libraries needed locally
- Use `--local` if you have `pip install cgc[extraction]` and want to run on your machine
- Trial users always run extraction locally

---

### cgc extract-file

Extract relationships from a file.

**Requires:** Active trial or Pro license.

**Format:**
```
cgc extract-file <file_path> [options]
```

**Arguments:**
- `file_path` - Path to a file

**Supported file formats:**
- **Structured** (hub-and-spoke extraction): CSV, JSON, XLS, XLSX
- **Unstructured** (pattern + ML extraction): Text, PDF, Markdown, and other text files

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--gliner / --no-gliner` | Use GliNER ML model (unstructured files only) | On |
| `--domain` or `-d` | Force an industry pack | Auto-detect |
| `--output` or `-o` | Save results to a JSON file | Display in terminal |
| `--local` or `-l` | Force local extraction | Off (uses cloud for Pro) |
| `--sink` or `-s` | Store triplets to a graph database (Neo4j or AGE) | None |
| `--graph` or `-g` | Graph name for storage (AGE only) | `cgc_graph` |

**Examples:**

Extract from a CSV file (structured extraction):
```
cgc extract-file employees.csv
```

Extract from an Excel spreadsheet:
```
cgc extract-file sales_data.xlsx
```

Extract from a JSON file (array of objects):
```
cgc extract-file customer_data.json
```

Extract from a text/PDF file (unstructured extraction):
```
cgc extract-file meeting_notes.txt
```

Save results:
```
cgc extract-file inventory.xlsx --output inventory_graph.json
```

**Extract and store to Neo4j:**
```
cgc extract-file employees.csv --sink neo4j://neo4j:password@localhost:7687
```

**Extract and store to PostgreSQL AGE:**
```
cgc extract-file contracts.pdf --sink postgresql://user:pass@localhost/db --graph legal_graph
```

**Output (structured file):**
```
                   Structured Triplets (employees.csv)
+----------+---------------+-------------+------------+
| Subject  | Predicate     | Object      | Confidence |
+----------+---------------+-------------+------------+
| Alice    | IN_DEPARTMENT | Engineering | 0.90       |
| Alice    | LOCATED_IN    | NYC         | 0.90       |
| Bob      | IN_DEPARTMENT | Sales       | 0.90       |
| Bob      | LOCATED_IN    | SF          | 0.90       |
+----------+---------------+-------------+------------+
```

**Notes:**
- CGC auto-detects whether a file is structured or unstructured
- Structured files (CSV, JSON, XLS, XLSX) use hub-and-spoke extraction that converts each row into triplets
- Unstructured files use pattern matching and optionally GliNER ML models

---

### cgc detect-domain

Detect the industry domain of text for optimized extraction.

**Requires:** Active trial or Pro license.

**Format:**
```
cgc detect-domain "<text>"
```

**Examples:**
```
cgc detect-domain "Our Series A was led by Sequoia Capital. The CTO is building in Kubernetes."
```

**Output:**
```
Domain: Tech / Startup (tech_startup)
Confidence: 0.848

Entity labels: person, company, product, technology, framework, ...
Relation labels: founded, leads, built with, integrates with, ...

Top scores:
  tech_startup:       0.848 <--
  finance_investment:  0.753
  hr_people:          0.751
```

**Notes:**
- Uses E5 embeddings for semantic similarity matching
- Returns the best-matching industry pack and confidence score
- Use the pack ID with `--domain` in other extraction commands

---

### cgc list-packs

List all available industry packs for domain-specific extraction.

**Format:**
```
cgc list-packs
```

**Output:**
```
Available Industry Packs (11):

  general_business   - General business documents
  tech_startup       - Technology companies, software, APIs
  ecommerce_retail   - Shopping, orders, products, pricing
  legal_corporate    - Legal documents, contracts, governance
  finance_investment - Financial markets, securities, banking
  hr_people          - HR, employees, skills, certifications
  healthcare_medical - Medical records, diagnoses, medications
  real_estate        - Properties, brokers, transactions
  supply_chain       - Manufacturing, shipping, procurement
  research_academic  - Academic papers, grants, journals
  government_public  - Government agencies, legislation
```

---

### cgc activate

Activate a CGC Pro license key.

**Format:**
```
cgc activate <license-key>
```

**Arguments:**
- `license-key` - The UUID license key you received after purchase

**Example:**
```
cgc activate a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Output (success):**
```
License activated successfully!
Tier: Pro

Graph extraction is now available.
```

**Output (invalid key):**
```
Invalid license key. Please check your key and try again.
```

**Notes:**
- License keys are validated against our secure server
- Once activated, the key is encrypted and stored locally on your machine
- Your key works on one machine at a time -- use `cgc deactivate` to transfer

---

### cgc license

Show current license status and tier.

**Format:**
```
cgc license
```

**Output (Trial):**
```
CGC License Status

  Tier: Trial
  Days remaining: 11
  Expires: 2026-02-13
```

**Output (Pro):**
```
CGC License Status

  Tier: Pro
  Last validated: 2026-02-02 10:48 UTC
  Key: a1b2c3d4...7890
```

**Output (Free):**
```
CGC License Status

  Tier: Free

  Graph extraction requires CGC Pro.
  Run 'cgc activate <license-key>' to upgrade.
  Visit https://cgc.dev to purchase a license.
```

---

### cgc deactivate

Remove the stored license and revert to the free tier.

**Format:**
```
cgc deactivate
```

**Output:**
```
License removed. Reverted to free tier.
```

**Notes:**
- Use this before transferring your license to another machine
- After deactivation, context extension features keep working
- Graph extraction will be blocked until you reactivate

---

### cgc health

Check if a data source is accessible.

**Format:**
```
cgc health <source_type> <connection>
```

**Arguments:**
- `source_type` - The type of source
- `connection` - Connection string or path

**Example:**
```
cgc health postgres "postgresql://admin:secret@localhost:5432/mydb"
```

**Output (Success):**
```
OK Source is healthy
  Type: postgres
  Status: Connected
  Response time: 12ms
```

**Output (Failure):**
```
X Source is not accessible
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

**Output:**
```
CGC (Context Graph Connector) v0.4.0
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
cgc sample filesystem "C:/My Documents" users 5
```

### Output Formats

Some commands support different output formats:

```
cgc discover postgres "postgresql://..." --format json
```

### Quiet Mode

Suppress extra output:

```
cgc sample postgres "postgresql://..." users --quiet
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

### "Graph extraction requires CGC Pro"

You're trying to use extraction on the free tier.

**Solutions:**
1. If you just installed CGC, a trial should start automatically. Run `cgc license` to check
2. Purchase a Pro license at [https://cgc.dev](https://cgc.dev)
3. Activate with `cgc activate your-key-here`

### "Invalid license key"

The license key was rejected.

**Solutions:**
1. Double-check the key (copy-paste from your purchase email)
2. Make sure you're using the full UUID (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
3. Contact support if the issue persists

---

## Next Steps

- [API Reference](API.md) - Use CGC with n8n, Make.com, or any HTTP client
- [MCP Reference](MCP.md) - Connect CGC to Claude Desktop
- [Security Guide](SECURITY.md) - Securing your CGC installation
