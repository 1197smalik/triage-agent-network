from rag.vectorstore import SimpleVectorStore
from schemas.claims import FNOL
from typing import Dict, Any, List


class VectorStoreRag:
    """Adapter around SimpleVectorStore to provide FNOL-aware retrieval."""

    def __init__(self):
        self.store = SimpleVectorStore()
        self.store.load_sample_docs()

    def retrieve_rules_for_fnol(self, fnol: FNOL | Dict[str, Any], top_k: int = 12) -> List[Dict[str, Any]]:
        desc = ""
        if isinstance(fnol, dict):
            desc = fnol.get("incident_description", "")
        else:
            desc = fnol.incident.description
        return self.store.retrieve_docs(desc, top_k=top_k)
