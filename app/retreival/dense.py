from pathlib import Path
import json

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DenseRetriever:
    def __init__(
        self,
        chunks_path: str | None = None,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        if chunks_path is None:
            chunks_path = (
                PROJECT_ROOT
                / "data"
                / "processed"
                / "policy_chunks.json"
            )

        self.chunks_path = Path(chunks_path)

        with open(self.chunks_path, "r", encoding="utf-8") as file:
            self.chunks = json.load(file)

        self.embedder = SentenceTransformer(model_name)

        texts = [chunk["text"] for chunk in self.chunks]

        embeddings = self.embedder.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype("float32")

        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    def search(self, query: str, top_k: int = 5):
        query_embedding = self.embedder.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32")

        scores, indices = self.index.search(
            query_embedding,
            min(top_k, len(self.chunks)),
        )

        results = []

        for score, index in zip(scores[0], indices[0]):
            if index < 0:
                continue

            results.append(
                {
                    "chunk": self.chunks[index],
                    "score": float(score),
                }
            )

        return results