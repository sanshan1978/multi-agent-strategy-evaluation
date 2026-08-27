# Chroma HTTP Vector Store Design

## Goal

Replace the project's active SQLite vector index with a self-hosted Chroma
service while preserving the existing `VectorStore` abstraction, Qwen
embedding pipeline, hybrid retrieval behavior, trace evidence, and local test
path.

## Scope

This change covers:

- a single-node Chroma server managed by Docker Compose;
- Chroma data persisted under
  `D:\BaiduNetdiskDownload\message_talk_chroma_data`;
- a Python `chromadb.HttpClient` connection from the host and application
  container;
- Qwen `qwen3.7-text-embedding` vectors stored in Chroma;
- automated configuration, adapter, index, retrieval, and failure tests;
- documentation and optimization-log updates.

This change does not add distributed Chroma, Chroma Cloud, authentication,
replication, or a second embedding model.

## Chosen Approach

Use `chromadb/chroma:1.5.9` as a separate Docker service and connect through
`chromadb.HttpClient`.

The alternatives considered were:

1. Embedded `PersistentClient`: smallest operational footprint, but the
   database lifecycle remains coupled to the FastAPI process.
2. Docker Chroma Server plus `HttpClient`: selected because it demonstrates
   service separation, persistent storage, health checking, and realistic
   deployment configuration without unnecessary infrastructure.
3. Chroma Cloud: omitted because it introduces an external account and cost
   without improving the current internship-project story.

## Architecture

The existing retrieval path remains:

```text
Qwen Embedding
    -> ChromaVectorStore
    -> Chroma HTTP Server
    -> HNSW cosine collection
    -> Dense Retrieval
    -> BM25 + Dense + Scene Signal
    -> RRF Fusion
    -> Rerank
    -> Retrieval Trace / Evaluation
```

`ChromaVectorStore` continues to implement the same public operations:

- `upsert_documents`
- `search`
- `stats`

The store will support two explicit client modes:

- `persistent`: use `chromadb.PersistentClient` for isolated tests and offline
  development;
- `http`: use `chromadb.HttpClient` for the configured Docker service.

No retrieval caller should need to know which mode is active.

## Configuration

The following settings will be added:

```text
MESSAGE_TALK_CHROMA_MODE=http
MESSAGE_TALK_CHROMA_HOST=localhost
MESSAGE_TALK_CHROMA_PORT=8001
MESSAGE_TALK_CHROMA_SSL=false
```

The active host profile will use:

```text
MESSAGE_TALK_VECTOR_STORE=chroma
MESSAGE_TALK_VECTOR_COLLECTION=tactical_knowledge_qwen_free
MESSAGE_TALK_CHROMA_MODE=http
MESSAGE_TALK_CHROMA_HOST=localhost
MESSAGE_TALK_CHROMA_PORT=8001
```

Inside Docker Compose, the application will override the host profile with:

```text
MESSAGE_TALK_CHROMA_HOST=chroma
MESSAGE_TALK_CHROMA_PORT=8000
```

`MESSAGE_TALK_VECTOR_DB_PATH` remains meaningful only for `persistent` mode.
Existing SQLite configuration remains supported as an explicit fallback.

## Docker Deployment

Docker Compose will define:

- `chroma`, using `chromadb/chroma:1.5.9`;
- host port `8001` mapped to container port `8000`;
- bind mount
  `D:/BaiduNetdiskDownload/message_talk_chroma_data:/data`;
- a heartbeat health check against `/api/v2/heartbeat`;
- `message-talk` depending on a healthy Chroma service.

FastAPI continues to use host port `8000`, so no port collision is introduced.
Destructive reset operations remain disabled.

## Data Model and Indexing

The existing document identity and idempotent update behavior remain:

- record ID: `source::title`;
- content hash detects changed text;
- metadata stores source, title, content hash, serialized chunk metadata,
  embedding provider, model, and dimensions;
- unchanged chunks are skipped;
- stale chunks are deleted when replacing a collection.

The collection uses cosine distance. The active index contains 1024-dimensional
vectors from `qwen3.7-text-embedding`. Existing SQLite vectors are not copied
byte-for-byte; the normal ingestion pipeline rebuilds the Chroma collection
from source documents to ensure metadata and embedding configuration are
consistent.

## Failure Handling

- Missing `chromadb` raises a configuration-oriented `RuntimeError`.
- Unreachable HTTP server raises a Chroma connection error during client
  heartbeat or collection initialization.
- Strict RAG mode must fail fast instead of silently switching to local hashing
  or SQLite.
- The error message must include the selected Chroma mode and endpoint but must
  not include API keys.
- Docker health checks distinguish an unavailable vector service from an
  unhealthy FastAPI application.

## Testing

Tests will be added or updated in this order:

1. settings tests for Chroma mode, host, port, and SSL parsing;
2. adapter tests using an injected Chroma-compatible client to verify HTTP
   client selection without requiring Docker;
3. existing persistent-client tests for indexing, idempotency, stale cleanup,
   metadata recovery, and search;
4. factory tests proving application and index CLI settings reach the store;
5. Docker Compose configuration validation;
6. live Chroma heartbeat, Qwen index build, dense retrieval, and RAG evaluation.

Completion evidence requires:

- the full pytest suite passing;
- `docker compose config` succeeding;
- Chroma reporting a healthy heartbeat;
- the Qwen collection containing the expected seven chunks;
- a known dense query returning the expected knowledge title;
- RAG evaluation metrics being recorded after switching to Chroma.

## Documentation

Update:

- `.env.example` with local-host and Compose profiles;
- `README.md` with startup, index build, and verification commands;
- `TESTING.md` with Chroma integration checks;
- `OPTIMIZATION_LOG.md` with changed files, technologies, verification results,
  and project value.

## Sources

- Chroma Docker deployment:
  https://docs.trychroma.com/deployment/docker
- Chroma client-server mode:
  https://docs.trychroma.com/production/chroma-server/client-server-mode
- Chroma release 1.5.9:
  https://github.com/chroma-core/chroma/releases/tag/1.5.9
