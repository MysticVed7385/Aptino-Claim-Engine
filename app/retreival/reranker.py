from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ):
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int = 5,
    ):
        if not results:
            return []

        pairs = []

        for result in results:
            chunk = result["chunk"]

            if isinstance(chunk, dict):
                text = chunk.get("text", "")
            else:
                text = getattr(chunk, "text", "")

            pairs.append((query, text))

        scores = self.model.predict(pairs)

        reranked = []

        for result, score in zip(results, scores):
            updated_result = dict(result)
            updated_result["rerank_score"] = float(score)
            reranked.append(updated_result)

        reranked.sort(
            key=lambda item: item["rerank_score"],
            reverse=True,
        )

        return reranked[:top_k]
# class Reranker:
#     """
#     Lightweight fallback reranker.
#     Uses the existing retrieval score instead of loading
#     a separate cross-encoder model.
#     """

#     def rerank(self, query, results, top_k=5):
#         ranked_results = sorted(
#             results,
#             key=lambda item: item.get("score", 0.0),
#             reverse=True,
#         )

#         return ranked_results[:top_k]