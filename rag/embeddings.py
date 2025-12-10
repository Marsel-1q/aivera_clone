from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable, List

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingBackend:
    """Thin wrapper around a sentence-transformers style model."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "sentence-transformers is required for embedding generation. "
                "Install via `pip install sentence-transformers`."
            ) from exc

        self.model_name = model_name
        logger.info("Loading embedding model %s", model_name)
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = int(getattr(self.model, "get_sentence_embedding_dimension", lambda: 0)())

    def encode(self, texts: Iterable[str], normalize: bool = True) -> np.ndarray:
        texts_list: List[str] = [text if isinstance(text, str) else str(text) for text in texts]
        if not texts_list:
            dim = self.embedding_dim or 0
            return np.empty((0, dim), dtype=np.float32)
        embeddings = self.model.encode(
            texts_list,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            show_progress_bar=True,
        )
        if not normalize:
            return embeddings.astype(np.float32)
        return embeddings


@lru_cache(maxsize=2)
def get_embedding_backend(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> EmbeddingBackend:
    return EmbeddingBackend(model_name=model_name)
