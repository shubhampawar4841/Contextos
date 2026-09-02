import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.supabase import supabase

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
        # 2. Read PDF bytes
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        # 3. Generate unique storage path
        document_id = str(uuid.uuid4())

        storage_path = f"documents/{document_id}/{file.filename}"

        # 4. Upload PDF to Supabase Storage
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": "application/pdf",
                "upsert": "false",
            },
        )

        # 5. Insert document metadata into database
        document_data = {
            "id": document_id,
            "title": file.filename.removesuffix(".pdf"),
            "filename": file.filename,
            "document_type": "pdf",
            "status": "uploaded",
            "storage_path": storage_path,
        }

        response = (
            supabase
            .table("documents")
            .insert(document_data)
            .execute()
        )

        return {
            "message": "Document uploaded successfully",
            "document": response.data[0] if response.data else document_data,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )