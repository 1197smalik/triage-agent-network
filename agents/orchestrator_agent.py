# agents/orchestrator_agent.py
import logging
import uuid
from agents.fnol_extraction_agent import extract_fnol_from_row
from agents.fnol_validation_agent import validate_fnol_package
from agents.fnol_summary_agent import summarize_fnol
from rag.vectorstore import SimpleVectorStore
from agents.fnol_agent import generate_fnol_for_row

# load a simple RAG store (in-memory)
vs = SimpleVectorStore()
vs.load_sample_docs()
logger = logging.getLogger(__name__)

def orchestrate_batch(rows: list):
    results = []
    for r in rows:
        logger.info("Orchestrating FNOL generation for row.")
        out = generate_fnol_for_row(r)
        results.append(out)
    logger.info("Completed orchestration for %d rows.", len(results))
    return results
