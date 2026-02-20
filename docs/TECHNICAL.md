# CGC Technical Overview

This document explains how CGC works and provides detailed use cases. While written for all users, this goes deeper into the technical concepts.

---

## Table of Contents

- [How CGC Works](#how-cgc-works)
- [The Problem CGC Solves](#the-problem-cgc-solves)
- [Core Concepts](#core-concepts)
- [Detailed Use Cases](#detailed-use-cases)
- [Data Flow](#data-flow)
- [Architecture](#architecture)
- [Supported Data Sources](#supported-data-sources)

---

## How CGC Works

### The Simple Explanation

CGC is a "bridge" between AI assistants and your data. Here's what happens when you ask Claude a question:

1. **You ask a question** about your data
2. **Claude decides what data it needs** to answer
3. **Claude uses CGC** to fetch that specific data
4. **CGC connects to your database/files** and retrieves the data
5. **Claude reads the data** and gives you an answer

The key insight: Claude doesn't need ALL your data - it just needs the RIGHT data at the RIGHT time.

### Why This Matters

AI assistants have a "context window" - a limit on how much text they can consider at once. For example:
- Claude can handle about 100,000-200,000 tokens
- ChatGPT varies from 8,000 to 128,000 tokens depending on version

Your database might have millions of rows. Your documents might have thousands of pages. You can't paste it all into a chat window.

CGC solves this by letting the AI **navigate** your data instead of memorizing it.

---

## The Problem CGC Solves

### Context Rot

Research from MIT found that AI reasoning degrades as conversations get longer - a phenomenon called "context rot." After about 33,000 tokens, AI assistants start making more mistakes, forgetting earlier information, and losing track of the conversation.

### Traditional Solutions

**Copy-Paste Method:**
- You copy data from your database
- Paste it into the chat
- AI analyzes it
- Problems: Tedious, limited by context window, data becomes stale

**RAG (Retrieval-Augmented Generation):**
- Pre-index all your documents
- Search returns relevant chunks
- AI reads the chunks
- Problems: Requires setup, may miss relevant data, one-directional

### The CGC Approach

CGC treats your data as an **environment to explore**, not a static snapshot. The AI can:

- Ask follow-up questions to your database
- Drill down into specific records
- Follow relationships across tables
- Request exactly the data it needs

This is similar to how a human analyst would work - they don't memorize the entire database; they run queries as needed.

---

## Core Concepts

### Data Sources

A "source" is any place your data lives:

| Type | Examples |
|------|----------|
| Relational Database | PostgreSQL, MySQL, SQLite |
| File Storage | Local folders, network drives |
| Vector Database | Qdrant, Pinecone, pgvector |
| Document Store | MongoDB |

You can connect multiple sources and query across them.

### Schema Discovery

When you connect a source, CGC "discovers" what's inside:

**For databases:**
- Table names and relationships
- Column names and data types
- Primary keys and foreign keys
- Approximate row counts

**For file folders:**
- File names and types
- Folder structure
- File sizes
- Document metadata

This schema becomes a "map" the AI can use to navigate your data.

### Chunking

Large data needs to be broken into smaller pieces for AI processing. CGC offers three chunking strategies:

**Fixed Rows** (`rows:1000`)
- Best for: Database tables
- How it works: Splits data every N rows
- Use when: Processing structured data

**Fixed Tokens** (`tokens:2000`)
- Best for: AI processing
- How it works: Estimates token count and splits accordingly
- Use when: Feeding data to an LLM

**By Sections** (`sections`)
- Best for: Documents with structure (chapters, headings)
- How it works: Detects natural breaks in the document
- Use when: Processing reports, manuals, books

### Relationship Discovery

CGC automatically finds connections between your data:

**Foreign Keys:**
- Explicit database relationships
- Example: `orders.user_id` → `users.id`

**Naming Conventions:**
- Similar column names across tables
- Example: `user_id` in multiple tables suggests a relationship

**Value Overlap:**
- Common values between columns
- Example: Both tables have similar email addresses

### Triplet Extraction

CGC can extract structured relationships from text using a multi-stage pipeline:

**Input:**
```
"Tim Cook is the CEO of Apple. Apple is headquartered in Cupertino."
```

**Output:**
```
(Tim Cook) --[LEADS]--> (Apple)       [person → organization]   conf=0.92
(Apple) --[LOCATED_IN]--> (Cupertino) [organization → location] conf=0.90
```

This is useful for:
- Building knowledge graphs
- Understanding document content
- Finding connections mentioned in text

#### Extraction Pipeline (v0.2.0)

CGC uses a multi-stage extraction pipeline:

1. **Pattern Matching** (50+ regex patterns) - Fast, high-precision extraction for employment, location, organizational, e-commerce, financial, and technical relationships.

2. **GliNER** (`urchade/gliner_medium-v2.1`) - Neural NER with batched label sets (core, technical, business, financial). Finds entities that patterns miss.

3. **GliREL** (`jackboyla/glirel-large-v0`) - Relation extraction that uses spaCy tokenization to map entity positions and extract typed relationships between GliNER entities.

4. **E5 Domain Router** (`intfloat/e5-small-v2`) - Classifies text into one of 17 industry packs using semantic similarity, selecting domain-specific entity and relation labels for optimal extraction.

5. **Structured Extractor** - Hub-and-spoke model for tabular data. Classifies columns (primary entity, foreign key, timestamp, property) and builds relationships automatically.

6. **Semantic Constraints** - Validates that extracted relations make sense (e.g., only a `person` can `WORKS_AT` an `organization`). Normalizes labels and predicates, filters garbage entities.

#### Industry Packs

CGC includes 17 industry-specific label sets for domain-optimized extraction:

| Pack | Use Case |
|------|----------|
| `general_business` | Default for most text |
| `tech_startup` | Software, APIs, funding rounds |
| `ecommerce_retail` | Products, orders, pricing |
| `legal_corporate` | Contracts, regulations, courts |
| `finance_investment` | Securities, funds, trading |
| `hr_people` | Employees, skills, hiring |
| `healthcare_medical` | Patients, diagnoses, medications |
| `real_estate` | Properties, transactions, zoning |
| `supply_chain` | Manufacturing, shipping, procurement |
| `research_academic` | Papers, grants, journals |
| `government_public` | Agencies, legislation, permits |
| `accounting_reporting` | Financial statements, IFRS/GAAP, auditing |
| `insurance` | Policies, claims, underwriting, risk |
| `manufacturing_engineering` | BOMs, specs, quality control |
| `marketing_sales` | Campaigns, competitive analysis, pipeline |
| `energy_environment` | ESG, sustainability, carbon emissions |
| `software_engineering` | Architecture, APIs, microservices, DevOps |

#### ML Dependencies

The ML extraction components (GliNER, GliREL, E5 router) require PyTorch, spaCy, and sentence-transformers. These are optional — pattern-based extraction works without any ML dependencies. Install the full stack with:

```
pip install context-graph-connector[extraction]
```

---

## Detailed Use Cases

### Use Case 1: Database Analysis

**Scenario:** You're a business analyst who needs to understand customer behavior in your company's PostgreSQL database.

**Step 1: Connect to the database**

```
You: Connect to our PostgreSQL database. Host is db.company.com, username analytics, password [hidden], database is production.

Claude: [Uses cgc_add_source]
Connected successfully to "production" database.
```

**Step 2: Explore the structure**

```
You: What data do we have?

Claude: [Uses cgc_discover]
I found 23 tables. The main ones appear to be:

Customer Data:
- customers (45,000 rows) - customer info
- addresses (52,000 rows) - shipping addresses

Orders:
- orders (180,000 rows) - purchase history
- order_items (450,000 rows) - individual items
- payments (175,000 rows) - payment records

Products:
- products (2,500 rows) - product catalog
- categories (45 rows) - product categories
- inventory (2,500 rows) - stock levels

Would you like me to explore any of these in detail?
```

**Step 3: Ask analytical questions**

```
You: What's our customer retention like? How many customers ordered more than once?

Claude: [Uses cgc_sql to run analysis]

Here's what I found:

Total Customers: 45,000
Customers with 1 order: 28,350 (63%)
Customers with 2+ orders: 16,650 (37%)
Customers with 5+ orders: 4,230 (9%)

Average orders per customer: 4.0
Top customer: 156 orders

Your retention rate of 37% is actually above the e-commerce industry average of 25-30%.
```

**Step 4: Drill deeper**

```
You: What products do repeat customers buy most?

Claude: [Uses cgc_sql with JOIN query]

Top products among repeat customers:
1. Premium Subscription (bought by 45% of repeat customers)
2. Accessory Bundle (bought by 38%)
3. Extended Warranty (bought by 32%)

Interestingly, customers who buy the Premium Subscription have a 78% chance of ordering again, compared to 31% for other customers.
```

### Use Case 2: Document Intelligence (RAG Alternative)

**Scenario:** Your company has a knowledge base with hundreds of PDFs, and you want to find information without manually searching.

**Step 1: Connect to the documents**

```
You: Connect to our knowledge base at //fileserver/knowledgebase

Claude: [Uses cgc_add_source]
Connected to knowledge base. Found 847 files:
- 523 PDFs
- 189 Word documents
- 98 Excel spreadsheets
- 37 other files

Total size: 2.3 GB
```

**Step 2: Search semantically (with vector database)**

```
You: I need to find our policy on work-from-home arrangements.

Claude: [Uses cgc_vector_search if connected to vector DB, or cgc_search]

I found 5 relevant documents:

1. "HR_Policy_Manual_2024.pdf" (Section 4.2)
   - Detailed WFH policy with eligibility requirements

2. "Employee_Handbook.pdf" (Page 45)
   - Brief overview of flexible work arrangements

3. "IT_Security_Guidelines.pdf" (Pages 12-15)
   - VPN and security requirements for remote work

Would you like me to read any of these in detail?
```

**Step 3: Deep dive into a document**

```
You: Read the detailed WFH policy from the HR manual.

Claude: [Uses cgc_chunk to get the relevant section]

Here's Section 4.2 from the HR Policy Manual:

**Work From Home Policy**

Eligibility:
- Full-time employees after 90-day probation
- Manager approval required
- Job duties must be suitable for remote work

Expectations:
- Must be available during core hours (10 AM - 3 PM)
- Required to attend weekly team meetings
- Must have reliable internet (minimum 25 Mbps)

Equipment:
- Company provides laptop and monitor
- $500 annual stipend for home office supplies
- IT support available for setup

Want me to summarize the approval process?
```

### Use Case 3: Cross-Source Investigation

**Scenario:** You need to understand a specific customer's complete journey across multiple systems.

**Step 1: Connect all relevant sources**

```
You: Connect to our CRM database, support ticket system, and email logs.

Claude: [Uses cgc_add_source three times]
Connected to:
1. CRM (PostgreSQL) - customer and sales data
2. Support (MongoDB) - ticket history
3. Email logs (filesystem) - communication records
```

**Step 2: Find everything about a customer**

```
You: Find all information about customer ID 12345.

Claude: [Uses cgc_find_related across all sources]

**Customer 12345: Acme Corporation**

From CRM:
- Account since: March 2022
- Plan: Enterprise ($5,000/month)
- Account owner: John Smith
- Health score: 72/100 (declining)

From Support System:
- 15 tickets in last 6 months (increasing)
- 3 critical issues (2 resolved, 1 open)
- Average resolution time: 4.2 days
- Current open ticket: "API rate limiting issues"

From Email Logs:
- 47 emails exchanged
- Last contact: 3 days ago
- Sentiment trend: Becoming frustrated

🚨 Risk Assessment: This account shows signs of churn risk:
- Declining health score
- Increasing support tickets
- Frustrated communication tone
```

**Step 3: Get actionable insights**

```
You: What should we do about this customer?

Claude: Based on the data:

Immediate Actions:
1. Escalate the open API ticket - it's been open 5 days
2. Have account owner call them today
3. Consider temporary rate limit increase

Root Cause:
Their API usage grew 300% in 3 months. They're hitting limits because they're actually successful with our product. This is a good problem.

Opportunity:
Propose upgrading to Custom tier with higher limits. Their current usage justifies a $8,000/month plan.
```

### Use Case 4: Large Document Processing

**Scenario:** You need to analyze a 700-page annual report to prepare for a board meeting.

**Step 1: Connect and chunk the document**

```
You: I have a large PDF at C:\Reports\Annual_Report_2024.pdf. Help me analyze it.

Claude: [Uses cgc_add_source, then cgc_chunk]

Connected to the file. It's 743 pages with:
- Executive Summary (pages 1-15)
- Financial Statements (pages 16-89)
- Management Discussion (pages 90-245)
- Business Segments (pages 246-450)
- Risk Factors (pages 451-520)
- Appendices (pages 521-743)

I've broken it into 61 chunks for processing.
What aspects would you like me to focus on?
```

**Step 2: Extract specific information**

```
You: What are the main risk factors mentioned?

Claude: [Reads relevant chunks from pages 451-520]

Here are the top 10 risk factors by severity:

1. **Cybersecurity threats** (High)
   - Mentioned 23 times
   - New this year: AI-powered attack concerns

2. **Supply chain disruption** (High)
   - Ongoing from last year
   - Mitigation: Diversified to 3 suppliers

3. **Regulatory changes** (Medium)
   - Specific concern: EU AI Act compliance
   - $2.3M budgeted for compliance

[continues with remaining risks...]

Would you like me to compare these to last year's report?
```

**Step 3: Generate summaries**

```
You: Create a one-page summary I can use for the board meeting.

Claude: [Synthesizes key points from multiple chunks]

**2024 Annual Report Summary**

**Financial Highlights:**
- Revenue: $1.2B (+15% YoY)
- Net Income: $180M (+8% YoY)
- Operating Margin: 15% (down from 16%)

**Key Achievements:**
- Launched 3 new product lines
- Expanded to 12 new markets
- Customer base grew 25% to 50,000

**Challenges:**
- Rising operational costs
- Increased competition in core markets
- Cybersecurity investment requirements

**Outlook:**
- Projecting 10-12% revenue growth
- $50M investment in AI capabilities
- Two potential acquisitions in pipeline

**Board Action Items:**
1. Approve cybersecurity budget increase
2. Review acquisition candidates
3. Discuss margin improvement strategies
```

---

## Data Flow

Here's what happens when you use CGC:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Question                             │
│              "How many orders were placed last month?"           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AI Assistant                             │
│                   (Claude, ChatGPT, etc.)                        │
│                                                                  │
│   Decides: "I need to query the orders table with a date filter" │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                             CGC                                  │
│                                                                  │
│   1. Validates the request (security checks)                     │
│   2. Connects to the data source                                 │
│   3. Executes: SELECT COUNT(*) FROM orders                      │
│      WHERE created_at >= '2024-01-01'                           │
│   4. Returns: {"count": 1523}                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AI Assistant                             │
│                                                                  │
│   Formats answer: "There were 1,523 orders placed last month."  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Your Answer                              │
│              "There were 1,523 orders placed last month."        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture

CGC has several components:

### Adapters

Each data source type has an "adapter" that knows how to connect and query it:

- **SqlAdapter** - PostgreSQL, MySQL, SQLite
- **FilesystemAdapter** - Local files and folders
- **QdrantAdapter** - Qdrant vector database
- **PineconeAdapter** - Pinecone vector database
- **PgVectorAdapter** - PostgreSQL with pgvector
- **MongoVectorAdapter** - MongoDB Atlas

### Connector

The main coordinator that:
- Manages multiple data sources
- Routes queries to the right adapter
- Handles chunking and processing
- Discovers relationships

### Security Layer

Protects your data:
- **Authentication** - API key verification
- **Rate Limiting** - Prevents abuse
- **Input Validation** - Blocks SQL injection, path traversal
- **Query Restrictions** - Only SELECT queries allowed by default

### Interfaces

Three ways to interact with CGC:
- **CLI** - Command-line interface
- **HTTP API** - Web API for automation tools
- **MCP** - Direct AI assistant integration

---

## Supported Data Sources

### Relational Databases

| Database | Connection String Format |
|----------|-------------------------|
| PostgreSQL | `postgresql://user:pass@host:5432/db` |
| MySQL | `mysql://user:pass@host:3306/db` |
| SQLite | `/path/to/database.db` |

### File Systems

| Type | Supported Formats |
|------|-------------------|
| Documents | PDF, DOCX, DOC |
| Spreadsheets | XLSX, CSV |
| Data | JSON, XML |
| Text | TXT, MD, RST |
| Code | PY, JS, TS, and 50+ more |

### Vector Databases

| Database | Best For |
|----------|----------|
| Qdrant | Self-hosted, open source |
| Pinecone | Managed, scalable |
| pgvector | PostgreSQL users |
| MongoDB Atlas | Existing MongoDB users |

---

## Performance Considerations

### For Databases

- **Add indexes** on frequently queried columns
- **Use LIMIT** in queries when possible
- **Chunking** for large result sets

### For Files

- **Pre-chunk** large documents
- **Use sections** strategy for structured docs
- **Index with vectors** for semantic search

### For Vector Search

- **Choose appropriate top_k** (10-50 usually sufficient)
- **Use filters** to narrow search space
- **Consider hybrid search** (vector + keyword)

---

## Security Best Practices

1. **Use the secure server** for any remote access
2. **Create separate API keys** for different users/applications
3. **Set appropriate permissions** (read-only for most users)
4. **Regularly rotate** API keys
5. **Monitor access logs** for unusual activity
6. **Keep CGC updated** for security patches

---

## Next Steps

- [API Reference](API.md) - Detailed endpoint documentation
- [CLI Reference](CLI.md) - Command-line usage
- [MCP Reference](MCP.md) - AI assistant integration
