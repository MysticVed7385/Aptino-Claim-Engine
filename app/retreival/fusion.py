from collections import defaultdict


def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """
    Combine dense and sparse retrieval results using
    Reciprocal Rank Fusion (RRF).

    Each input result must have this structure:

    {
        "chunk": {
            "chunk_id": "...",
            "text": "...",
            "page_number": 1,
            "section": "...",
            "source": "policy.pdf"
        },
        "score": 0.85
    }
    """

    fused_scores = defaultdict(float)
    chunks_by_id = {}

    # Process dense retrieval results.
    for rank, result in enumerate(dense_results, start=1):
        chunk = result["chunk"]
        chunk_id = chunk["chunk_id"]

        fused_scores[chunk_id] += 1 / (k + rank)
        chunks_by_id[chunk_id] = chunk

    # Process sparse/BM25 retrieval results.
    for rank, result in enumerate(sparse_results, start=1):
        chunk = result["chunk"]
        chunk_id = chunk["chunk_id"]

        fused_scores[chunk_id] += 1 / (k + rank)
        chunks_by_id[chunk_id] = chunk

    # Sort chunks by their combined RRF score.
    ranked_chunk_ids = sorted(
        fused_scores.keys(),
        key=lambda chunk_id: fused_scores[chunk_id],
        reverse=True,
    )

    # Return the same wrapped format expected by the reranker.
    fused_results = []

    for chunk_id in ranked_chunk_ids:
        fused_results.append(
            {
                "chunk": chunks_by_id[chunk_id],
                "score": fused_scores[chunk_id],
            }
        )

    return fused_results