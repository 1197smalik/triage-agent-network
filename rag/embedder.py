# rag/embedder.py
# placeholder embedder - for POC, we use a simple TF-IDF style vector (or random)
from sklearn.feature_extraction.text import TfidfVectorizer

class SimpleEmbedder:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()

    def fit(self, docs):
        texts = [d["text"] for d in docs]
        self.vectorizer.fit(texts)

    def embed(self, text):
        return self.vectorizer.transform([text])
