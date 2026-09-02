from docling.chunking import HybridChunker


def chunk_document(docling_document):
    chunker = HybridChunker()

    chunks = list(
        chunker.chunk(dl_doc=docling_document)
    )

    results = []

    for index, chunk in enumerate(chunks):
        results.append(
            {
                "chunk_index": index,
                "text": chunk.text,
            }
        )

    return results
