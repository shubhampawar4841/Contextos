from fastapi import APIRouter
from pydantic import BaseModel
from google import genai

from app.core.config import settings
from app.core.supabase import supabase
from app.services.embedding_service import create_embedding


router = APIRouter(
    tags=["chat"],
)

client = genai.Client(
    api_key=settings.GEMINI_API_KEY
)


class ChatRequest(BaseModel):
    question: str
    limit: int = 5


@router.post("/chat")
def chat_with_documents(body: ChatRequest):
    print(f"1. Chat question: {body.question}")

    query_embedding = create_embedding(body.question)
    print(f"2. Query embedding dimensions={len(query_embedding)}")

    response = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": body.limit,
        },
    ).execute()

    chunks = response.data or []
    print(f"3. Retrieved chunks={len(chunks)}")

    context = "\n\n".join(
        [
            f"[Chunk {chunk['chunk_index']}]\n{chunk['content']}"
            for chunk in chunks
        ]
    )

    prompt = f"""
You are answering questions using only the provided context.

If the answer is not supported by the context, say:
"I don't have enough information in the uploaded documents."

Context:
{context}

Question:
{body.question}

Answer clearly and concisely.
"""

    print("4. Generating answer with Gemini")
    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    print("5. CHAT COMPLETE")
    return {
        "question": body.question,
        "answer": result.text,
        "sources": [
            {
                "chunk_index": chunk["chunk_index"],
                "document_id": chunk["document_id"],
                "similarity": chunk["similarity"],
                "content": chunk["content"],
            }
            for chunk in chunks
        ],
    }
