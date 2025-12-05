# agents/fnol_agent.py
"""
FNOL Generation Agent
- Input: sanitized row dict (no PII), e.g. keys: policy_number, claimant_name (token), car_number (token),
         incident_time, incident_description, incident_location (token)
- Output: {
    "fnol_package": {...}, "summary": "...", "verification": {...}
  }
"""

import logging
import os
import json
import uuid
import subprocess
from datetime import datetime
from typing import Dict, Any

# RAG store from scaffold
from rag.vectorstore import SimpleVectorStore

# basic validators from scaffold

logger = logging.getLogger(__name__)

# ---- Helper utilities ----

def _session_id():
    return "sess-" + uuid.uuid4().hex[:8]

def _safe_isoformat(t):
    try:
        if not t:
            return ""
        return pd_to_iso(t)
    except Exception:
        return ""

def pd_to_iso(v):
    # basic conversion robust to pandas Timestamp or string
    try:
        from pandas import to_datetime
        return to_datetime(v).isoformat()
    except Exception:
        # fallback
        return str(v)

# ---- Compose LLM prompt (RAG aware) ----

SYSTEM_PROMPT = """
You are ClaimAssist Agent. Use ONLY the retrieved document excerpts to ground any factual claims about coverage or SOPs.
Return a JSON object (fnol_package) with these fields:
  - session_id (str)
  - incident_time (ISO string)
  - incident_location (string)
  - damage_regions (array of strings)
  - photos (array of urls - blank allowed)
  - severity_score (0.0-1.0)
  - coverage_indicator (covered|not_covered|unknown)
  - missing_fields (array)
  - fraud_flags (array)
  - requires_manual_review (bool)
  - cited_docs (array of {doc_id, excerpt})
Also return "summary" (short human text) and "confidence" (0.0-1.0).
If coverage can't be concluded from retrieved docs, set coverage_indicator to "unknown".
"""

USER_PROMPT_TEMPLATE = """
Claim Data (SANITIZED TOKENS ONLY):
{claim_json}

Retrieved Documents (use these for grounding):
{retrieved}

Return the JSON described in the system prompt. Keep extra text out of the JSON.
"""

# ---- RAG store instance (in-memory) ----
_vs = SimpleVectorStore()
_vs.load_sample_docs()

# ---- LLM call wrapper (OpenAI function-calling style or fallback) ----

def call_llm_for_fnol(prompt_system: str, prompt_user: str, function_schema: Dict[str, Any] = None):
    """
    Calls the local Ollama model (llama3.2:3B by default). If the CLI call fails,
    falls back to a deterministic mock response.
    """
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3B")
    prompt = f"{prompt_system.strip()}\n\n{prompt_user.strip()}\n\nReturn ONLY JSON."
    logger.info("Invoking Ollama model=%s", model)
    try:
        # call Ollama CLI; assume it is installed and model is running locally
        resp = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=90
        )
        if resp.returncode == 0 and resp.stdout:
            # model should return JSON; attempt to parse
            logger.info("Ollama call succeeded with %d bytes output.", len(resp.stdout))
            return json.loads(resp.stdout.strip()), {"provider": "ollama", "model": model}
        else:
            logger.error("Ollama call failed: %s", resp.stderr or resp.stdout)
    except Exception as e:
        logger.exception("Ollama invocation error: %s", e)

    # ---- Mock fallback (deterministic, safe) ----
    # This generates a reproducible fnol_package based only on text heuristics.
    logger.warning("Ollama not configured or failed, returning mocked FNOL (safe fallback).")
    # Very simple heuristic-based output:
    # parse claim json
    try:
        claim = json.loads(prompt_user.split("Claim Data (SANITIZED TOKENS ONLY):",1)[1].split("Retrieved Documents")[0].strip())
    except Exception:
        claim = {}
    desc = (claim.get("incident_description") or "").lower()
    damage_regions = []
    for k in ["rear","front","side","windshield"]:
        if k in desc:
            damage_regions.append(k)
    if not damage_regions:
        damage_regions = ["general"]
    severity = 0.2 if any(k in desc for k in ["minor","scratch"]) else 0.6 if "collision" in desc or "airbag" in desc else 0.3
    # decide coverage from retrieved docs (simple substring logic)
    retrieved_section = prompt_user.split("Retrieved Documents (use these for grounding):",1)[1]
    coverage = "unknown"
    if "collision" in retrieved_section.lower():
        coverage = "likely_in_coverage"
    # build fnol package
    fnol = {
        "session_id": claim.get("session_id", _session_id()),
        "incident_time": claim.get("incident_time",""),
        "incident_location": claim.get("incident_location","[redacted]"),
        "damage_regions": damage_regions,
        "photos": claim.get("photos", []),
        "severity_score": round(float(severity),2),
        "coverage_indicator": coverage,
        "missing_fields": [],
        "fraud_flags": [],
        "requires_manual_review": False,
        "cited_docs": []
    }
    # simple missing fields check
    for f in ["policy_number","incident_description"]:
        if not claim.get(f):
            fnol["missing_fields"].append(f)
    if fnol["missing_fields"]:
        fnol["requires_manual_review"] = True
    return {"fnol_package": fnol, "summary":"(mock) generated FNOL", "confidence":0.8}, {"provider":"mock"}

# ---- Validation helpers ----

def run_validators(fnol_package: Dict[str,Any]) -> Dict[str,Any]:
    """
    Apply deterministic checks on fnol_package. Returns augmented package and verification log.
    """
    vd = {"issues": [], "passed": True}
    # example: incident_time parse
    try:
        if fnol_package.get("incident_time"):
            # try ISO parse
            datetime.fromisoformat(fnol_package["incident_time"])
    except Exception:
        vd["issues"].append("incident_time_unparsable")
    # check required fields
    if not fnol_package.get("policy_number") and not fnol_package.get("policy_token"):
        vd["issues"].append("missing_policy_reference")
    if not fnol_package.get("incident_description") and not fnol_package.get("damage_regions"):
        vd["issues"].append("missing_description")
    if vd["issues"]:
        vd["passed"] = False
        fnol_package["requires_manual_review"] = True
    return fnol_package, vd

# ---- Agent main function ----

def generate_fnol_for_row(sanitized_row: Dict[str,Any]) -> Dict[str,Any]:
    """
    Entry point: sanitized_row contains only tokenized PII and incident_description.
    Returns dict with keys: fnol_package, summary, verification
    """
    session_id = _session_id()
    logger.info("Generating FNOL for session_id=%s", session_id)
    # build claim JSON (sanitized)
    claim_json = {
        "session_id": session_id,
        "policy_number": sanitized_row.get("policy_number",""),
        "policy_token": sanitized_row.get("policy_number",""),
        "vehicle_token": sanitized_row.get("car_number",""),
        "claimant_token": sanitized_row.get("claimant_name",""),
        "incident_time": sanitized_row.get("incident_time",""),
        "incident_description": sanitized_row.get("incident_description",""),
        "incident_location": sanitized_row.get("incident_location",""),
        "photos": sanitized_row.get("photos", [])
    }

    # 1) RAG retrieval
    retrieved = _vs.retrieve_docs(claim_json["incident_description"], top_k=3)
    logger.info("Retrieved %d documents for session_id=%s", len(retrieved), session_id)

    # 2) Build user prompt that contains claim + retrieved docs
    retrieved_text = "\n\n".join([f"{d['id']}: {d['text']}" for d in retrieved])
    user_prompt = USER_PROMPT_TEMPLATE.format(
        claim_json=json.dumps(claim_json),
        retrieved=retrieved_text
    )

    # define a function schema (for OpenAI) that the model should return if available
    function_schema = {
        "name": "submit_fnol_package",
        "description": "Return the validated FNOL package as JSON.",
        "parameters": {
            "type": "object",
            "properties": {
                "fnol_package": {"type": "object"},
                "summary": {"type": "string"},
                "confidence": {"type":"number"}
            },
            "required": ["fnol_package", "summary"]
        }
    }

    # 3) Call LLM (or fallback)
    llm_output, meta = call_llm_for_fnol(SYSTEM_PROMPT, user_prompt, function_schema)
    logger.info("LLM output received for session_id=%s", session_id)

    # the OpenAI wrapper returns either direct JSON or a dict containing keys
    if isinstance(llm_output, dict) and "fnol_package" in llm_output:
        fnol = llm_output["fnol_package"]
        summary = llm_output.get("summary","")
        confidence = llm_output.get("confidence", 0.5)
    else:
        # If the mock returned nested structure
        if isinstance(llm_output, dict) and "fnol_package" in llm_output.get("fnol_package", {}):
            fnol = llm_output["fnol_package"]
            summary = llm_output.get("summary","")
            confidence = llm_output.get("confidence", 0.5)
        else:
            # If our mock wrapper returned a dict containing 'fnol_package' nested differently (like earlier fallback),
            fnol = llm_output.get("fnol_package") if isinstance(llm_output, dict) else {}
            summary = llm_output.get("summary","(no summary)")
            confidence = llm_output.get("confidence", 0.5)

    # 4) Attach metadata & citations from retrieved docs
    if "cited_docs" not in fnol:
        fnol["cited_docs"] = [{"doc_id": d["id"], "excerpt": d["text"][:300]} for d in retrieved]

    # 5) Run validators (deterministic)
    validated_fnol, verification = run_validators(fnol)
    logger.info("Validation complete for session_id=%s; passed=%s", session_id, verification.get("passed"))

    # 6) Build result object
    result = {
        "fnol_package": validated_fnol,
        "summary": summary,
        "confidence": confidence,
        "retrieved_docs": retrieved,
        "verification": verification,
        "llm_meta": meta
    }
    return result
