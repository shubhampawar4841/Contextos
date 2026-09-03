import time
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.supabase import supabase
from app.services.pdf_parser import extract_pdf_text
from app.services.document_parser import parse_document
from app.services.chunking_service import chunk_document
from app.services.embedding_service import create_embedding
from app.services.entity_service import (
    DEFAULT_USER_ID,
    extract_entities_and_relationships,
    save_knowledge,
)


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

BUCKET_NAME = "Rag storage"


@router.get("")
def list_documents():
    try:
        response = (
            supabase
            .table("documents")
            .select(
                "id, title, filename, document_type, status, created_at"
            )
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "documents": response.data or []
        }

    except Exception as e:
        print(f"LIST DOCUMENTS FAILED: {e}")

        raise HTTPException(
            status_code=500,
            detail=f"Could not load documents: {str(e)}",
        )


@router.delete("/{document_id}")
def delete_document(document_id: str):
    try:
        response = (
            supabase
            .table("documents")
            .select("storage_path")
            .eq("id", document_id)
            .single()
            .execute()
        )

        document = response.data

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        storage_path = document.get("storage_path")

        if storage_path:
            supabase.storage.from_(BUCKET_NAME).remove([
                storage_path
            ])

        supabase.table("documents").delete().eq(
            "id",
            document_id,
        ).execute()

        return {
            "message": "Document deleted successfully"
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"DELETE DOCUMENT FAILED: {e}")

        raise HTTPException(
            status_code=500,
            detail=f"Could not delete document: {str(e)}",
        )


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )

    document_id = None

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

        document_id = str(uuid.uuid4())
        filename = file.filename or f"{document_id}.pdf"
        storage_path = f"documents/{document_id}/{filename}"

        title = filename
        if title.lower().endswith(".pdf"):
            title = title[:-4]

        print("2. Uploading PDF to Supabase Storage")
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
            "status": "processing",
            "storage_path": storage_path,
        }

        print("3. Saving document as processing")
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

        print("4. Extracting PDF text (PyMuPDF)")
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

        if not non_empty_pages:
            print(
                "WARNING: no readable text from PyMuPDF; "
                "continuing with Docling anyway"
            )

        print("5. Starting Docling")
        start = time.time()
        docling_result = parse_document(
            file_bytes=file_bytes,
            filename=filename,
        )
        print(
            f"6. Docling finished "
            f"({time.time() - start:.2f}s)"
        )

        print("7. Starting chunking")
        chunks = chunk_document(docling_result["document"])
        print(f"   chunks_created={len(chunks)}")

        for chunk in chunks:
            print(
                f"\nCHUNK {chunk['chunk_index']} "
                f"PAGES {chunk['page_start']}-{chunk['page_end']}\n"
                f"{chunk['text'][:300]}\n"
            )

        print("8. Creating embeddings + saving chunks")
        chunk_rows = []

        for chunk in chunks:
            embedding = create_embedding(chunk["text"])

            print(
                f"Chunk {chunk['chunk_index']} "
                f"embedding dimensions={len(embedding)}"
            )

            chunk_rows.append({
                "document_id": document_id,
                "chunk_index": chunk["chunk_index"],
                "content": chunk["text"],
                "embedding": embedding,
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
            })

        if chunk_rows:
            supabase.table("document_chunks").insert(
                chunk_rows
            ).execute()

        print(f"Saved {len(chunk_rows)} chunks + embeddings")

        print("9. Extracting document knowledge")
        total_entities = 0
        total_relationships = 0

        for chunk in chunks:
            text = chunk["text"].strip()

            if len(text) < 100:
                continue

            try:
                knowledge = extract_entities_and_relationships(text)

                save_result = save_knowledge(
                    supabase=supabase,
                    user_id=DEFAULT_USER_ID,
                    knowledge=knowledge,
                    source_type="document",
                    source_document_id=document_id,
                    source_page=chunk.get("page_start"),
                )

                total_entities += save_result["entities_saved"]
                total_relationships += save_result["relationships_saved"]

                print(
                    f"   chunk {chunk['chunk_index']} "
                    f"entities={save_result['entities_saved']} "
                    f"relationships={save_result['relationships_saved']}"
                )
            except Exception as e:
                print(
                    f"   chunk {chunk['chunk_index']} "
                    f"knowledge extraction failed: {e}"
                )

        print(
            f"Document knowledge saved: "
            f"entities={total_entities}, "
            f"relationships={total_relationships}"
        )

        print("10. Marking document ready")
        ready_response = (
            supabase
            .table("documents")
            .update({"status": "ready"})
            .eq("id", document_id)
            .execute()
        )

        if ready_response.data:
            saved_document = ready_response.data[0]
        else:
            saved_document = {
                **saved_document,
                "status": "ready",
            }

        print("11. UPLOAD COMPLETE")
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
            "knowledge_entities_saved": total_entities,
            "knowledge_relationships_saved": total_relationships,
        }

    except HTTPException as e:
        if document_id:
            try:
                supabase.table("documents").update({
                    "status": "failed"
                }).eq("id", document_id).execute()
            except Exception:
                pass
        raise e

    except Exception as e:
        print(f"UPLOAD FAILED: {e}")

        if document_id:
            try:
                supabase.table("documents").update({
                    "status": "failed"
                }).eq("id", document_id).execute()
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"Document upload failed: {str(e)}",
        )
