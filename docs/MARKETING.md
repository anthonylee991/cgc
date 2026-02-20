# CGC Marketing Feature List

Use this content for the CGC website (cgc.dev), landing pages, and product descriptions.

---

## Tagline Options

- "Give your AI the ability to explore your data."
- "Connect any data source to any AI assistant."
- "Context extension for AI agents -- databases, files, and vector stores in one tool."

---

## One-Liner

CGC (Context Graph Connector) connects AI assistants to your databases, files, and vector stores so they can explore and understand your data directly -- no copy-pasting required.

---

## Feature List (for website)

### Context Extension (Free Forever)

**Connect to anything**
- PostgreSQL, MySQL, SQLite databases
- PDF, Word, Excel, CSV, JSON, Markdown, and code files
- Qdrant, Pinecone, pgvector, and MongoDB Atlas vector stores
- Connect once, query unlimited times

**Schema discovery**
- Instantly see all tables, columns, types, and row counts
- File structure mapping for document folders
- Relationship detection across tables

**Smart data sampling**
- Preview any table or file without loading everything
- Configurable sample sizes
- Works across all source types

**Intelligent chunking**
- Break large documents into AI-sized pieces
- Row-based, token-based, or section-based strategies
- Process 1000-page PDFs without hitting context limits

**Full SQL access**
- Run SELECT queries on any connected database
- Safe by default -- dangerous queries are blocked
- Results up to 10,000 rows

**Text search**
- Keyword and pattern matching across all sources
- Fuzzy search fallback for approximate matches
- Search within specific files or across entire folders

**Relationship mapping**
- Automatic foreign key and relationship detection
- Cross-source relationship graph
- Find all related records with one query

**Session tracking**
- Persist work context across conversations
- Automatic logging of decisions and findings
- Resume sessions after breaks or context resets
- Built-in safeguards against session bloat

**Three ways to use it**
- Command-line interface (CLI) for quick tasks
- HTTP API for automation tools (n8n, Make.com, Zapier)
- MCP server for direct Claude Desktop/Code integration

---

### Graph Extraction (14-Day Free Trial, then Pro)

**Cloud-powered extraction**
- No ML libraries or GPU required
- Extract knowledge graph triplets from any text
- Subject-predicate-object relationships with confidence scores
- Powered by our secure cloud relay

**Structured data extraction**
- Upload CSV, Excel (XLS/XLSX), or JSON files
- Hub-and-spoke model converts rows into graph triplets
- Automatic column-to-relationship mapping

**17 industry packs**
- Optimized entity and relation labels for specific domains
- Automatic domain detection using E5 embeddings
- Starter packs: general business, tech/startup, e-commerce, legal, finance, HR, healthcare, real estate, supply chain, research, government
- Expansion packs: accounting & financial reporting, insurance, manufacturing & engineering, marketing & sales, energy & environment, software engineering

**50+ extraction patterns**
- High-precision regex patterns for common relationships
- Works without any ML dependencies
- Combines with GliNER/GliREL for maximum recall

**File upload extraction**
- Upload files directly via API or CLI
- Auto-detects structured vs. unstructured content
- Supports CSV, JSON, XLS, XLSX, text, PDF, Markdown

**Chunk-then-extract workflow**
- Process large documents automatically
- Chunks the file, extracts from each chunk, combines results
- Single API call for the entire pipeline

---

## Pricing Tiers (for website)

### Free
- All context extension features
- Connect unlimited data sources
- Unlimited queries, samples, and chunks
- CLI, API, and MCP access
- No account required

### Trial (automatic, 14 days)
- Everything in Free
- Full graph extraction access
- All 17 industry packs
- Runs locally on your machine

### Pro ($X/month or one-time)
- Everything in Trial
- Cloud-powered extraction (no ML setup)
- Priority support
- License key for easy activation

---

## Key Differentiators

1. **No copy-paste workflow** -- Your AI queries your data directly instead of you pasting it into chat windows.

2. **Universal connector** -- One tool connects to SQL databases, document folders, and vector stores. No switching between tools.

3. **Zero-config MCP** -- Drop in the executable, add one line to your Claude config, and Claude can access all your data.

4. **Free context extension** -- The most useful features (connect, discover, sample, chunk, search, SQL) are free forever. No bait-and-switch.

5. **Cloud extraction** -- Pro users get graph extraction without installing PyTorch, spaCy, or any ML dependencies. Just activate and extract.

6. **Industry-aware** -- 17 domain-specific extraction packs that understand the entities and relationships in your industry.

7. **Works offline** -- Context extension features run entirely on your machine. Your data never leaves unless you use cloud extraction.

8. **Built for non-coders** -- Executables work out of the box on Windows and macOS. No Python, no command line expertise required.

---

## Use Cases (for website sections)

### For Business Analysts
"Connect your company database and let Claude answer questions about your data. No SQL knowledge needed -- just ask in plain English."

### For No-Code Builders
"Add CGC to your n8n or Make.com workflows. Extract knowledge from documents, search databases, and feed results to AI -- all through HTTP APIs."

### For Developers
"Build AI agents that can explore any data source. CGC provides the data access layer so you can focus on the intelligence layer."

### For Data Teams
"Convert unstructured documents and spreadsheets into knowledge graph triplets. Feed structured facts into Neo4j, graph databases, or your own analytics pipeline."

### For Anyone with Data
"Stop copy-pasting data into ChatGPT. Connect your files and databases once, then have unlimited AI-powered conversations about your data."

---

## Social Proof / Stats (when available)

- X data sources supported
- X industry packs for domain-specific extraction
- 50+ built-in extraction patterns
- Works with Claude, ChatGPT, and any MCP-compatible AI
- Windows and macOS executables -- no installation required
