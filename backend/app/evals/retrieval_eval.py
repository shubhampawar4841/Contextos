from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.supabase import supabase
from app.services.embedding_service import create_embedding
from app.services.retrieval_service import CHUNK_SIMILARITY_THRESHOLD


DATASET_PATH = Path(__file__).parent / "dataset.json"


def retrieve_vector_chunks(
    question: str,
    limit: int = 10,
    document_id: str | None = None,
) -> list[dict]:
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


def load_dataset() -> list[dict]:
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def chunk_matches_expected(chunk: dict, item: dict) -> bool:
    content = (chunk.get("content") or "").lower()

    expected_terms = [
        term.lower()
        for term in item.get("expected_terms", [])
    ]

    term_match = all(
        term in content
        for term in expected_terms
    )

    if not term_match:
        return False

    expected_pages = item.get("expected_pages")

    if not expected_pages:
        return True

    page_start = chunk.get("page_start")
    page_end = chunk.get("page_end") or page_start

    if page_start is None:
        return False

    return any(
        page_start <= page <= page_end
        for page in expected_pages
    )


def find_first_relevant_rank(
    chunks: list[dict],
    item: dict,
) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        if chunk_matches_expected(chunk, item):
            return rank

    return None


def main():
    dataset = load_dataset()

    recall_at_1_hits = 0
    recall_at_5_hits = 0
    recall_at_10_hits = 0

    reciprocal_rank_sum = 0.0
    total_latency_ms = 0.0

    print("\nContextOS Retrieval Evaluation")
    print("==============================")
    print(f"Queries: {len(dataset)}")
    print("\nVECTOR BASELINE\n")

    for item in dataset:
        question = item["question"]

        start = time.perf_counter()

        chunks = retrieve_vector_chunks(
            question=question,
            limit=10,
        )

        latency_ms = (
            time.perf_counter() - start
        ) * 1000

        total_latency_ms += latency_ms

        rank = find_first_relevant_rank(
            chunks,
            item,
        )

        if rank is None:
            print("\n  TOP RETRIEVED CHUNKS:")

            for i, chunk in enumerate(chunks, start=1):
                content = (chunk.get("content") or "").replace("\n", " ")

                print(
                    f"  {i}. "
                    f"sim={float(chunk.get('similarity', 0)):.4f} "
                    f"doc={chunk.get('document_title')} "
                    f"page={chunk.get('page_start')}"
                )
                print(f"     {content[:220]}")

        if rank is not None:
            if rank <= 1:
                recall_at_1_hits += 1

            if rank <= 5:
                recall_at_5_hits += 1

            if rank <= 10:
                recall_at_10_hits += 1

            reciprocal_rank_sum += 1 / rank

        rank_display = rank if rank is not None else "MISS"

        print(
            f"[{item['id']}] "
            f"rank={rank_display} "
            f"latency={latency_ms:.1f}ms"
        )
        print(f"  {question}")

    total = len(dataset)

    recall_at_1 = recall_at_1_hits / total
    recall_at_5 = recall_at_5_hits / total
    recall_at_10 = recall_at_10_hits / total
    mrr = reciprocal_rank_sum / total
    avg_latency = total_latency_ms / total

    print("\nRESULTS")
    print("-------")
    print(f"Recall@1:  {recall_at_1:.4f}")
    print(f"Recall@5:  {recall_at_5:.4f}")
    print(f"Recall@10: {recall_at_10:.4f}")
    print(f"MRR:       {mrr:.4f}")
    print(f"Avg latency: {avg_latency:.2f} ms")


if __name__ == "__main__":
    main()