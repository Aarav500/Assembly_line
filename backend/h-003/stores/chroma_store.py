from typing import List, Dict, Any
import chromadb


class ChromaVectorStore:
    def __init__(self, persist_directory: str, metric: str = "cosine"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.metric = metric

    def _collection(self, name: str):
        metadata = {"hnsw:space": self.metric}
        return self.client.get_or_create_collection(name=name, metadata=metadata)

    def upsert(
        self,
        collection: str,
        ids: List[str],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: List[List[float]],
        embedding_dim: int,
    ) -> int:
        col = self._collection(collection)
        col.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
        return len(ids)

    def query(self, collection: str, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        col = self._collection(collection)
        res = col.query(query_embeddings=[query_embedding], n_results=top_k)
        results = []
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i, _id in enumerate(ids or []):
            results.append({
                "id": _id,
                "text": docs[i] if i < len(docs) else None,
                "metadata": metas[i] if i < len(metas) else None,
                "score": dists[i] if i < len(dists) else None,
            })
        return results

    def reset_collection(self, collection: str) -> None:
        try:
            self.client.delete_collection(name=collection)
        except Exception:
            pass

