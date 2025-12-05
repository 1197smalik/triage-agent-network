from typing import Protocol, Dict, Any


class LLMClient(Protocol):
    def generate_fnol(self, masked_row: Dict[str, Any]) -> Dict[str, Any]:
        ...


class RAGClient(Protocol):
    def retrieve_rules_for_fnol(self, fnol: Dict[str, Any], top_k: int = 12):
        ...
