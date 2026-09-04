from app.core.supabase import supabase
from app.services.embedding_service import create_embedding
from app.services.retrieval_service import CHUNK_SIMILARITY_THRESHOLD


def retrieve_vector_chunks(
    question: str,
    limit: int = 10,
    document_id: str | None = None,
) -> list[dict]:
    """Pure dense retrieval baseline — no keyword fallback."""
    query_embedding = create_embedding(question)

    response = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": limit,
            "filter_document_id": document_id,
        },
    ).execute()

    chunks = []

    for chunk in response.data or []:
        similarity = float(chunk.get("similarity", 0))

        if similarity >= CHUNK_SIMILARITY_THRESHOLD:
            chunks.append(chunk)

    return chunks


if __name__ == "__main__":
    question = "What did Ronald Read invest his money in?"

    chunks = retrieve_vector_chunks(
        question,
        limit=10,
    )

    print(f"\nQuestion: {question}")
    print(f"Retrieved: {len(chunks)} chunks\n")

    for rank, chunk in enumerate(chunks, start=1):
        print(
            f"{rank}. "
            f"sim={float(chunk['similarity']):.4f} "
            f"page={chunk.get('page_start')} "
            f"doc={chunk.get('document_title')}"
        )
        print(chunk["content"][:250])
        print()
