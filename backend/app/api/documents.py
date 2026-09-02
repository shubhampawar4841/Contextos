import time
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.supabase import supabase
from app.services.pdf_parser import extract_pdf_text
from app.services.document_parser import parse_document


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
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        print("2. Extracting PDF text (PyMuPDF)")
        pages = extract_pdf_text(file_bytes)

        if not pages:
            raise HTTPException(
                status_code=400,
                detail="Could not extract pages from PDF",
            )

        non_empty_pages = [
            page
            for page in pages
            if page["text"].strip()
        ]

        if not non_empty_pages:
            raise HTTPException(
                status_code=400,
                detail=(
                    "PDF pages were detected, but no readable text "
                    "could be extracted."
                ),
            )

        print(
            f"   pages={len(pages)}, "
            f"text_pages={len(non_empty_pages)}"
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

        docling_markdown = docling_result["markdown"]

        document_id = str(uuid.uuid4())
        filename = file.filename or f"{document_id}.pdf"
        storage_path = f"documents/{document_id}/{filename}"

        print("5. Uploading PDF to Supabase Storage")
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": "application/pdf",
                "upsert": "false",
            },
        )

        title = filename
        if title.lower().endswith(".pdf"):
            title = title[:-4]

        document_data = {
            "id": document_id,
            "title": title,
            "filename": filename,
            "document_type": "pdf",
            "status": "uploaded",
            "storage_path": storage_path,
        }

        print("6. Saving document metadata")
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

        print("7. UPLOAD COMPLETE")
        return {
            "message": "Document uploaded successfully",
            "document": saved_document,
            "pdf_info": {
                "total_pages": len(pages),
                "text_pages": len(non_empty_pages),
                "empty_pages": len(pages) - len(non_empty_pages),
                "first_text_page": non_empty_pages[0]["page_number"],
                "preview": non_empty_pages[:3],
            },
            "docling_info": {
                "markdown_length": len(docling_markdown),
                "markdown_preview": docling_markdown[:5000],
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Document upload failed: {str(e)}",
        )
