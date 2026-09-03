from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.supabase import supabase
from app.services.embedding_service import create_embedding
from app.services.context_service import build_unified_context
from app.services.entity_service import (
    DEFAULT_USER_ID,
    extract_entities_and_relationships,
    get_graph_context_for_entities,
)


router = APIRouter(
    prefix="/search",
    tags=["Context Search"],
)


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


@router.post("")
def search_context(body: SearchRequest):
    print(f"1. Context search: {body.query}")

    query_embedding = create_embedding(body.query)
    print(f"2. Query embedding dimensions={len(query_embedding)}")

    memory_response = supabase.rpc(
        "match_memories",
        {
            "query_embedding": query_embedding,
            "match_count": body.limit,
        },
    ).execute()

    memories = [
        memory
        for memory in (memory_response.data or [])
        if float(memory.get("similarity", 0))
        >= settings.MEMORY_SIMILARITY_THRESHOLD
    ]
    print(f"3. Relevant memories={len(memories)}")

    document_response = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": body.limit,
            "filter_document_id": None,
        },
    ).execute()

    chunks = [
        chunk
        for chunk in (document_response.data or [])
        if float(chunk.get("similarity", 0)) >= 0.60
    ]
    print(f"4. Relevant document chunks={len(chunks)}")

    knowledge = extract_entities_and_relationships(body.query)

    entity_names = [
        entity["name"]
        for entity in knowledge.get("entities", [])
        if entity.get("name")
    ]

    graph_rows = get_graph_context_for_entities(
        supabase=supabase,
        user_id=DEFAULT_USER_ID,
        entity_names=entity_names,
    )
    print(f"5. Query graph entities={entity_names}")
    print(f"6. Relevant graph relationships={len(graph_rows)}")

    context = build_unified_context(
        memories=memories,
        document_chunks=chunks,
        graph_rows=graph_rows,
    )

    print("7. CONTEXT SEARCH COMPLETE")
    return {
        "query": body.query,
        "context": context,
        "memories": memories,
        "documents": chunks,
        "relationships": graph_rows,
        "entities": knowledge.get("entities", []),
    }
