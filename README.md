# Triage Agent Network

Streamlit-based FNOL intake assistant that masks PII, retrieves KB rules, calls a local LLM via Ollama, and returns FNOL + claim assessment JSON per Excel row.

## Prerequisites
- Python 3.10+ (recommend 3.11)
- Git
- Ollama installed with the `llama3.2:3b` model pulled and running locally
- Only use synthetic/sample data (no real PII)

## Setup (Windows / macOS / Linux)

### 1) Clone
```
git clone https://github.com/1197smalik/triage-agent-network.git
cd triage-agent-network
```

### 2) Create and activate a virtual environment
- **macOS/Linux (bash/zsh):**
  ```
  python -m venv .venv
  source .venv/bin/activate
  ```
- **Windows (PowerShell):**
  ```
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

### 3) Install dependencies
```
pip install -r requirements.txt
```

### 4) Start Ollama (ensure llama3.2:3b is available)
```
ollama pull llama3.2:3b
ollama serve
```
Verify: `ollama run llama3.2:3b "ping"`

## Run the Streamlit app
From the repo root:
```
streamlit run app.py
```
To pick a port (e.g., 9999):
```
streamlit run app.py --server.port=9999
```

## Usage
1. In the web UI, upload a synthetic Excel file (see `sample_data/sample_claims.xlsx`).
2. The app masks PII, shows a sanitized preview, and processes rows one-by-one with live progress.
3. For each row you’ll see eligibility, fraud risk, required followups, and links to view/download FNOL JSON. “Process ready” rows are highlighted.

## Notes
- Avoid processing real PII.
- To change the model, set `OLLAMA_MODEL` (e.g., `export OLLAMA_MODEL=llama3.2:3b`).
- KB rules live under `knowledge_base/` (markdown) and `knowledge_base/json/`; RAG uses these for grounding.
- Deterministic fallbacks and validation help prevent empty outputs; manual review is flagged when validation fails.***
