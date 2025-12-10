import os
import json
import uuid
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
try:
    import chromadb
    from chromadb.config import Settings
    from transformers import AutoTokenizer, AutoModel
except ImportError:
    chromadb = None
    AutoTokenizer = None
    AutoModel = None

class TransformerEmbeddingModel:
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2'):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.model.to(self.device)

    def mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output[0] # First element of model_output contains all token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def encode(self, sentences):
        # Tokenize sentences
        encoded_input = self.tokenizer(sentences, padding=True, truncation=True, return_tensors='pt')
        encoded_input = {k: v.to(self.device) for k, v in encoded_input.items()}

        # Compute token embeddings
        with torch.no_grad():
            model_output = self.model(**encoded_input)

        # Perform pooling
        sentence_embeddings = self.mean_pooling(model_output, encoded_input['attention_mask'])

        # Normalize embeddings
        sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)

        return sentence_embeddings.cpu().numpy()

class RAGEngine:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.client = None
        self.collection = None
        self.model = None  # encoder for queries/documents
        self.enabled = self.config_manager.get("rag.enabled", False)
        self.index_embeddings = None
        self.index_metadata = None
        self.index_dir = None
        self.embedding_model_name = self.config_manager.get("rag.embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
        
        if self.enabled:
            self.init_db()

    def init_db(self):
        base_dir = Path(__file__).resolve().parents[2]
        index_dir_cfg = self.config_manager.get("rag.index_dir", "./data/rag_index")
        if index_dir_cfg and not os.path.isabs(index_dir_cfg):
            index_dir_cfg = str((base_dir / index_dir_cfg).resolve())
        self.index_dir = Path(index_dir_cfg)

        # Try to load prebuilt index (embeddings.npy + records.jsonl)
        if self._load_prebuilt_index():
            print(f"RAG Engine loaded prebuilt index from {self.index_dir}")
            return

        # Fallback to ChromaDB for dynamic uploads (if dependencies installed)
        if chromadb is None or AutoModel is None:
            print("Warning: chromadb or transformers not installed. RAG disabled (no prebuilt index found).")
            self.enabled = False
            return

        try:
            db_path = self.config_manager.get("rag.db_path", "./data/rag")
            if db_path and not os.path.isabs(db_path):
                db_path = str((base_dir / db_path).resolve())
            os.makedirs(db_path, exist_ok=True)

            # Initialize ChromaDB
            self.client = chromadb.PersistentClient(path=db_path)

            # Initialize Embedding Model for dynamic docs
            self.model = TransformerEmbeddingModel(self.embedding_model_name)

            self.collection = self.client.get_or_create_collection(name="knowledge_base")
            print(f"RAG Engine initialized at {db_path} (dynamic storage, no prebuilt index found).")
        except Exception as e:
            print(f"Failed to initialize RAG: {e}")
            self.enabled = False

    def _load_prebuilt_index(self):
        if not self.index_dir:
            return False
        emb_path = self.index_dir / "embeddings.npy"
        meta_path = self.index_dir / "records.jsonl"
        if not emb_path.exists() or not meta_path.exists():
            return False
        try:
            self.index_embeddings = np.load(emb_path)
            with meta_path.open("r", encoding="utf-8") as f:
                self.index_metadata = [json.loads(line) for line in f if line.strip()]

            if self.index_embeddings.ndim != 2:
                raise ValueError("Embeddings must be 2D matrix.")
            if len(self.index_metadata) != self.index_embeddings.shape[0]:
                raise ValueError("Embeddings count does not match metadata entries.")

            # Normalize embeddings
            norms = np.linalg.norm(self.index_embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self.index_embeddings = self.index_embeddings / norms

            # Encoder for queries (must match the model used to create the index)
            self.model = TransformerEmbeddingModel(self.embedding_model_name)
            return True
        except Exception as e:
            print(f"Failed to load prebuilt RAG index at {self.index_dir}: {e}")
            self.index_embeddings = None
            self.index_metadata = None
            return False

    def add_document(self, text: str, metadata: dict = None):
        """
        Adds document only to dynamic Chroma store (prebuilt index is read-only).
        """
        if not self.enabled or self.collection is None or self.model is None:
            return False

        if metadata is None:
            metadata = {}

        doc_id = str(uuid.uuid4())

        try:
            embeddings = self.model.encode([text]).tolist()
            self.collection.add(
                documents=[text],
                embeddings=embeddings,
                metadatas=[metadata],
                ids=[doc_id]
            )
            return doc_id
        except Exception as e:
            print(f"Error adding document: {e}")
            return False

    def delete_document(self, doc_id: str) -> bool:
        """
        Deletes a document only from dynamic Chroma store. Prebuilt index is read-only.
        """
        if not self.enabled or self.collection is None:
            return False
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            print(f"Error deleting document {doc_id}: {e}")
            return False

    def search(self, query: str, top_k: int = 3) -> list[str]:
        if not self.enabled:
            return []

        results: list[str] = []

        # Search prebuilt index
        if self.index_embeddings is not None and self.model is not None:
            try:
                query_vec = self.model.encode([query])[0]
                if query_vec.ndim > 1:
                    query_vec = query_vec.squeeze(0)
                query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-12)
                scores = self.index_embeddings @ query_vec
                top_indices = np.argsort(-scores)[:top_k]
                for idx in top_indices:
                    meta = self.index_metadata[idx] if self.index_metadata else {}
                    results.append(str(meta.get("content", "")))
            except Exception as e:
                print(f"Error searching prebuilt RAG index: {e}")

        # Search dynamic Chroma if available
        if self.collection is not None and self.model is not None and len(results) < top_k:
            remain = top_k - len(results)
            try:
                embeddings = self.model.encode([query]).tolist()
                chroma_results = self.collection.query(
                    query_embeddings=embeddings,
                    n_results=remain
                )
                if chroma_results.get('documents'):
                    results.extend(chroma_results['documents'][0])
            except Exception as e:
                print(f"Error searching Chroma RAG: {e}")

        return results[:top_k]

    def get_all_documents(self):
        """
        Returns a list of all documents (metadata only for listing).
        This is a bit tricky with Chroma, usually you list by ID or peek.
        For MVP we might just return a count or peek first 10.
        """
        if not self.enabled:
            return []

        if self.index_metadata is not None:
            return [
                {
                    "id": f"prebuilt-{idx}",
                    "metadata": meta
                } for idx, meta in enumerate(self.index_metadata[:100])
            ]

        if self.collection is None:
            return []

        try:
            data = self.collection.get(limit=100, include=['metadatas'])
            docs = []
            for i, meta in enumerate(data['metadatas']):
                docs.append({
                    "id": data['ids'][i],
                    "metadata": meta
                })
            return docs
        except Exception as e:
            print(f"Error listing documents: {e}")
            return []
