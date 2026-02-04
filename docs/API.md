# CGC API Reference

This guide explains how to use CGC's HTTP API to connect your data to AI tools and automation platforms.

---

## Table of Contents

- [Understanding CGC](#understanding-cgc-what-it-does-and-doesnt-do)
- [Free vs Pro Endpoints](#free-vs-pro-endpoints)
- [Common Workflows](#common-workflows-step-by-step)
- [Quick Start](#quick-start)
- [All Endpoints](#all-endpoints-reference)
- [Using with PowerShell](#using-with-powershell-windows)
- [Using with n8n](#using-with-n8n)
- [Error Reference](#error-reference)

---

## Understanding CGC: What It Does (and Doesn't Do)

Before diving into the API, it's important to understand what CGC handles and what you need to do yourself.

### What CGC Does

| Task | Tier | Description |
|------|------|-------------|
| Connect to files | Free | Point CGC at a folder, it reads PDFs, Word docs, text files |
| Connect to databases | Free | PostgreSQL, MySQL, SQLite - CGC reads your tables |
| Break documents into chunks | Free | Split large files into AI-sized pieces |
| Search text (keyword) | Free | Find text patterns in files or database fields |
| Connect to vector databases | Free | Qdrant, Pinecone, pgvector |
| Schema discovery and sampling | Free | Explore your data structure without reading everything |
| Extract relationships from text | Trial/Pro | Find "who did what to whom" in sentences |
| Extract from files (CSV, Excel, JSON) | Trial/Pro | Convert structured data into knowledge graph triplets |
| Domain detection | Trial/Pro | Classify text by industry for optimized extraction |

### What CGC Does NOT Do

| Task | Who Does It? | What You Need |
|------|--------------|---------------|
| Convert text to vectors (embeddings) | External service | OpenAI, Cohere, or local model |
| Store extracted triplets | You decide | Database, Neo4j, or JSON file |
| Summarize text | External AI | OpenAI, Claude, etc. |

---

## Free vs Pro Endpoints

| Endpoint | Free | Trial/Pro |
|----------|------|-----------|
| `GET /health` | Yes | Yes |
| `GET /sources`, `POST /sources`, `DELETE /sources/{id}` | Yes | Yes |
| `GET /sources/{id}/schema` | Yes | Yes |
| `GET /schemas` | Yes | Yes |
| `POST /query/sql` | Yes | Yes |
| `POST /query/search` | Yes | Yes |
| `POST /query/vector` | Yes | Yes |
| `POST /sample` | Yes | Yes |
| `POST /chunk` | Yes | Yes |
| `GET /graph` | Yes | Yes |
| `POST /graph/find-related` | Yes | Yes |
| `GET /summary` | Yes | Yes |
| `POST /extract/triplets` | -- | Yes |
| `POST /extract/structured` | -- | Yes |
| `POST /extract/file` | -- | Yes |
| `POST /extract/chunked` | -- | Yes |
| `POST /detect/domain` | -- | Yes |
| `GET /packs` | -- | Yes |
| `GET /sinks`, `POST /sinks`, `DELETE /sinks/{id}` | -- | Yes |
| `GET /sinks/{id}/stats` | -- | Yes |
| `POST /sinks/{id}/query` | -- | Yes |
| `GET /sinks/{id}/find/{entity}` | -- | Yes |

Extraction and sink endpoints return a `403` error on the free tier with instructions to upgrade.

---

## Common Workflows (Step-by-Step)

### Workflow 1: Search Your Documents

**Goal:** Find all mentions of "revenue" in your PDF reports

**Step 1:** Start CGC server
```
cgc serve
```

**Step 2:** Add your documents folder
```
POST http://localhost:8420/sources
{
  "source_id": "my_docs",
  "source_type": "filesystem",
  "connection": "C:/Users/You/Documents/Reports"
}
```

**Step 3:** Search for "revenue"
```
POST http://localhost:8420/query/search
{
  "source_id": "my_docs",
  "query": "revenue"
}
```

**Result:** CGC returns every line containing "revenue" from all your files.

---

### Workflow 2: Process a Large Document with AI

**Goal:** Have AI summarize a 100-page report

**Problem:** AI can only handle ~4000 words at a time

**Solution:** Break it into chunks, process each one

**Step 1:** Add document folder and chunk the file
```
POST http://localhost:8420/chunk
{
  "source_id": "my_docs",
  "entity": "big-report.pdf",
  "strategy": "tokens:2000"
}
```

**Result:** CGC returns chunks like this:
```json
{
  "chunks": [
    {"index": 0, "content": "Chapter 1: Introduction..."},
    {"index": 1, "content": "Chapter 2: Market Analysis..."}
  ],
  "total_chunks": 15
}
```

**Step 2:** In n8n/Make, loop through chunks and send each to AI

---

### Workflow 3: Extract Knowledge from Text (Trial/Pro)

**Goal:** Build a knowledge graph from documents

**What is a triplet?** A simple fact: `(Subject, Relationship, Object)`
- "Apple was founded by Steve Jobs" --> `(Apple, founded by, Steve Jobs)`
- "Paris is the capital of France" --> `(Paris, capital of, France)`

**Step 1:** Get your document text (from chunking or search)

**Step 2:** Send text to triplet extraction
```
POST http://localhost:8420/extract/triplets
{
  "text": "Apple Inc. was founded by Steve Jobs in California."
}
```

**Result:**
```json
{
  "triplets": [
    {"subject": "Apple Inc.", "predicate": "founded by", "object": "Steve Jobs"},
    {"subject": "Apple Inc.", "predicate": "founded in", "object": "California"}
  ]
}
```

**Important:** CGC extracts the triplets but does NOT store them. You need to save them to:
- A database table
- Neo4j graph database
- A JSON file
- Wherever you want

---

### Workflow 4: Extract from Structured Data (Trial/Pro)

**Goal:** Convert a CSV or Excel file into knowledge graph triplets

**Step 1:** Upload the file
```
POST http://localhost:8420/extract/file
Content-Type: multipart/form-data

file: employees.csv
```

**Result:**
```json
{
  "triplets": [
    {"subject": "Alice", "predicate": "IN_DEPARTMENT", "object": "Engineering", "confidence": 0.9},
    {"subject": "Alice", "predicate": "LOCATED_IN", "object": "NYC", "confidence": 0.9},
    {"subject": "Bob", "predicate": "IN_DEPARTMENT", "object": "Sales", "confidence": 0.9}
  ],
  "count": 6,
  "file_type": "structured",
  "filename": "employees.csv"
}
```

---

### Workflow 5: Chunk Then Extract (Trial/Pro)

**Goal:** Process a large file by chunking it first, then extracting from each chunk

**Step 1:** Send a chunked extraction request
```
POST http://localhost:8420/extract/chunked
{
  "source_id": "my_docs",
  "entity": "big-report.pdf",
  "strategy": "tokens:2000",
  "use_gliner": false
}
```

**Result:**
```json
{
  "chunks_processed": 15,
  "total_triplets": 47,
  "triplets": [...]
}
```

This is a convenience endpoint that combines chunking + extraction in one call.

---

### Workflow 6: Vector/Semantic Search

**Goal:** Find documents "similar to" a concept, not just keyword matches

**Requirements:**
- A vector database (Qdrant, Pinecone, or pgvector)
- An embedding service (OpenAI, Cohere, etc.)
- Documents already embedded and stored in your vector DB

**Step 1:** Get embeddings from OpenAI (in n8n, use the OpenAI node)
```
POST https://api.openai.com/v1/embeddings
{
  "input": "machine learning",
  "model": "text-embedding-ada-002"
}
```
Returns: `[0.023, -0.156, 0.892, ...]` (1536 numbers)

**Step 2:** Send those numbers to CGC
```
POST http://localhost:8420/query/vector
{
  "source_id": "my_vectors",
  "query_vector": [0.023, -0.156, 0.892, ...],
  "top_k": 10
}
```

**Result:** The 10 most similar documents from your vector store.

---

## Quick Start

### Step 1: Start the Server

**Windows PowerShell:**
```
.\cgc.exe serve
```

**Windows Command Prompt:**
```
cgc.exe serve
```

You'll see:
```
Starting CGC API server on 127.0.0.1:8420
```

### Step 2: Test It

Open browser to: `http://localhost:8420/health`

Should show: `{"status": "healthy"}`

### Step 3: Try the Interactive Docs

Go to: `http://localhost:8420/docs`

You can test every endpoint directly in your browser!

---

## All Endpoints (Reference)

### Managing Data Sources

#### List Sources
See what's connected.
```
GET http://localhost:8420/sources
```

#### Add a Source
Connect a folder or database.
```
POST http://localhost:8420/sources
{
  "source_id": "my_docs",
  "source_type": "filesystem",
  "connection": "C:/Users/You/Docs"
}
```

**Source types:**
- `filesystem` - Local folder with files
- `postgres` - PostgreSQL database
- `mysql` - MySQL database
- `sqlite` - SQLite file
- `qdrant` - Qdrant vector database
- `pinecone` - Pinecone vector database
- `pgvector` - PostgreSQL with pgvector extension
- `mongodb` - MongoDB database

#### Remove a Source
```
DELETE http://localhost:8420/sources/my_docs
```

#### See What's in a Source
```
GET http://localhost:8420/sources/my_docs/schema
```
Returns list of files (filesystem) or tables (database).

#### Discover All Schemas
```
GET http://localhost:8420/schemas
```
Returns schemas for all connected sources at once.

---

### Searching

#### Text Search (Keywords)
Find exact or fuzzy text matches.
```
POST http://localhost:8420/query/search
{
  "source_id": "my_docs",
  "query": "revenue growth",
  "entity": "report.pdf",
  "fuzzy_fallback": true
}
```

#### SQL Query (Databases only)
```
POST http://localhost:8420/query/sql
{
  "source_id": "mydb",
  "sql": "SELECT * FROM users WHERE active = true LIMIT 10"
}
```
Note: Only SELECT queries allowed for safety.

#### Vector/Semantic Search
**Requires:** Pre-embedded query vector from OpenAI/Cohere.
```
POST http://localhost:8420/query/vector
{
  "source_id": "my_vectors",
  "query_vector": [0.023, -0.156, ...],
  "top_k": 10
}
```

---

### Processing Documents

#### Chunk a Document
Break large files into AI-sized pieces.
```
POST http://localhost:8420/chunk
{
  "source_id": "my_docs",
  "entity": "big-report.pdf",
  "strategy": "tokens:2000"
}
```

**Strategy options:**
- `tokens:2000` - Split by token count (best for AI)
- `rows:1000` - Split by rows (for databases)
- `sections` - Split by headers (for markdown)

#### Get Specific Chunk
```
GET http://localhost:8420/chunk/my_docs/big-report.pdf/0
```
(Gets chunk index 0)

#### Sample Data
Get a few example rows/lines.
```
POST http://localhost:8420/sample
{
  "source_id": "my_docs",
  "entity": "report.pdf",
  "n": 5
}
```

---

### Relationships and Context

#### Get Relationship Graph
```
GET http://localhost:8420/graph
```
Returns how tables and entities relate to each other across all sources.

#### Find Related Records
```
POST http://localhost:8420/graph/find-related
{
  "source_id": "mydb",
  "entity": "users",
  "field": "id",
  "value": "42"
}
```
Finds all records related to a specific value across all sources.

#### Get Summary
```
GET http://localhost:8420/summary
```
Returns a compact overview of all connected sources and their schemas. Useful for giving AI context about available data.

---

### Extracting Knowledge (Trial/Pro)

These endpoints require an active trial or Pro license.

#### Extract Triplets from Text
Find facts/relationships in text.
```
POST http://localhost:8420/extract/triplets
{
  "text": "Steve Jobs founded Apple in California.",
  "use_gliner": false,
  "domain": null
}
```

**Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | string | required | Text to extract from |
| `use_gliner` | boolean | `true` | Use GliNER ML model (higher recall). Set `false` for pattern-only extraction. |
| `domain` | string | `null` | Force an industry pack (e.g., `"tech_startup"`, `"healthcare_medical"`). `null` for auto-detection. |
| `sink_uri` | string | `null` | Store triplets to a graph database. Supports `neo4j://`, `age://`, or `postgresql://` URIs. |
| `graph_name` | string | `null` | Graph name for AGE sinks. |

Returns:
```json
{
  "triplets": [
    {
      "subject": "Steve Jobs",
      "predicate": "FOUNDED",
      "object": "Apple",
      "confidence": 0.92,
      "subject_label": "person",
      "object_label": "organization"
    }
  ],
  "count": 1
}
```

#### Extract from Structured Data
Extract relationships from tabular data (JSON rows) using a hub-and-spoke model.
```
POST http://localhost:8420/extract/structured
{
  "data": [
    {"name": "Alice", "department": "Engineering", "location": "NYC"},
    {"name": "Bob", "department": "Sales", "location": "SF"}
  ]
}
```

Returns:
```json
{
  "triplets": [
    {"subject": "Alice", "predicate": "IN_DEPARTMENT", "object": "Engineering", "confidence": 0.9},
    {"subject": "Alice", "predicate": "LOCATED_IN", "object": "NYC", "confidence": 0.9}
  ],
  "count": 4,
  "rows_processed": 2
}
```

#### Extract from File Upload
Upload a file and extract triplets. Supports CSV, JSON, XLS, XLSX (structured) and text, PDF, Markdown (unstructured).
```
POST http://localhost:8420/extract/file
Content-Type: multipart/form-data

file: (your file)
domain: tech_startup          (optional)
use_gliner: true              (optional, default: true)
```

Returns:
```json
{
  "triplets": [...],
  "count": 12,
  "file_type": "structured",
  "filename": "employees.csv"
}
```

#### Chunk Then Extract
Chunk a file from a connected source, then extract triplets from each chunk.
```
POST http://localhost:8420/extract/chunked
{
  "source_id": "my_docs",
  "entity": "big-report.pdf",
  "strategy": "tokens:2000",
  "use_gliner": false,
  "domain": null
}
```

Returns:
```json
{
  "chunks_processed": 15,
  "total_triplets": 47,
  "triplets": [...]
}
```

#### Detect Domain
Classify text into an industry domain for optimized extraction.
```
POST http://localhost:8420/detect/domain
{
  "text": "Our Series A was led by Sequoia. The CTO is building in Kubernetes."
}
```

Returns:
```json
{
  "pack_id": "tech_startup",
  "pack_name": "Tech / Startup",
  "confidence": 0.848,
  "entity_labels": ["person", "company", "product", "technology"],
  "relation_labels": ["founded", "leads", "built with"],
  "scores": {"tech_startup": 0.848, "finance_investment": 0.753}
}
```

#### List Industry Packs
See all available domain packs for extraction.
```
GET http://localhost:8420/packs
```

Returns 11 industry packs: `general_business`, `tech_startup`, `ecommerce_retail`, `legal_corporate`, `finance_investment`, `hr_people`, `healthcare_medical`, `real_estate`, `supply_chain`, `research_academic`, `government_public`.

**What to do with triplets:** Store them yourself OR use the `sink_uri` parameter to automatically store to a graph database.

---

### Managing Graph Sinks (Trial/Pro)

Graph sinks are databases where extracted triplets can be stored automatically.

#### List Sinks
```
GET http://localhost:8420/sinks
```

#### Add a Sink
```
POST http://localhost:8420/sinks
{
  "sink_id": "mygraph",
  "sink_type": "neo4j",
  "connection": "bolt://localhost:7687",
  "options": {
    "user": "neo4j",
    "password": "password",
    "database": "neo4j"
  }
}
```

**Sink types:**
- `neo4j` - Neo4j graph database (requires `user`, `password`)
- `age` - PostgreSQL with Apache AGE extension (requires `graph_name`)

**AGE Example:**
```
POST http://localhost:8420/sinks
{
  "sink_id": "mygraph",
  "sink_type": "age",
  "connection": "postgresql://user:pass@localhost:5432/mydb",
  "options": {
    "graph_name": "company_graph"
  }
}
```

#### Remove a Sink
```
DELETE http://localhost:8420/sinks/mygraph
```

#### Get Sink Statistics
```
GET http://localhost:8420/sinks/mygraph/stats
```

Returns:
```json
{
  "sink_id": "mygraph",
  "node_count": 1523,
  "edge_count": 2891,
  "graph_names": ["company_graph"]
}
```

#### Query a Sink (Cypher)
Execute Cypher queries against a graph sink.
```
POST http://localhost:8420/sinks/mygraph/query
{
  "cypher": "MATCH (n)-[r]->(m) RETURN n.name, type(r), m.name LIMIT 10",
  "params": {},
  "graph_name": null
}
```

Returns:
```json
{
  "results": [
    {"n.name": "John", "type(r)": "WORKS_AT", "m.name": "Apple"},
    {"n.name": "Jane", "type(r)": "MANAGES", "m.name": "Engineering"}
  ],
  "count": 2
}
```

#### Find Entity in Sink
Find all triplets involving a specific entity.
```
GET http://localhost:8420/sinks/mygraph/find/John?limit=50
```

Returns:
```json
{
  "entity": "John",
  "triplets": [
    {"subject": "John", "predicate": "WORKS_AT", "object": "Apple"},
    {"subject": "John", "predicate": "LIVES_IN", "object": "California"}
  ],
  "count": 2
}
```

---

### Storing Triplets via URI

Instead of managing sinks explicitly, you can pass a `sink_uri` parameter to any extraction endpoint:

**Neo4j:**
```
POST http://localhost:8420/extract/triplets
{
  "text": "John works at Apple Inc.",
  "sink_uri": "neo4j://neo4j:password@localhost:7687/neo4j"
}
```

**PostgreSQL AGE:**
```
POST http://localhost:8420/extract/triplets
{
  "text": "John works at Apple Inc.",
  "sink_uri": "postgresql://user:pass@localhost:5432/mydb",
  "graph_name": "company_graph"
}
```

The response includes a `sink` field with storage results:
```json
{
  "triplets": [...],
  "count": 2,
  "sink": {
    "stored": 2,
    "skipped": 0,
    "errors": [],
    "sink_type": "neo4j"
  }
}
```

---

## Using with PowerShell (Windows)

PowerShell is the default terminal on Windows. Here's how to call CGC's API.

### Important: PowerShell vs curl

PowerShell has a `curl` alias, but it's NOT the real curl - it's `Invoke-WebRequest`. Use `Invoke-RestMethod` instead:

```powershell
# This WON'T work (PowerShell curl alias):
curl -X POST http://localhost:8420/sources ...

# This WILL work:
Invoke-RestMethod -Uri "http://localhost:8420/sources" -Method POST ...
```

### Basic API Calls

**Add a data source:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8420/sources" -Method POST -ContentType "application/json" -Body '{"source_id": "mydb", "source_type": "postgres", "connection": "postgresql://user:pass@localhost:5432/dbname"}'
```

**Run a SQL query:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8420/query/sql" -Method POST -ContentType "application/json" -Body '{"source_id": "mydb", "sql": "SELECT * FROM users LIMIT 10"}'
```

**Search for text:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8420/query/search" -Method POST -ContentType "application/json" -Body '{"source_id": "mydb", "query": "revenue", "entity": "reports"}'
```

### Seeing Full Results

PowerShell truncates long output. Use these tricks to see everything:

**Convert to JSON (best for nested data):**
```powershell
(Invoke-RestMethod -Uri "http://localhost:8420/query/sql" -Method POST -ContentType "application/json" -Body '{"source_id": "mydb", "sql": "SELECT * FROM users"}').rows | ConvertTo-Json
```

**Save to a variable first:**
```powershell
$result = Invoke-RestMethod -Uri "http://localhost:8420/query/sql" -Method POST -ContentType "application/json" -Body '{"source_id": "mydb", "sql": "SELECT * FROM users"}'

# Now explore the result
$result.rows          # Just the data rows
$result.row_count     # Number of rows
$result.columns       # Column names
$result | ConvertTo-Json -Depth 5   # Full result as JSON
```

### Quick Test Commands

Once CGC is running (`.\cgc.exe serve`), try these:

```powershell
# Check health
Invoke-RestMethod -Uri "http://localhost:8420/health"

# List connected sources
Invoke-RestMethod -Uri "http://localhost:8420/sources"

# View a source's schema (tables/files)
Invoke-RestMethod -Uri "http://localhost:8420/sources/mydb/schema"
```

---

## Using with n8n

### Basic Setup

1. Start CGC: `cgc serve`
2. In n8n, use "HTTP Request" nodes to call CGC

### Example: Search and Summarize

**Node 1: HTTP Request (Search)**
- Method: POST
- URL: `http://localhost:8420/query/search`
- Body:
```json
{
  "source_id": "my_docs",
  "query": "quarterly results"
}
```

**Node 2: OpenAI (Summarize)**
- Connect to Node 1
- Prompt: `Summarize these search results: {{ $json.rows }}`

### AI Agent Integration Issues

If using n8n's AI Agent with HTTP Request Tool nodes, you may see "Field required" errors.

**Problem:** The AI outputs parameters but they don't map to the request body.

**Solution:** Map parameters explicitly:
1. Body Content Type: `JSON`
2. Specify Body: `Using Fields Below`
3. Add fields:
   - Name: `source_id`, Value: `{{ $fromAI("source_id") }}`
   - Name: `entity`, Value: `{{ $fromAI("entity") }}`

**Alternative:** Use regular HTTP Request nodes instead of Tool nodes.

---

## Error Reference

| Error | Meaning | Fix |
|-------|---------|-----|
| 401 Unauthorized | Missing API key | Add `X-API-Key` header (secure mode) |
| 403 Forbidden | Free tier trying to use extraction | Activate a Pro license: `cgc activate <key>` |
| 404 Source Not Found | Source not connected | Add source first with POST /sources |
| 422 Validation Error | Bad input format | Check that entity is a string, not JSON object |
| 400 SQL Blocked | Dangerous SQL | Only SELECT queries allowed |

---

## Summary: What Goes Where

| Data Type | Where It Lives | CGC's Role |
|-----------|----------------|------------|
| Your files | Your computer/server | CGC reads them |
| Database tables | Your database server | CGC queries them |
| Extracted triplets | **You decide** (DB, Neo4j, JSON) | CGC extracts, you store |
| Vector embeddings | Your vector DB (Qdrant, etc.) | CGC searches them |
| Embedding generation | **External** (OpenAI, Cohere) | CGC does NOT do this |

---

## Next Steps

- [CLI Reference](CLI.md) - Command-line usage
- [MCP Reference](MCP.md) - Claude integration
- [Security Guide](SECURITY.md) - Securing your CGC installation
