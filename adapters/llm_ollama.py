from typing import Dict, Any

from agents.fnol_agent_ollama import generate_fnol_ollama
from adapters.rag_adapter import RagAdapter


class OllamaLLMClient:
    """LLM adapter that delegates to the existing Ollama-backed FNOL generator."""

    def __init__(self, rag_client=None):
        self.rag_client = rag_client or RagAdapter()

    def generate_fnol(self, masked_row: Dict[str, Any]) -> Dict[str, Any]:
        return generate_fnol_ollama(masked_row, rag_client=self.rag_client)
