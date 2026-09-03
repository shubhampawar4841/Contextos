# ContextOS

Chat with your PDFs using RAG, long-term memory, and a knowledge graph.

## Stack

- **FastAPI** — API server
- **Docling** — PDF parse + chunking
- **Gemini** — embeddings (`768` dims)
- **Groq** — chat / memory / entity extraction
- **Supabase** — storage, documents, chunks, memories, graph
- **Vanilla HTML + D3** — frontend UI

## Run backend

```bash
cd backend

# Windows (Git Bash)
source .venv/Scripts/activate

# macOS / Linux
# source .venv/bin/activate

python -m uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000  
Docs: http://127.0.0.1:8000/docs

Make sure `backend/.env` has:

```env
SUPABASE_URL=...
SUPABASE_SECRET_KEY=...
GEMINI_API_KEY=...
GROQ_API_KEY=...
```

## Run frontend (HTML)

In a **second terminal**:

```bash
cd frontend
python -m http.server 5500
```

Open: http://localhost:5500

Do **not** open `index.html` by double-clicking it — serve it with the command above so it can talk to the API (CORS is set for `http://localhost:5500`).

## Run MCP server

Keep the FastAPI backend running, then in another terminal:

```bash
cd backend
source .venv/Scripts/activate   # Windows Git Bash
mcp dev mcp_server.py
```

This exposes one tool: `search_context` → `POST /search`.

## What you can do in the UI

- Upload PDFs
- Chat with RAG + memory + knowledge graph
- Browse chats / documents
- Open **Context** and **Knowledge Graph**

## Project layout

```
backend/
  app/
    main.py
    api/          # documents, chat, sessions, context, search
    services/     # parsing, chunking, embeddings, memory, entities
frontend/
  index.html      # chat UI + context + D3 graph
```
