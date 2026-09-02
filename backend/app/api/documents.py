import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.supabase import supabase
from app.services.pdf_parser import extract_pdf_text


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

BUCKET_NAME = "Rag storage"


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    # 1. Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )

    try:
        # 2. Read uploaded PDF bytes
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        # 3. Extract PDF text
        pages = extract_pdf_text(file_bytes)

        if not pages:
            raise HTTPException(
                status_code=400,
                detail="Could not extract pages from PDF",
            )

        # 4. Find non-empty text pages
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
                    "could be extracted. The PDF may be scanned/image-based."
                ),
            )

        # 5. Generate unique document ID
        document_id = str(uuid.uuid4())

        # 6. Build safe storage path
        filename = file.filename or f"{document_id}.pdf"

        storage_path = (
            f"documents/{document_id}/{filename}"
        )

        # 7. Upload original PDF to Supabase Storage
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": "application/pdf",
                "upsert": "false",
            },
        )

        # 8. Prepare document metadata
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

        # 9. Insert metadata into documents table
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

        # 10. Return useful PDF information
        return {
            "message": "Document uploaded successfully",
            "document": saved_document,
            "pdf_info": {
                "total_pages": len(pages),
                "text_pages": len(non_empty_pages),
                "empty_pages": (
                    len(pages) - len(non_empty_pages)
                ),
                "first_text_page": (
                    non_empty_pages[0]["page_number"]
                ),
                "preview": non_empty_pages[:3],
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Document upload failed: {str(e)}",
        )