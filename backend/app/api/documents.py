import time
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.supabase import supabase
from app.services.pdf_parser import extract_pdf_text
from app.services.document_parser import parse_document
from app.services.chunking_service import chunk_document


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

BUCKET_NAME = "Rag storage"


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )

    try:
        print("1. PDF received")
        print(
            f"   filename={file.filename}, "
            f"content_type={file.content_type}"
        )
        file_bytes = await file.read()
        print(f"   bytes={len(file_bytes)}")

        if not file_bytes:
            print("ERROR: uploaded file is empty")
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        print("2. Extracting PDF text (PyMuPDF)")
        pages = extract_pdf_text(file_bytes)

        if not pages:
            print("ERROR: PyMuPDF returned 0 pages")
            raise HTTPException(
                status_code=400,
                detail="Could not extract pages from PDF",
            )

        non_empty_pages = [
            page
            for page in pages
            if page["text"].strip()
        ]

        print(
            f"   pages={len(pages)}, "
            f"text_pages={len(non_empty_pages)}"
        )

        # PyMuPDF text is only a preview — Docling is the real parser.
        # Don't block upload if pages have no extractable text layer.
        if not non_empty_pages:
            print(
                "WARNING: no readable text from PyMuPDF; "
                "continuing with Docling anyway"
            )

        print("3. Starting Docling")
        start = time.time()
        docling_result = parse_document(
            file_bytes=file_bytes,
            filename=file.filename or "document.pdf",
        )
        print(
            f"4. Docling finished "
            f"({time.time() - start:.2f}s)"
        )

        print("5. Starting chunking")
        chunks = chunk_document(docling_result["document"])
        print(f"   chunks_created={len(chunks)}")

        for chunk in chunks:
            print(
                f"\nCHUNK {chunk['chunk_index']}\n"
                f"{chunk['text'][:300]}\n"
            )

        document_id = str(uuid.uuid4())
        filename = file.filename or f"{document_id}.pdf"
        storage_path = f"documents/{document_id}/{filename}"

        title = filename
        if title.lower().endswith(".pdf"):
            title = title[:-4]

        print("6. Uploading PDF to Supabase Storage")
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": "application/pdf",
                "upsert": "false",
            },
        )

        document_data = {
            "id": document_id,
            "title": title,
            "filename": filename,
            "document_type": "pdf",
            "status": "uploaded",
            "storage_path": storage_path,
        }

        print("7. Saving document metadata")
        response = (
            supabase
            .table("documents")
            .insert(document_data)
            .execute()
        )

        saved_document = (
            response.data[0]
            if response.data
            else document_data
        )

        print("8. Saving chunks to document_chunks")
        chunk_rows = []

        for chunk in chunks:
            chunk_rows.append({
                "document_id": document_id,
                "chunk_index": chunk["chunk_index"],
                "content": chunk["text"],
            })

        if chunk_rows:
            try:
                supabase.table("document_chunks").insert(
                    chunk_rows
                ).execute()
            except Exception as e:
                print(f"ERROR saving chunks: {e}")
                raise

        print(f"Saved {len(chunk_rows)} chunks to Supabase")
        print("9. UPLOAD COMPLETE")

        return {
            "message": "Document uploaded and chunks saved",
            "document": saved_document,
            "pdf_info": {
                "total_pages": len(pages),
                "text_pages": len(non_empty_pages),
                "empty_pages": len(pages) - len(non_empty_pages),
            },
            "chunks_created": len(chunks),
            "chunks_saved": len(chunk_rows),
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"UPLOAD FAILED: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Document upload failed: {str(e)}",
        )
