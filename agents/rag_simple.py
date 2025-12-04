# rag_simple.py
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from schemas.claims import FNOL

logger = logging.getLogger(__name__)

KB_TEXT_DIR = Path("knowledge_base")
KB_JSON_DIR = Path("knowledge_base/json")


def _json_chunks_from_file(p: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return [{
            "id": p.name,
            "text": p.read_text(encoding="utf-8", errors="ignore"),
            "meta": {"source": p.name}
        }]
    chunks = []
    if isinstance(data, list):
        for idx, item in enumerate(data):
            rid = item.get("rule_id") if isinstance(item, dict) else None
            chunks.append({
                "id": rid or f"{p.stem}-{idx}",
                "text": json.dumps(item, ensure_ascii=False, indent=2),
                "meta": {"source": p.name, "rule_id": rid}
            })
    elif isinstance(data, dict):
        for key, val in data.items():
            chunks.append({
                "id": f"{p.stem}-{key}",
                "text": json.dumps({key: val}, ensure_ascii=False, indent=2),
                "meta": {"source": p.name, "section": key}
            })
    else:
        chunks.append({
            "id": p.name,
            "text": json.dumps(data, ensure_ascii=False, indent=2),
            "meta": {"source": p.name}
        })
    return chunks


def _load_kb_chunks():
    chunks = []
    if not KB_TEXT_DIR.exists():
        logger.warning("KB directory %s not found; using synthetic defaults.", KB_TEXT_DIR)
        chunks = [
            {"id": "policy_dummy.txt", "text": "Collision within policy term is covered unless deliberate damage.", "meta": {"source": "dummy"}},
            {"id": "photo_dummy.txt", "text": "Minimum 3 photos: overall, close-up of damage, license plate.", "meta": {"source": "dummy"}},
            {"id": "triage_dummy.txt", "text": "If severity_score > 0.6 escalate to adjuster.", "meta": {"source": "dummy"}},
        ]
        return chunks

    # Markdown files
    for p in sorted(KB_TEXT_DIR.glob("*.md")):
        chunks.append({
            "id": p.name,
            "text": p.read_text(encoding="utf-8", errors="ignore"),
            "meta": {"source": p.name}
        })
    # JSON rules
    if KB_JSON_DIR.exists():
        for p in sorted(KB_JSON_DIR.glob("*.json")):
            chunks.extend(_json_chunks_from_file(p))
    return chunks


KB_CHUNKS = _load_kb_chunks()
KB_DOCS = [c["text"] for c in KB_CHUNKS]
KB_IDS = [c["id"] for c in KB_CHUNKS]
VECT = TfidfVectorizer().fit(KB_DOCS)
DOC_EMB = VECT.transform(KB_DOCS)
logger.info("RAG simple loaded %d chunks; TF-IDF vectorizer initialized.", len(KB_DOCS))


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


def retrieve_rules_for_fnol(fnol: FNOL, top_k: int = 20) -> List[Dict[str, Any]]:
    """
    Build a query from FNOL details and return top_k KB chunks with metadata.
    """
    parts = [
        f"coverage_type {fnol.policy.coverage_type}",
        f"policy_status {fnol.policy.status}",
        f"incident_type {fnol.incident.type}",
        f"impact_point {fnol.incident.impact_point}",
        f"location {fnol.incident.location or ''}",
        f"photos_count {fnol.documents.photos_count}",
        f"addons {' '.join(fnol.policy.addons or [])}"
    ]
    query = " | ".join(parts + [fnol.incident.description[:200]])
    qv = VECT.transform([query])
    sims = cosine_similarity(qv, DOC_EMB).flatten()
    idxs = np.argsort(-sims)[:top_k]
    results = []
    for i in idxs:
        results.append({
            "id": KB_CHUNKS[i]["id"],
            "text": KB_CHUNKS[i]["text"],
            "meta": KB_CHUNKS[i].get("meta", {}),
            "score": float(sims[i])
        })
    logger.info("retrieve_rules_for_fnol returning %d chunks for query.", len(results))
    return results
