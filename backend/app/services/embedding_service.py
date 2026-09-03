from __future__ import annotations

from sentence_transformers import SentenceTransformer

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
EMBED_BATCH_SIZE = 16
EMBED_DIM = 768

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Loading local embedding model: {EMBED_MODEL_NAME}")
        _model = SentenceTransformer(EMBED_MODEL_NAME)
        print("Local embedding model ready")
    return _model


def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed texts locally with MPNet (768-d, no API quota)."""
    if not texts:
        return []

    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def create_embedding(text: str) -> list[float]:
    return create_embeddings([text])[0]
