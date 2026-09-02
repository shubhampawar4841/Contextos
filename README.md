# ContextOS

Backend API for uploading and parsing PDF documents (early stage).

## Stack

- **FastAPI** — API server
- **PyMuPDF** — extract text from PDF pages
- **Docling** — parse PDF structure into markdown
- **Supabase** — store PDFs and document metadata

## What's built

- `GET /health` — health check
- `POST /documents/upload` — upload a PDF, extract text, parse with Docling, save to Supabase storage + `documents` table

## Project layout

```
backend/
  app/
    main.py              # FastAPI app
    api/documents.py     # upload endpoint
    core/                # config + Supabase client
    services/
      pdf_parser.py      # page text extraction
      document_parser.py # Docling markdown conversion
```

## Run

```bash
cd backend

# Windows (Git Bash)
source .venv/Scripts/activate

# macOS / Linux
# source .venv/bin/activate

python -m uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs
