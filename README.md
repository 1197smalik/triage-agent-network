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

## Static analysis and tests
Install dev tools:
```
pip install -r requirements-dev.txt
```
Run lint/type checks (or use the bundled venv `venv_claim`):
```
ruff check .
mypy --config-file pyproject.toml .
```

Security scans (optional; bandit can have issues on Python 3.14, semgrep/pip-audit are good alternatives):
```
semgrep --config p/ci --error
pip-audit
```
If Semgrep needs a cert bundle:
```
export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")
semgrep --config p/security-audit --config p/secrets --error
```

Tests + coverage:
```
pytest --cov=. --cov-report=term --cov-report=html
```
Using the bundled venv:
```
./venv_claim/bin/ruff check .
./venv_claim/bin/python -m mypy --config-file pyproject.toml .
./venv_claim/bin/python -m pytest --cov=. --cov-report=term --cov-report=html
```
Coverage HTML will be in `htmlcov/index.html`.

## Usage
1. In the web UI, upload a synthetic Excel file (see `sample_data/sample_claims.xlsx`).
2. The app masks PII, shows a sanitized preview, and processes rows one-by-one with live progress.
3. For each row you’ll see eligibility, fraud risk, required followups, and links to view/download FNOL JSON. “Process ready” rows are highlighted.

## Notes
- Avoid processing real PII.
- To change the model, set `OLLAMA_MODEL` (e.g., `export OLLAMA_MODEL=llama3.2:3b`).
- KB rules live under `knowledge_base/` (markdown) and `knowledge_base/json/`; RAG uses these for grounding.
- Deterministic fallbacks and validation help prevent empty outputs; manual review is flagged when validation fails.***
