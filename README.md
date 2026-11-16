# MTS EnergyTool - AI Energy Consultant

An AI-powered consultant for MTS EnergyTool clients. The system answers customer inquiries strictly from a curated energy knowledge base, profiles every stage of the RAG pipeline, automatically generates conversation summaries, and forwards it to the operator dashboard.

---

## Table of Contents

- [Architecture & Services](#architecture--services)
- [How the RAG Pipeline Works](#how-the-rag-pipeline-works)
  - [1. Knowledge Base Ingestion](#1-knowledge-base-ingestion)
  - [2. Hybrid Retrieval & Context Expansion](#2-hybrid-retrieval--context-expansion)
  - [3. Response Generation & Lead Handoff](#3-response-generation--lead-handoff)
  - [4. Async Summarization & Profiling](#4-async-summarization--profiling)
- [Repository Structure](#repository-structure)
- [Getting Started from Scratch](#getting-started-from-scratch)
  - [Prerequisites](#prerequisites)
  - [Step 1. Configure `.env` & Start Local Models (`llama-server`)](#step-1-configure-env--start-local-models-llama-server)
  - [Step 2. Start Docker Services](#step-2-start-docker-services)
  - [Step 3. Prepare Data & Ingest the Knowledge Base into Qdrant](#step-3-prepare-data--ingest-the-knowledge-base-into-qdrant)
  - [Step 4. Verify the Deployment](#step-4-verify-the-deployment)
- [Development & Debugging](#development--debugging)

---

## Architecture & Services

The system runs as five Docker Compose services backed by local `llama-server` inference processes:

| Component | Stack | Port | Responsibility |
| --- | --- | --- | --- |
| `frontend` | Vanilla JS + Nginx | `3000` (`:80`) | Client chat UI (`/`) and Operator Dashboard (`/operator.html`); proxies `/api/` to `web-app` |
| `web-app` | Go (`gorilla/mux`, PostgreSQL + Goose) | `8090` (`:8080`) | Chat lifecycle, message/chunk/profiler persistence, lead capture, and operator analytics |
| `ai-service` | FastAPI + LlamaIndex / Qdrant Client | `8000` | RAG completions (`/completions`), dialog summarization (`/summarize`), document lookup (`/documents/{doc_id}`) |
| `postgres` | PostgreSQL 16 | `5432` | Stores chats, messages (`sources`, `profiler`), leads, and dialog summaries |
| `qdrant` | Qdrant | `6333` / `6334` | Hybrid vector database (dense + sparse vectors) |
| Model Servers | `llama.cpp` (`llama-server`) | `8080`, `8081`, `8082` | Local OpenAI-compatible inference for LLM, Embeddings, and Reranker |

---

## How the RAG Pipeline Works

### 1. Knowledge Base Ingestion

`services/ai-service/scripts/ingest_kb.py` prepares Markdown files from `data/knowledge-base/` and indexes them into Qdrant:

1. **Loading (`kb/loader.py`)** — reads `.md` files deterministically from a directory or `.zip` archive and normalizes relative paths.
2. **Cleaning (`kb/cleaner.py`)** — normalizes line breaks and strips escaped headings and formatting artifacts.
3. **Table Linearization (`kb/linearizer.py`)** — converts plain-text Markdown tables into linearized text so embeddings and LLMs preserve row-column relationships.
4. **Structural Chunking (`rag/chunker.py` + `rag/section_rules.json`)** — splits documents along Markdown heading hierarchies (`h1..h6`), preserving `section_path` and classifying `section_type` (including `RESTRICTION` and `REQUIREMENTS`).
5. **Hybrid Indexing (`core/embeddings.py`, `core/qdrant.py`)** — stores two vector representations per chunk:
   - **Dense vector** via the local embedding server (port `8081`, `1024` dimensions),
   - **Sparse vector** for exact keyword and terminology matching.

### 2. Hybrid Retrieval & Context Expansion

Implemented in `services/ai-service/src/rag/retriever.py` (`retrieve`):

1. **Query Embedding (`embedding_time`)** — cleans the incoming query and computes its dense embedding.
2. **Hybrid Qdrant Search with RRF (`db_search_time`)** — runs dense and sparse prefetch queries (`limit = RAG_TOP_K`, default `15`) and merges candidates using **Reciprocal Rank Fusion (RRF)**.
3. **Cross-Encoder Reranking (`reranking_time`)** — scores retrieved chunks via the reranker server (port `8082`) and keeps the top `RRK_TOP_N` (default `5`).
4. **Context Expansion (`_expand_chunks`)** — automatically fetches missing `RESTRICTION` and `REQUIREMENTS` chunks from the top matched documents (`EXPAND_TOP_DOCS`, `EXPAND_LIMIT_PER_DOC`) so key constraints and caveats are included in the prompt.

### 3. Response Generation & Lead Handoff

Implemented in `services/ai-service/src/rag/pipeline.py` (`run_rag_pipeline`):

1. Retrieved chunks are formatted with file paths and section headers (`_format_context`).
2. `ConsultantPrompt.format_prompt` assembles the prompt from the context, user query, and current dialog summary.
3. `generate_response` calls the local LLM with dialog history and `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`.
4. If the model emits `ConsultantPrompt.LEAD_MARKER`, it is stripped from the user-facing text and `ready_for_lead=true` is returned so the frontend displays the contact form.

### 4. Async Summarization & Profiling

- `services/web/internal/service/chat.go` stores each assistant reply together with its retrieved `sources` and `profiler` timings (`embedding_time`, `db_search_time`, `reranking_time`, `generation_time`, `rag_time`) in PostgreSQL.
- In parallel, an async goroutine calls `/summarize` on `ai-service`, updates the chat summary, and records `summarizer_time` on the assistant message.
- The Operator Dashboard (`frontend/operator.html`) displays:
  - per-chat average metrics (`Эмбеддинг`, `Поиск в Qdrant`, `Реранжирование`, `Генерация LLM`, `RAG пайплайн`, `Суммаризатор`),
  - per-message profiler badges and clickable knowledge-base chunks beneath every assistant message,
  - submitted lead details and the latest bot-generated summary.

---

## Repository Structure

```text
.
├── data/
│   └── knowledge-base/          # Markdown KB (00-reference, 10-energy, 20-products)
├── frontend/
│   ├── index.html               # Client chat interface
│   ├── operator.html            # Operator dashboard
│   ├── nginx.conf               # Static hosting + /api/ reverse proxy to web-app:8080
│   └── src/
│       ├── api/client.js        # Backend HTTP client
│       ├── data/starters.js     # Pool of 56 starter prompts (4 random picked per new chat)
│       ├── state/sessions.js    # LocalStorage session store & server sync
│       ├── ui/render.js         # Message, chunk-bar, modal, and debug panel rendering
│       ├── main.js              # Client chat entrypoint
│       └── operator.js          # Operator dashboard & chat stats rendering
├── services/
│   ├── ai-service/
│   │   ├── models/              # GGUF model files (LLM, Embedding, Reranker)
│   │   ├── scripts/
│   │   │   ├── serve_llama.py   # Launches 3 llama-server processes from .env
│   │   │   └── ingest_kb.py     # Ingests data/knowledge-base into Qdrant
│   │   ├── src/
│   │   │   ├── api/v1/chat.py   # FastAPI endpoints (/completions, /summarize, /documents/{doc_id})
│   │   │   ├── kb/              # KB loader, cleaner, table linearizer
│   │   │   ├── rag/             # Chunker, retriever, prompts, RAG pipeline
│   │   │   └── summarization/   # Dialog summarization pipeline
│   │   ├── .env.example         # Environment variable template
│   │   └── pyproject.toml       # Python dependencies & Ruff configuration
│   └── web/
│       ├── cmd/web/main.go      # Go HTTP server entrypoint (:8080)
│       ├── internal/            # HTTP handlers, chat service, PostgreSQL repositories
│       └── migrations/          # Goose SQL migrations (auto-applied on startup)
└── docker-compose.yml           # Orchestrates qdrant, postgres, web-app, ai-service, frontend
```

---

## Getting Started from Scratch

### Prerequisites

- **Docker** & **Docker Compose**
- **llama.cpp** (`llama-server` available in `PATH`)
- **Python 3.12+** & **uv**
- **Knowledge base archive / Markdown files** (the `data/` folder is gitignored and must be populated locally)
- **GGUF models** placed inside `services/ai-service/models/` (gitignored; for example: `Qwen3.5-4B-UD-Q6_K_XL.gguf` or `Qwen3.5-9B-Q4_K_M.gguf`, `bge-m3-Q6_K.gguf`, and `bge-reranker-v2-m3-Q6_K.gguf`)

### Step 1. Configure `.env` & Start Local Models (`llama-server`)

1. Copy the environment template:
   ```bash
   cp services/ai-service/.env.example services/ai-service/.env
   ```
2. Set the model filenames from `services/ai-service/models/` in `services/ai-service/.env` (for example, in development we use):
   ```env
   LLM_MODEL=Qwen3.5-4B-UD-Q6_K_XL.gguf
   EMB_MODEL=bge-m3-Q6_K.gguf
   RRK_MODEL=bge-reranker-v2-m3-Q6_K.gguf

   LLM_URL=http://127.0.0.1:8080/v1
   EMB_URL=http://127.0.0.1:8081/v1
   RRK_URL=http://127.0.0.1:8082/v1
   ```
   > **Docker & LAN note:** `docker-compose.yml` configures `ai-service` to reach the host via `http://host.docker.internal:8080..8082/v1`. If you serve models from another machine on your LAN, bind `llama-server` to `0.0.0.0` and point those URLs to the host's LAN IP.
3. Start all three model servers:
   ```bash
   cd services/ai-service
   python3 scripts/serve_llama.py
   ```
   This starts:
   - LLM on port `8080` (`-c ${LLM_CONTEXT_WINDOW}`),
   - Embedding server on port `8081` (`--embedding`),
   - Reranker server on port `8082` (`--reranking`).

### Step 2. Start Docker Services

From the repository root, build and launch all containers:

```bash
docker compose up -d --build
```

On startup:
- `qdrant` (`:6333`) and `postgres` (`:5432`) initialize storage,
- `web-app` (`:8090`) automatically applies Goose migrations from `services/web/migrations/`,
- `ai-service` (`:8000`) connects to Qdrant and the local `llama-server` endpoints,
- `frontend` (`:3000`) serves the UI and proxies `/api/` to `web-app`.

### Step 3. Prepare Data & Ingest the Knowledge Base into Qdrant

Because `data/` is excluded from Git (`.gitignore`), create the folder at the repository root and unpack the knowledge-base Markdown files into `data/knowledge-base/` first:

```bash
mkdir -p data/knowledge-base
unzip path/to/knowledge-base.zip -d data/knowledge-base
```

Once `qdrant` and the embedding server (`8081`) are running, index the knowledge base:

```bash
cd services/ai-service
uv sync
uv run python -m scripts.ingest_kb --data-dir ../../data/knowledge-base --recreate
```

*(You can also pass the `.zip` archive directly via `--data-dir ../../data/knowledge-base.zip`. Use `--recreate` whenever `.md` knowledge base files or chunking rules are updated.)*

### Step 4. Verify the Deployment

- **Client Chat UI:** `http://localhost:3000`
- **Operator Dashboard:** `http://localhost:3000/operator.html`
- **AI Service Health Check:** `http://localhost:8000/health`
- **Qdrant Dashboard:** `http://localhost:6333/dashboard`

---

## Development & Debugging

- **Rebuild specific services after changes:**
  ```bash
  docker compose up -d --build --no-deps web-app frontend
  # or for ai-service:
  docker compose up -d --build --no-deps ai-service
  ```
- **Inspect container logs:**
  ```bash
  docker logs -f go_chat_app
  docker logs -f ai_service
  ```
- **Run Python linter (`ruff`) in `ai-service`:**
  ```bash
  cd services/ai-service
  uv run python scripts/check_ruff.py
  ```
- **Mock mode (without running LLMs):** set `MOCK_MODE=True` in `services/ai-service/.env` and/or `USE_MOCK = true` in `frontend/src/api/client.js`.
