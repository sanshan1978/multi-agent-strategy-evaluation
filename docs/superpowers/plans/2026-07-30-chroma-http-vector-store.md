# Chroma HTTP Vector Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run Chroma as a Docker service with data on D drive and make it the
active vector backend for the Qwen-powered RAG pipeline.

**Architecture:** Extend the existing Chroma adapter with explicit persistent
and HTTP modes. Settings and vector-store factories pass connection parameters
to the adapter, while Docker Compose runs a pinned Chroma server and persists
its `/data` directory to D drive.

**Tech Stack:** Python 3.11, chromadb 1.5.9, Docker Compose, Chroma HttpClient,
Qwen `qwen3.7-text-embedding`, pytest

## Global Constraints

- Persist Chroma server data at
  `D:\BaiduNetdiskDownload\message_talk_chroma_data`.
- Map Chroma to host port `8001`; FastAPI remains on host port `8000`.
- Pin both Python client and Docker server to Chroma `1.5.9`.
- Keep the existing persistent mode for isolated tests and offline development.
- Do not expose or write the DashScope API key.
- Use the project virtual environment at `.venv`; install with
  `--no-cache-dir`.
- The project directory is not a Git repository, so commit steps are replaced
  by verification checkpoints.

---

### Task 1: Chroma Runtime Settings

**Files:**

- Modify: `settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**

- Produces: `AppSettings.chroma_mode: str`
- Produces: `AppSettings.chroma_host: str`
- Produces: `AppSettings.chroma_port: int`
- Produces: `AppSettings.chroma_ssl: bool`

- [ ] **Step 1: Write the failing settings tests**

Add the four environment names to the default cleanup list and assert:

```python
assert settings.chroma_mode == "persistent"
assert settings.chroma_host == "localhost"
assert settings.chroma_port == 8000
assert settings.chroma_ssl is False
```

Add an environment override test:

```python
def test_settings_support_chroma_http_options(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_MODE", "http")
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_HOST", "localhost")
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_PORT", "8001")
    monkeypatch.setenv("MESSAGE_TALK_CHROMA_SSL", "true")

    settings = get_settings()

    assert settings.chroma_mode == "http"
    assert settings.chroma_host == "localhost"
    assert settings.chroma_port == 8001
    assert settings.chroma_ssl is True
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_settings.py -q
```

Expected: failure because the four `AppSettings` attributes do not exist.

- [ ] **Step 3: Implement settings**

Add defaults:

```python
DEFAULT_CHROMA_MODE = "persistent"
DEFAULT_CHROMA_HOST = "localhost"
DEFAULT_CHROMA_PORT = 8000
DEFAULT_CHROMA_SSL = False
```

Add the four fields to `AppSettings` and populate them in `get_settings` with
`_first_env`, `_read_positive_int`, and `_read_bool`.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 command. Expected: all `tests/test_settings.py` tests pass.

- [ ] **Step 5: Checkpoint**

Re-read the settings diff and verify that no API key value is printed or stored.

### Task 2: HTTP-Capable Chroma Adapter

**Files:**

- Modify: `rag/vector_store.py`
- Test: `tests/test_vector_store.py`

**Interfaces:**

- Consumes: Chroma mode, host, port, SSL, persistent directory, collection
- Produces:
  `ChromaVectorStore(persist_directory, collection, mode, host, port, ssl)`
- Produces: `ChromaVectorStore.stats()` with `mode` and `endpoint`

- [ ] **Step 1: Write failing HTTP client and failure tests**

Use a fake `chromadb` module to verify:

```python
store = ChromaVectorStore(
    persist_directory=tmp_path / "unused",
    collection="test",
    mode="http",
    host="localhost",
    port=8001,
    ssl=False,
)
assert store.stats()["mode"] == "http"
assert store.stats()["endpoint"] == "http://localhost:8001"
```

The fake client must record `HttpClient(host="localhost", port=8001,
ssl=False)`, return a heartbeat, and expose a collection. Add a second test
whose heartbeat raises `ConnectionError("offline")` and assert a
`RuntimeError` containing `http://localhost:8001` but no credential.

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_vector_store.py -q
```

Expected: failure because `ChromaVectorStore` does not accept HTTP connection
arguments.

- [ ] **Step 3: Implement client selection**

Normalize and validate mode:

```python
normalized_mode = mode.strip().lower()
if normalized_mode not in {"persistent", "http"}:
    raise ValueError(f"unsupported Chroma mode: {mode}")
```

For persistent mode, create the directory and use:

```python
chromadb.PersistentClient(path=str(persist_directory))
```

For HTTP mode, use:

```python
chromadb.HttpClient(host=host, port=port, ssl=ssl)
```

Call `heartbeat()` before collection creation. Wrap connection failures in a
`RuntimeError` that identifies the mode and endpoint. Update search evidence
and stats so persistent mode reports its path and HTTP mode reports its
endpoint.

- [ ] **Step 4: Verify GREEN and regressions**

Run the Task 2 command. Expected: SQLite, persistent Chroma, and HTTP Chroma
tests all pass.

- [ ] **Step 5: Checkpoint**

Confirm unchanged documents still skip embedding and stale documents are still
deleted.

### Task 3: Wire Settings Through Runtime and Index CLI

**Files:**

- Modify: `rag/retriever.py`
- Modify: `scripts/build_rag_index.py`
- Test: `tests/test_rag.py`
- Test: `tests/test_vector_store.py`

**Interfaces:**

- Consumes: Task 1 Chroma settings
- Calls: Task 2 `ChromaVectorStore` constructor
- Produces CLI options:
  `--chroma-mode`, `--chroma-host`, `--chroma-port`, `--chroma-ssl`

- [ ] **Step 1: Write failing factory tests**

Update the existing local Chroma RAG test to set:

```python
monkeypatch.setenv("MESSAGE_TALK_CHROMA_MODE", "persistent")
```

Add a factory test with a fake `ChromaVectorStore` constructor and assert that
HTTP mode receives:

```python
{
    "mode": "http",
    "host": "localhost",
    "port": 8001,
    "ssl": False,
}
```

Add a CLI parser test proving the four arguments are accepted.

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rag.py tests/test_vector_store.py -q
```

Expected: failure because runtime and CLI factories do not pass HTTP settings.

- [ ] **Step 3: Implement runtime wiring**

Extend both `_create_vector_store` functions with:

```python
chroma_mode: str = "persistent"
chroma_host: str = "localhost"
chroma_port: int = 8000
chroma_ssl: bool = False
```

Pass these values into `ChromaVectorStore`. In `KnowledgeRetriever.default`,
use the corresponding `AppSettings` values. In the index script, let CLI
arguments override settings.

- [ ] **Step 4: Verify GREEN**

Run the Task 3 command. Expected: all selected tests pass.

- [ ] **Step 5: Checkpoint**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\build_rag_index.py --help
```

Expected: all four Chroma connection arguments are documented.

### Task 4: Reproducible Dependency and Docker Deployment

**Files:**

- Modify: `requirements.txt`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Interfaces:**

- Chroma host endpoint: `localhost:8001`
- Compose endpoint: `chroma:8000`
- Persistent mount:
  `D:/BaiduNetdiskDownload/message_talk_chroma_data:/data`

- [ ] **Step 1: Pin and install the Python client**

Change:

```text
chromadb>=1.0,<2
```

to:

```text
chromadb==1.5.9
```

Install into the D-drive virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-cache-dir chromadb==1.5.9
```

Expected: `pip show chromadb` reports version `1.5.9` and a location under the
project `.venv`.

- [ ] **Step 2: Configure Docker Compose**

Add a `chroma` service using `chromadb/chroma:1.5.9`, map `8001:8000`, mount
the required D-drive directory at `/data`, and add:

```yaml
healthcheck:
  test:
    - CMD
    - /bin/sh
    - -c
    - "wget -qO- http://localhost:8000/api/v2/heartbeat >/dev/null || exit 1"
```

Configure `message-talk` for `MESSAGE_TALK_VECTOR_STORE=chroma`,
`MESSAGE_TALK_CHROMA_MODE=http`, host `chroma`, port `8000`, and
`depends_on.chroma.condition=service_healthy`.

- [ ] **Step 3: Validate Compose**

Run:

```powershell
docker compose config
```

Expected: exit code 0, both services present, Chroma port `8001`, and D-drive
bind mount resolved.

- [ ] **Step 4: Update environment template**

Document both profiles:

```text
MESSAGE_TALK_CHROMA_MODE=http
MESSAGE_TALK_CHROMA_HOST=localhost
MESSAGE_TALK_CHROMA_PORT=8001
MESSAGE_TALK_CHROMA_SSL=false
```

- [ ] **Step 5: Checkpoint**

Confirm the Dockerfile has no SQLite-only vector-store environment defaults
that override Compose.

### Task 5: Live Chroma Migration and Verification

**Files:**

- Modify: `README.md`
- Modify: `TESTING.md`
- Modify: `OPTIMIZATION_LOG.md`
- Runtime data:
  `D:\BaiduNetdiskDownload\message_talk_chroma_data`

**Interfaces:**

- Uses: DashScope key from the existing user environment
- Uses: Qwen embedding configuration already stored in user environment
- Produces: Chroma collection `tactical_knowledge_qwen_free`

- [ ] **Step 1: Start Docker Desktop if required**

Check:

```powershell
docker info
```

If the daemon is unavailable, start the existing Docker Desktop installation
and wait until `docker info` succeeds. Do not reinstall Docker.

- [ ] **Step 2: Start Chroma and verify health**

Run:

```powershell
docker compose up -d chroma
docker compose ps
Invoke-RestMethod http://localhost:8001/api/v2/heartbeat
```

Expected: the Chroma service is healthy and heartbeat returns a numeric
nanosecond timestamp.

- [ ] **Step 3: Configure the Windows user profile**

Set only non-secret user variables:

```text
MESSAGE_TALK_VECTOR_STORE=chroma
MESSAGE_TALK_VECTOR_COLLECTION=tactical_knowledge_qwen_free
MESSAGE_TALK_CHROMA_MODE=http
MESSAGE_TALK_CHROMA_HOST=localhost
MESSAGE_TALK_CHROMA_PORT=8001
MESSAGE_TALK_CHROMA_SSL=false
```

Keep `DASHSCOPE_API_KEY` unchanged and never print its value.

- [ ] **Step 4: Build the real Qwen index**

Load existing user variables into the current process, then run:

```powershell
.\.venv\Scripts\python.exe scripts\build_rag_index.py --strict
```

Expected: provider `openai-compatible`, model
`qwen3.7-text-embedding`, dimensions `1024`, store `chroma`, collection
`tactical_knowledge_qwen_free`, and document count `7`.

- [ ] **Step 5: Run verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe rag_evaluation.py
.\.venv\Scripts\python.exe -m py_compile settings.py rag\vector_store.py rag\retriever.py scripts\build_rag_index.py
docker compose config
docker compose ps
```

Expected: full pytest suite passes; RAG evaluation reports all five cases
passing; compilation and Compose validation exit 0; Chroma is healthy.

- [ ] **Step 6: Document verified results**

Update `README.md`, `TESTING.md`, and `OPTIMIZATION_LOG.md` with the exact
commands, collection count, retrieval metrics, changed files, and technologies.
Do not claim a metric that was not freshly observed.
