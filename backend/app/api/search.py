from fastapi import APIRouter
from pydantic import BaseModel

from app.services.embedding_service import create_embedding
from app.core.supabase import supabase


router = APIRouter(
    tags=["search"],
)


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


@router.post("/search")
def semantic_search(body: SearchRequest):
    print(f"1. Search query: {body.query}")
    query_embedding = create_embedding(body.query)
    print(f"2. Query embedding dimensions={len(query_embedding)}")

    response = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": body.limit,
        },
    ).execute()

    print(f"3. Matches returned={len(response.data or [])}")

    return {
        "query": body.query,
        "results": response.data,
    }
