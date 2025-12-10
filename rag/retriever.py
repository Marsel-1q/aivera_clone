from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np

from .embeddings import get_embedding_backend

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    content: str
    score: float
    source: str | None = None
    metadata: dict | None = None


def load_metadata(path: Path) -> List[dict]:
    records: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.append(payload)
    return records


class KnowledgeRetriever:
    """Lightweight in-memory retriever based on cosine similarity."""

    def __init__(
        self,
        index_dir: Path = Path("data/rag_index"),
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        embeddings_path = index_dir / "embeddings.npy"
        metadata_path = index_dir / "records.jsonl"
        if not embeddings_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(
                f"Index not found in {index_dir}. Run build_index.py to generate embeddings first."
            )

        logger.info("Loading RAG index from %s", index_dir)
        self.embeddings = np.load(embeddings_path)
        if self.embeddings.ndim != 2:
            raise ValueError("Embeddings file must be 2D array [num_docs, dim].")
        self.metadata = load_metadata(metadata_path)
        if len(self.metadata) != self.embeddings.shape[0]:
            raise ValueError("Embeddings count does not match metadata entries.")

        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.embeddings = self.embeddings / norms
        self.backend = get_embedding_backend(embedding_model)

    def search(self, query: str, k: int = 4) -> List[RetrievalResult]:
        if not query.strip():
            return []
        query_vec = self.backend.encode([query], normalize=True)[0]
        scores = self.embeddings @ query_vec
        if k >= len(scores):
            top_indices = np.argsort(-scores)
        else:
            top_indices = np.argpartition(-scores, kth=k - 1)[:k]
            top_indices = top_indices[np.argsort(-scores[top_indices])]

        results: List[RetrievalResult] = []
        for idx in top_indices:
            meta = self.metadata[idx] if idx < len(self.metadata) else {}
            results.append(
                RetrievalResult(
                    content=meta.get("content", ""),
                    source=meta.get("source"),
                    metadata=meta.get("metadata"),
                    score=float(scores[idx]),
                )
            )
        return results

    def batch_search(self, queries: Sequence[str], k: int = 4) -> List[List[RetrievalResult]]:
        return [self.search(query, k=k) for query in queries]
