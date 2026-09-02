from fastapi import APIRouter
from pydantic import BaseModel

from app.core.supabase import supabase
from app.services.embedding_service import create_embedding
from app.services.llm_service import generate_text
from app.services.memory_service import (
    extract_memories,
    is_duplicate_memory,
)


router = APIRouter(
    tags=["chat"],
)


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None
    document_id: str | None = None
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

    memories = extract_memories(body.question)

    existing_response = (
        supabase.table("memories")
        .select("content, memory_type")
        .eq("session_id", session_id)
        .execute()
    )
    existing_memories = existing_response.data or []

    saved_memories = []
    for memory in memories:
        if is_duplicate_memory(
            memory["content"],
            existing_memories,
        ):
            print(f"Skipping exact duplicate: {memory['content']}")
            continue

        memory_embedding = create_embedding(memory["content"])

        similar = supabase.rpc(
            "match_memories",
            {
                "query_embedding": memory_embedding,
                "match_count": 3,
            },
        ).execute()

        matches = similar.data or []
        is_semantic_duplicate = any(
            float(match["similarity"]) >= 0.90
            for match in matches
        )

        if is_semantic_duplicate:
            print(
                f"Skipping semantic duplicate: "
                f"{memory['content']}"
            )
            continue

        supabase.table("memories").insert({
            "session_id": session_id,
            "memory_type": memory["memory_type"],
            "content": memory["content"],
            "embedding": memory_embedding,
        }).execute()

        existing_memories.append(memory)
        saved_memories.append(memory)

    print(f"3. Extracted {len(memories)} memories, saved {len(saved_memories)}")
    for memory in saved_memories:
        print(f"   [{memory['memory_type']}] {memory['content']}")

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
    print(f"4. History messages={len(history)}")

    query_embedding = create_embedding(body.question)
    print(f"5. Query embedding dimensions={len(query_embedding)}")

    memory_response = supabase.rpc(
        "match_memories",
        {
            "query_embedding": query_embedding,
            "match_count": 5,
        },
    ).execute()

    stored_memories = memory_response.data or []
    memory_text = "\n".join(
        f"- {memory['content']}"
        for memory in stored_memories
    )
    print(f"6. Relevant memories={len(stored_memories)}")
    for memory in stored_memories:
        print(
            f"   [{memory.get('memory_type')}] "
            f"sim={float(memory['similarity']):.4f} "
            f"{memory['content']}"
        )

    response = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": body.limit,
            "filter_document_id": body.document_id,
        },
    ).execute()

    chunks = response.data or []
    print(f"7. Retrieved chunks={len(chunks)}")

    context = "\n\n".join(
        [
            f"[Chunk {chunk['chunk_index']}]\n{chunk['content']}"
            for chunk in chunks
        ]
    )

    prompt = f"""
You are answering the user using:
1. relevant uploaded-document context
2. conversation history
3. long-term memories about the user

Long-term memories:
{memory_text}

Conversation history:
{history_text}

Document context:
{context}

Current question:
{body.question}

Instructions:
- Use memories to personalize how you answer.
- Use document context as the source of truth for document-related facts.
- If the user prefers a certain response style, follow it.
- If the answer is not supported by the documents when documents are required, say:
  "I don't have enough information in the uploaded documents."

Do not mention chunk numbers.
Answer clearly.
"""

    print("8. Generating answer with Groq")
    answer = generate_text(prompt)

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
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "similarity": round(float(chunk["similarity"]), 4),
            "preview": (
                chunk["content"][:180] + "..."
                if len(chunk["content"]) > 180
                else chunk["content"]
            ),
        }
        for chunk in chunks
    ]

    print("9. CHAT COMPLETE")
    return {
        "session_id": session_id,
        "question": body.question,
        "answer": answer,
        "memories_extracted": memories,
        "memories_saved": saved_memories,
        "memories_used": stored_memories,
        "sources": sources,
    }
