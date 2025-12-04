# rag_simple.py
import logging
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)

KB_DIR = Path("kb")

def _load_kb_texts():
    docs = []
    ids = []
    if not KB_DIR.exists():
        logger.warning("KB directory %s not found; using synthetic defaults.", KB_DIR)
        # provide synthetic default docs
        docs = [
            "Collision within policy term is covered unless deliberate damage.",
            "Minimum 3 photos: overall, close-up of damage, license plate.",
            "If severity_score > 0.6 escalate to adjuster."
        ]
        ids = ["policy_dummy.txt","photo_dummy.txt","triage_dummy.txt"]
    else:
        for p in sorted(KB_DIR.glob("*")):
            ids.append(p.name)
            docs.append(p.read_text(encoding="utf-8", errors="ignore"))
    return ids, docs

KB_IDS, KB_DOCS = _load_kb_texts()
VECT = TfidfVectorizer().fit(KB_DOCS)
DOC_EMB = VECT.transform(KB_DOCS)
logger.info("RAG simple loaded %d docs; TF-IDF vectorizer initialized.", len(KB_DOCS))

def retrieve_relevant_snips(query: str, top_k: int = 3):
    if not query:
        logger.info("Empty query provided; returning default snippets.")
        return KB_DOCS[:top_k]
    qv = VECT.transform([query])
    sims = cosine_similarity(qv, DOC_EMB).flatten()
    idxs = np.argsort(-sims)[:top_k]
    snips = [KB_DOCS[i] for i in idxs]
    logger.info("Retrieved %d snippets for query '%s...'", len(snips), (query or "")[:40])
    return snips
