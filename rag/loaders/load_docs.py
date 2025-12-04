# rag/loaders/load_docs.py
def load_sample_docs():
    # simple in-memory docs (synthetic)
    return [
        {"id":"policy/DUMMY-001", "text":"Collision within policy term is covered unless deliberate damage."},
        {"id":"sop/photos", "text":"Minimum 3 photos: overall, close-up of damage, license plate."},
        {"id":"sop/escalation", "text":"If severity_score > 0.6 escalate to adjuster."},
    ]
