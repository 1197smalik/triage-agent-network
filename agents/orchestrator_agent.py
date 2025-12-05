# agents/orchestrator_agent.py
import logging

from core.use_cases import process_row
from rag.vectorstore import SimpleVectorStore

# load a simple RAG store (in-memory)
vs = SimpleVectorStore()
vs.load_sample_docs()
logger = logging.getLogger(__name__)

def orchestrate_batch(rows: list):
    results = []
    for r in rows:
        logger.info("Orchestrating FNOL generation for row.")
        out = process_row(r)
        results.append(out)
    logger.info("Completed orchestration for %d rows.", len(results))
    return results
