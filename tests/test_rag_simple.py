from schemas.claims import FNOL, PolicyInfo, IncidentInfo, DocumentInfo
from agents import rag_simple


def test_retrieve_rules_for_fnol_returns_chunks():
    fnol = FNOL(
        policy=PolicyInfo(coverage_type="COMP", status="Active"),
        incident=IncidentInfo(type="Collision", impact_point="Front", description="front impact"),
        documents=DocumentInfo(photos_count=2),
    )
    chunks = rag_simple.retrieve_rules_for_fnol(fnol, top_k=5)
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    first = chunks[0]
    assert "text" in first and "id" in first


def test_retrieve_relevant_snips_handles_empty_query():
    snips = rag_simple.retrieve_relevant_snips("", top_k=2)
    assert len(snips) == 2
