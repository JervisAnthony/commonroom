# ADR 0003: Primary Datastore and Vector Retrieval Strategy

## Status
Accepted

## Context
The **Commonroom** ecosystem requires persistent storage for both structured relational domains and unstructured semantic embeddings:
- **Structured Domains**: User identities, house point ledgers, quiz question banks, exam histories, friend relationships, consent logs, geofence definitions, and canonical citation metadata.
- **Unstructured / Semantic Retrieval**: Pensieve requires vector embeddings and similarity search over lawfully usable structured lore metadata, original summaries, citation records, permitted source material, and current news content to power its AI companion and RAG (Retrieval-Augmented Generation) pipeline.

Introducing multiple disparate database engines early in a project creates unnecessary operational overhead, distributed transaction challenges, and dual-write synchronization complexity.

---

## Decision

We establish **PostgreSQL** as the unified primary structured datastore and **PostgreSQL with the `pgvector` extension** as Pensieve's retrieval baseline:

1. **Primary Structured Datastore**:
   - **PostgreSQL** is the standard relational database for all Commonroom products.
   - Provides ACID transactions, relational integrity, mature indexing, JSON/JSONB support, and robust tooling.
2. **Pensieve Vector Retrieval Baseline**:
   - Pensieve will utilize the **`pgvector`** extension in PostgreSQL for storing embeddings and executing similarity queries.
   - The specific indexing strategy (e.g., HNSW, IVFFlat, or exact search where appropriate) will be selected based on measured dataset size and query latency requirements during implementation.
   - Keeps vector embeddings co-located with structured document metadata (such as canonical tiering, chapter citations, and ingestion timestamps) within a single datastore.
3. **Infrastructure Boundary**:
   - We do not mandate standalone vector databases (e.g., Pinecone, Qdrant, Milvus), caching layers (e.g., Redis), or NoSQL databases (e.g., MongoDB) as mandatory baseline infrastructure.
   - Specialized stores may be introduced in future commits through dedicated ADRs only when measured operational scale or retrieval characteristics justify them.

---

## Consequences

### Positive
- **Operational Simplicity**: A single database engine to deploy, configure, backup, and monitor across local development and production environments.
- **Transactional Consistency**: Transactional storage reduces synchronization risk and permits metadata and vector records to be committed atomically where the ingestion workflow supports it.
- **Hybrid Relational-Vector Querying**: Enables SQL queries that combine vector similarity filtering with structured relational clauses (e.g., filter lore embeddings where `canonical_tier = 'book_canon'`).

### Trade-offs
- While `pgvector` scales effectively across expected initial lore datasets, high-throughput vector search across massive collections may eventually warrant a dedicated vector search engine at higher product maturity.

---

## Alternatives Considered

1. **MongoDB / Document Databases**:
   - *Rationale for Non-Selection*: Document stores lack the rigid relational integrity, foreign keys, and transactional guarantees essential for financial-style house point ledgers, strict friend consent graphs, and quiz scoring.
2. **Standalone Vector Database (e.g., Pinecone, Qdrant, Weaviate) from Day 1**:
   - *Rationale for Non-Selection*: Adds an extra distributed service, separate authentication, and dual-write synchronization overhead before data volume justifies the operational burden.
3. **Firebase / Supabase as Architecture**:
   - *Rationale for Non-Selection*: Supabase and Firebase are hosting/platform providers rather than portable database technologies. Our architecture specifies standard PostgreSQL so it remains fully portable across hosting environments (including Supabase, managed cloud PostgreSQL, or containerized instances).
4. **Multiple Specialized Databases from Day 1**:
   - *Rationale for Non-Selection*: Prematurely introducing separate relational, key-value, document, and vector databases multiplies infrastructure complexity without architectural necessity.

