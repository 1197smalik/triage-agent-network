# Triage Agent Network


## Quickstart (local)
1. python -m venv .venv && source .venv/bin/activate
2. pip install -r requirements.txt
3. cd streamlit_app
4. streamlit run app.py

App expects a synthetic Excel file (see /sample_data). The app masks PII, runs a simple in-memory RAG, and produces synthetic FNOL JSONs.

## Notes
- No real PII should be processed.
- To hook a real LLM (OpenAI), implement an embedder and change rag/embedder.py to call OpenAI embeddings and vector DB.
- This scaffold uses deterministic logic for validation and synthetic doc retrieval for safety and reproducibility.
