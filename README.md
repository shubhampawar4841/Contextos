# ContextOS

Persistent AI context layer: chat over PDFs with hybrid retrieval, long-term memory that supersedes itself, and a focused knowledge graph — plus an evaluation page that shows real retrieval numbers.

## What it does

- **Ingest PDFs** — Docling parse → chunk → local MPNet embeddings → Supabase / pgvector
- **Chat with evidence** — answer first, then passages / memories / graph relationships in a Context Inspector
- **Long-term memory** — semantic + episodic extraction; similar memories get **superseded**, not duplicated
- **Knowledge graph** — entity/relationship extraction; explore with search, filters, hop depth (no full-graph dump)
- **Hybrid retrieval** — dense (MPNet) + lexical (Postgres FTS) → Reciprocal Rank Fusion → optional cross-encoder rerank
- **Evaluation UI** — published Recall@1 / MRR / latency for Vector vs Hybrid vs Hybrid+Reranker
- **MCP** — `search_context` tool for agents (Claude, etc.)

## Stack

| Layer | Choice |
| --- | --- |
| API | FastAPI |
| PDF | Docling + PyMuPDF |
| Embeddings | `sentence-transformers/all-mpnet-base-v2` (local, 768-d) |
| Lexical search | Postgres `ts_rank` / `websearch_to_tsquery` |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (eval / optional) |
| LLM | Groq (chat, memory, entities, contextual chunk drafts) |
| Data | Supabase (storage, documents, chunks, memories, graph) |
| Frontend | TanStack Start + React + Tailwind (`frontend/`) |
| Graph UI | React Flow (focused exploration) |
| Agents | MCP Streamable HTTP (`mcp_server.py`) |

## Current retrieval benchmark

From `python -m app.evals.retrieval_eval` (9-query Psychology of Money set):

| Strategy | R@1 | R@5 | R@10 | MRR | Latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vector | 77.8% | 100% | 100% | 88.9% | ~738ms |
| Hybrid RRF | **88.9%** | 100% | 100% | **94.4%** | ~863ms |
| Hybrid + Reranker | 88.9% | 100% | 100% | 94.4% | ~3144ms |

**Finding:** Hybrid improved Recall@1 (77.8% → 88.9%). The cross-encoder raised latency without improving aggregate metrics on this set. Treat as engineering evidence, not production accuracy — see **Evaluation** in the UI.

## Run backend

```bash
cd backend

# Windows (Git Bash)
source .venv/Scripts/activate

# macOS / Linux
# source .venv/bin/activate

# Full local stack (PDF upload + Docling + chat) — default
python -m uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000 · Docs: http://127.0.0.1:8000/docs

`backend/.env`:

```env
SUPABASE_URL=...
SUPABASE_SECRET_KEY=...
GROQ_API_KEY=...
APP_MODE=full
# GEMINI_API_KEY optional — embeddings are local MPNet now
```

### App modes

| Mode | Env | PDF ingest | Docling / OCR / PyMuPDF | Chat / search |
| --- | --- | --- | --- | --- |
| **full** (local) | `APP_MODE=full` | yes | loaded when upload runs | yes |
| **retrieval** (Render) | `APP_MODE=retrieval` | no (503) | never imported | yes |

Local install (everything):

```bash
pip install -r requirements.txt
```

Render / API-only install:

```bash
pip install -r requirements-api.txt
```

**Embeddings:** Query vectors still use local `all-mpnet-base-v2` so they match Supabase chunks. That means **torch + sentence-transformers stay in `requirements-api.txt`**. Do not swap embedding models without re-embedding all chunks. Cross-encoder reranker is **not** on the Render path (eval/local only).

Useful Supabase SQL (run once in SQL Editor):

- `backend/app/evals/search_document_chunks_fts.sql` — FTS / BM25-style RPC
- `backend/app/evals/add_contextual_content_column.sql` — optional `contextual_content` column

## Deploy on Render (retrieval API)

Free tier is tight (512 MB). Use retrieval mode so Docling/OCR never load.

**Build Command**

```bash
pip install -r requirements-api.txt
```

**Start Command**

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Environment variables**

```env
APP_MODE=retrieval
SUPABASE_URL=...
SUPABASE_SECRET_KEY=...
GROQ_API_KEY=...
MEMORY_SIMILARITY_THRESHOLD=0.60
CORS_ORIGINS=https://your-frontend.example.com
```

Root directory: `backend`

**Unavailable on Render:** PDF upload / Docling / OCR / re-indexing. Ingest locally with `APP_MODE=full`, then point the frontend at the Render API for chat.

**Memory caveat:** First chat request loads MPNet (~torch). On 512 MB this can still OOM; if it does, move query embeddings to a small always-on worker later — do **not** change the model without re-embedding.

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually http://localhost:3000).

Set API base if needed (`frontend/.env`):

```env
VITE_CONTEXTOS_API_URL=http://127.0.0.1:8000
```

### UI routes

| Route | Purpose |
| --- | --- |
| Overview | Status / pipeline snapshot |
| Chat | Context Chat + demo questions + inspector |
| Memories | Active vs superseded memory history |
| Documents | Upload / status |
| Knowledge Graph | Focused React Flow exploration |
| Evaluation | Retrieval ablation results |
| Connections | API + MCP |
| Settings | Workspace / keys notes |

## Retrieval evaluation (CLI)

```bash
cd backend
source .venv/Scripts/activate
python -m app.evals.retrieval_eval
```

Compares:

1. Pure vector (`match_document_chunks`)
2. Hybrid vector + lexical RRF
3. Hybrid + cross-encoder rerank

Dataset: `backend/app/evals/dataset.json`

## Run MCP server

Keep FastAPI on `:8000`, then:

```bash
cd backend
source .venv/Scripts/activate
python mcp_server.py
```

MCP: http://127.0.0.1:8001/mcp  

Expose with `ngrok http 8001` for Claude. Tool: `search_context` → `POST /search`.

## Project layout

```text
backend/
  requirements.txt      # full local (Docling + torch + …)
  requirements-api.txt  # Render retrieval-only
  app/
    main.py             # APP_MODE gates ingest router
    api/
      documents.py         # list/delete (light)
      documents_ingest.py  # PDF upload (full mode only)
      chat.py / search.py / …
    services/      # Docling, chunking, embeddings, retrieval, …
    evals/
  mcp_server.py
frontend/
```

## Design notes (product)

- **Chat** — answer first; evidence summary; Inspect for passages / memories / relationships; Graph for structure
- **Graph** — never render the full graph by default; search + 1/2-hop focus
- **Memory** — updates supersede older facts (`status` + `superseded_by`)
- **Embeddings** — re-ingest docs after switching models; don’t mix Gemini + MPNet vectors in one index
