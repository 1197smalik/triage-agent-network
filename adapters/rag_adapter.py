from typing import Dict, Any, List

from agents.rag_simple import retrieve_rules_for_fnol


class RagAdapter:
    """RAG adapter that wraps the existing rag_simple retrieval."""

    def retrieve_rules_for_fnol(self, fnol: Dict[str, Any], top_k: int = 12) -> List[Dict[str, Any]]:
        return retrieve_rules_for_fnol(fnol, top_k=top_k)
