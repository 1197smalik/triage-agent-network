from typing import Dict, Any

from adapters.llm_ollama import OllamaLLMClient
from adapters.rag_adapter import RagAdapter


class ClaimProcessingService:
    """
    Service orchestrating FNOL + claim assessment generation via injected adapters.
    Defaults to Ollama LLM + rag_simple retrieval.
    """

    def __init__(self, llm_client=None, rag_client=None):
        self.rag_client = rag_client or RagAdapter()
        self.llm_client = llm_client or OllamaLLMClient(rag_client=self.rag_client)

    def process_row(self, masked_row: Dict[str, Any]) -> Dict[str, Any]:
        return self.llm_client.generate_fnol(masked_row)
