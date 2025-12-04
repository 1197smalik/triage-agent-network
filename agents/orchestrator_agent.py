# agents/orchestrator_agent.py
import uuid
from agents.fnol_extraction_agent import extract_fnol_from_row
from agents.fnol_validation_agent import validate_fnol_package
from agents.fnol_summary_agent import summarize_fnol
from rag.vectorstore import SimpleVectorStore

# load a simple RAG store (in-memory)
vs = SimpleVectorStore()
vs.load_sample_docs()

def orchestrate_batch(rows: list):
    results = []
    for r in rows:
        # extraction produces sanitized structured dict
        extracted = extract_fnol_from_row(r)
        # run RAG retrieval for context
        retrieved = vs.retrieve_docs(extracted["incident_description"], top_k=3)
        # validate + augment
        validated = validate_fnol_package(extracted, retrieved)
        # summary
        summary = summarize_fnol(validated, retrieved)
        results.append({
            "fnol_package": validated,
            "retrieved_docs": retrieved,
            "summary": summary
        })
    return results
