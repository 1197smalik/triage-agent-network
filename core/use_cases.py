from typing import Dict, Any

from core.services import ClaimProcessingService

_service = ClaimProcessingService()


def process_row(masked_row: Dict[str, Any], llm_client=None) -> Dict[str, Any]:
    """
    Entry point for processing a sanitized row into FNOL + assessment.
    By default uses the service with Ollama LLM + RAG adapters.
    llm_client can be injected to support alternate providers in future.
    """
    if llm_client:
        return llm_client.generate_fnol(masked_row)
    return _service.process_row(masked_row)
