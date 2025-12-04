# rag/embedder.py
# placeholder embedder - for POC, we use a simple TF-IDF style vector (or random)
import logging
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

class SimpleEmbedder:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()

    def fit(self, docs):
        texts = [d["text"] for d in docs]
        self.vectorizer.fit(texts)
        logger.info("TF-IDF embedder fitted on %d docs.", len(texts))

    def embed(self, text):
        logger.debug("Embedding text snippet len=%d", len(text))
        return self.vectorizer.transform([text])
