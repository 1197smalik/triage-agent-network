# rag/vectorstore.py
import logging

from rag.loaders.load_docs import load_sample_docs
from rag.embedder import SimpleEmbedder
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)

class SimpleVectorStore:
    def __init__(self):
        self.docs = []
        self.embedder = SimpleEmbedder()
        self.doc_embeddings = None

    def load_sample_docs(self):
        self.docs = load_sample_docs()
        self.embedder.fit(self.docs)
        self.doc_embeddings = self.embedder.vectorizer.transform([d["text"] for d in self.docs])
        logger.info("Loaded %d sample docs into vector store.", len(self.docs))

    def retrieve_docs(self, query: str, top_k=3):
        qv = self.embedder.embed(query)
        sims = cosine_similarity(qv, self.doc_embeddings).flatten()
        idxs = np.argsort(-sims)[:top_k]
        results = []
        for i in idxs:
            results.append({"id": self.docs[i]["id"], "text": self.docs[i]["text"], "score": float(sims[i])})
        logger.info("Retrieved %d docs for query snippet: %s", len(results), (query or "")[:50])
        return results
