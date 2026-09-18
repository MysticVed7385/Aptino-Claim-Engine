def format_evidence(results: list[dict]) -> list[dict]:
    evidence = []

    for result in results:
        chunk = result.get("chunk", result)

        page_number = chunk.get("page_number")

        evidence.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "text": chunk.get("text", ""),
                "page_number": page_number,
                "section": chunk.get("section"),
                "source": chunk.get("source", "policy.pdf"),
                "dense_score": result.get("dense_score"),
                "sparse_score": result.get("sparse_score"),
                "rrf_score": result.get("score"),
                "rerank_score": result.get("rerank_score"),
            }
        )

    return evidence