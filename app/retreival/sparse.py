from rank_bm25 import BM25Okapi


class SparseRetriever:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks

        tokenized_documents = [
            chunk["text"].lower().split()
            for chunk in chunks
        ]

        self.bm25 = BM25Okapi(tokenized_documents)

    def search(self, query: str, top_k: int = 5):
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:top_k]

        return [
            {
                "chunk": self.chunks[index],
                "score": float(scores[index]),
            }
            for index in ranked_indices
        ]