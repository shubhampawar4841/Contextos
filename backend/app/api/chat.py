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
    session_id: str | None = None
    limit: int = 5


@router.post("/chat")
def chat_with_documents(body: ChatRequest):
    print(f"1. Chat question: {body.question}")

    session_id = body.session_id

    if not session_id:
        session = supabase.table("chat_sessions").insert({
            "title": body.question[:80],
        }).execute()
        session_id = session.data[0]["id"]
        print(f"2. Created session_id={session_id}")
    else:
        print(f"2. Using session_id={session_id}")

    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "role": "user",
        "content": body.question,
    }).execute()

    history_response = (
        supabase.table("chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    history = list(reversed(history_response.data or []))
    history_text = "\n".join(
        f"{msg['role']}: {msg['content']}"
        for msg in history
    )
    print(f"3. History messages={len(history)}")

    query_embedding = create_embedding(body.question)
    print(f"4. Query embedding dimensions={len(query_embedding)}")

    response = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": body.limit,
        },
    ).execute()

    chunks = response.data or []
    print(f"5. Retrieved chunks={len(chunks)}")

    context = "\n\n".join(
        [
            f"[Chunk {chunk['chunk_index']}]\n{chunk['content']}"
            for chunk in chunks
        ]
    )

    prompt = f"""
You are answering questions using the uploaded documents and conversation history.

Conversation:
{history_text}

Document context:
{context}

Current question:
{body.question}

Use the document context as the source of truth.
Use conversation history only to understand follow-up questions.

If the answer is not supported by the documents, say:
"I don't have enough information in the uploaded documents."

Answer clearly and concisely.
"""

    print("6. Generating answer with Gemini")
    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    answer = result.text

    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "role": "assistant",
        "content": answer,
    }).execute()

    sources = [
        {
            "document": chunk.get("document_title"),
            "document_id": chunk["document_id"],
            "chunk_index": chunk["chunk_index"],
            "similarity": round(float(chunk["similarity"]), 4),
            "preview": (
                chunk["content"][:180] + "..."
                if len(chunk["content"]) > 180
                else chunk["content"]
            ),
        }
        for chunk in chunks
    ]

    print("7. CHAT COMPLETE")
    return {
        "session_id": session_id,
        "question": body.question,
        "answer": answer,
        "sources": sources,
    }
