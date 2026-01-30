# CGC API Reference

This guide explains how to use CGC to connect your data to AI tools and automation platforms.

---

## Understanding CGC: What It Does (and Doesn't Do)

Before diving into the API, it's important to understand what CGC handles and what you need to do yourself.

### What CGC Does

| Task | CGC Handles It? | Description |
|------|-----------------|-------------|
| Connect to files | Yes | Point CGC at a folder, it reads PDFs, Word docs, text files |
| Connect to databases | Yes | PostgreSQL, MySQL, SQLite - CGC reads your tables |
| Break documents into chunks | Yes | Split large files into AI-sized pieces |
| Search text (keyword) | Yes | Find text patterns in files or database fields |
| Extract relationships from text | Yes | Find "who did what to whom" in sentences |
| Connect to vector databases | Yes | Qdrant, Pinecone, pgvector |

### What CGC Does NOT Do

| Task | Who Does It? | What You Need |
|------|--------------|---------------|
| Convert text to vectors (embeddings) | External service | OpenAI, Cohere, or local model |
| Store extracted triplets | You decide | Database, Neo4j, or JSON file |
| Summarize text | External AI | OpenAI, Claude, etc. |

### Important Concept: Vector Search Requires Pre-Embedded Queries

When searching a vector database, you can't just send text like "find similar documents about cats".

**The workflow is:**
```
1. You have: "find documents about cats"
2. You must FIRST: Send to OpenAI/Cohere to get embeddings → [0.023, -0.156, 0.892, ...]
3. THEN send: Those numbers to CGC's vector search
4. CGC returns: Similar documents from your vector store
```

CGC doesn't do step 2 for you. You need an embedding service.

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
    {"index": 1, "content": "Chapter 2: Market Analysis..."},
    ...
  ],
  "total_chunks": 15
}
```

**Step 2:** In n8n/Make, loop through chunks and send each to AI

---

### Workflow 3: Extract Knowledge from Text

**Goal:** Build a knowledge graph from documents

**What is a triplet?** A simple fact: `(Subject, Relationship, Object)`
- "Apple was founded by Steve Jobs" → `(Apple, founded by, Steve Jobs)`
- "Paris is the capital of France" → `(Paris, capital of, France)`

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

### Workflow 4: Vector/Semantic Search

**Goal:** Find documents "similar to" a concept, not just keyword matches

**Requirements:**
- A vector database (Qdrant, Pinecone, or pgvector)
- An embedding service (OpenAI, Cohere, etc.)
- Documents already embedded and stored in your vector DB

**Why this is complex:** Vector search works with numbers, not words.

**The full workflow:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        YOUR AUTOMATION TOOL                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  User asks: "Find documents about machine learning"                 │
│                          │                                          │
│                          ▼                                          │
│  ┌─────────────────────────────────────┐                           │
│  │  Step 1: Call OpenAI Embeddings API │                           │
│  │  Input: "machine learning"          │                           │
│  │  Output: [0.023, -0.15, 0.89, ...]  │                           │
│  └─────────────────────────────────────┘                           │
│                          │                                          │
│                          ▼                                          │
│  ┌─────────────────────────────────────┐                           │
│  │  Step 2: Call CGC Vector Search     │                           │
│  │  Input: [0.023, -0.15, 0.89, ...]   │  ◄── Numbers, not words!  │
│  │  Output: Similar documents          │                           │
│  └─────────────────────────────────────┘                           │
│                          │                                          │
│                          ▼                                          │
│  Results: Documents about ML, AI, neural networks, etc.            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

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
POST http://localhost:8420/query/semantic
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
  "source_id": "my_docs",           // Your name for it
  "source_type": "filesystem",       // filesystem, postgres, mysql, sqlite, qdrant, etc.
  "connection": "C:/Users/You/Docs"  // Path or connection string
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

#### Remove a Source
```
DELETE http://localhost:8420/sources/my_docs
```

#### See What's in a Source
```
GET http://localhost:8420/sources/my_docs/schema
```
Returns list of files (filesystem) or tables (database).

---

### Searching

#### Text Search (Keywords)
Find exact or fuzzy text matches.
```
POST http://localhost:8420/query/search
{
  "source_id": "my_docs",
  "query": "revenue growth",
  "entity": "report.pdf",        // Optional: specific file
  "fuzzy_fallback": true         // Try fuzzy if no exact match
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
POST http://localhost:8420/query/semantic
{
  "source_id": "my_vectors",
  "query_vector": [0.023, -0.156, ...],  // From embedding API
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
  "strategy": "tokens:2000"       // ~2000 tokens per chunk
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

### Extracting Knowledge

#### Extract Triplets
Find facts/relationships in text. **Does not store them - just extracts.**
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
| `use_gliner` | boolean | `true` | Use GliNER ML model (higher recall, slower). Set `false` for pattern-only extraction. |
| `domain` | string | `null` | Force an industry pack (e.g., `"tech_startup"`, `"healthcare_medical"`). `null` for auto-detection. |

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
  "entity_labels": ["person", "company", "product", "technology", ...],
  "relation_labels": ["founded", "leads", "built with", ...],
  "scores": {"tech_startup": 0.848, "finance_investment": 0.753, ...}
}
```

#### List Industry Packs
See all available domain packs for extraction.
```
GET http://localhost:8420/packs
```

Returns 11 industry packs: `general_business`, `tech_startup`, `ecommerce_retail`, `legal_corporate`, `finance_investment`, `hr_people`, `healthcare_medical`, `real_estate`, `supply_chain`, `research_academic`, `government_public`.

**What to do with triplets:** Store them yourself in:
- A database table with columns: subject, predicate, object
- Neo4j or another graph database
- A JSON file for later use

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

**Format as a list:**
```powershell
(Invoke-RestMethod -Uri "http://localhost:8420/query/sql" -Method POST -ContentType "application/json" -Body '{"source_id": "mydb", "sql": "SELECT * FROM users"}').rows | Format-List
```

**Format as auto-sized table:**
```powershell
(Invoke-RestMethod -Uri "http://localhost:8420/query/sql" -Method POST -ContentType "application/json" -Body '{"source_id": "mydb", "sql": "SELECT * FROM users"}').rows | Format-Table -AutoSize -Wrap
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
- [Technical Overview](TECHNICAL.md) - Architecture details
