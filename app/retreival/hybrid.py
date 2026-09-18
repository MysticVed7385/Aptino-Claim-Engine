from pathlib import Path
import json

from app.retreival.dense import DenseRetriever
from app.retreival.sparse import SparseRetriever
from app.retreival.fusion import reciprocal_rank_fusion
from app.retreival.reranker import Reranker


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class HybridRetriever:
    def __init__(self, chunks_path: str | None = None):
        if chunks_path is None:
            chunks_path = (
                PROJECT_ROOT
                / "data"
                / "processed"
                / "policy_chunks.json"
            )

        self.chunks_path = Path(chunks_path)

        if not self.chunks_path.exists():
            raise FileNotFoundError(
                f"Policy chunks file not found: {self.chunks_path}. "
                "Run scripts/ingest_policy.py first."
            )

        with open(self.chunks_path, "r", encoding="utf-8") as file:
            self.chunks = json.load(file)

        self.dense_retriever = DenseRetriever(
            chunks_path=str(self.chunks_path)
        )

        self.sparse_retriever = SparseRetriever(
            chunks=self.chunks
        )

        self.reranker = Reranker()

    def search(
    self,
    query: str,
    top_k: int = 5,
    dense_k: int | None = None,
    sparse_k: int | None = None,
    final_k: int | None = None,
    ):
        # final_k is the final number of reranked results.
        result_limit = final_k or top_k

        dense_limit = dense_k or result_limit
        sparse_limit = sparse_k or result_limit

        dense_results = self.dense_retriever.search(
            query,
            top_k=dense_limit,
        )

        sparse_results = self.sparse_retriever.search(
            query,
            top_k=sparse_limit,
        )

        fused_results = reciprocal_rank_fusion(
            dense_results,
            sparse_results,
        )

        return self.reranker.rerank(
            query,
            fused_results,
            top_k=result_limit,
        )