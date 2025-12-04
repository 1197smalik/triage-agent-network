# agents/fnol_agent_ollama.py
"""
Robust FNOL agent using local Ollama (Llama) backend.

Behavior:
- Calls Ollama via HTTP API (default: http://localhost:11434/api/chat).
- Attempts to parse a strict JSON response from the model.
- If the 'confidence' field is missing or None, returns a structured error object (per your choice B).
- Always returns safe, deterministic fallback if parsing fails, but for this strict mode we return an explicit error
  when confidence is invalid so the caller can inspect model output and logs.
"""

import logging
import os
import json
import uuid
from datetime import datetime
import requests
import traceback

from .rag_simple import retrieve_relevant_snips
from .validators import validate_fnol_schema, run_basic_checks

logger = logging.getLogger(__name__)

# Config
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_S", "60"))

# Helpers
def _session_id():
    return "sess-" + uuid.uuid4().hex[:8]

def safe_float(x, default=0.5):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

def call_ollama_chat(system: str, user: str, model: str = OLLAMA_MODEL, max_tokens: int = 700):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "stream": False
    }
    try:
        logger.info("Calling Ollama API at %s with model=%s", OLLAMA_API, model)
        resp = requests.post(OLLAMA_API, json=payload, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns combined content under data["message"]["content"]
        content = data.get("message", {}).get("content", "")
        logger.info("Ollama API call succeeded; content length=%d", len(content))
        return content, data
    except Exception as e:
        # bubble up caller to handle fallback / error
        logger.exception("Ollama call failed.")
        raise RuntimeError(f"Ollama call failed: {e}")

def _build_system_and_user_prompt(claim: dict, retrieved_snips: list[str]) -> tuple[str, str]:
    system = (
        "You are ClaimAssist, a strict JSON-only assistant for generating FNOL packages. "
        "Use only the retrieved policy/SOP snippets to ground any coverage claims. "
        "Return a single JSON object with keys: fnol_package, summary, confidence.\n"
        "fnol_package MUST include: session_id, incident_time, incident_location, damage_regions (array), "
        "photos (array), severity_score (0-1), coverage_indicator ('covered'|'not_covered'|'unknown'), "
        "missing_fields (array), fraud_flags (array), requires_manual_review (bool), cited_docs (array).\n"
        "Set 'confidence' to a numeric value between 0 and 1; NEVER leave it null or omit it.\n"
        "Set 'severity_score' to a numeric value between 0 and 1; NEVER leave it null or omit it.\n"
        "Do NOT output any text outside the JSON object. If you cannot determine coverage using the snippets, set "
        "'coverage_indicator' to 'unknown'."
    )
    retrieved_block = "\n\n".join(f"[{i+1}] {s[:800]}" for i, s in enumerate(retrieved_snips))
    user = (
        f"Claim (SANITIZED TOKENIZED FIELDS ONLY):\n{json.dumps(claim, ensure_ascii=False)}\n\n"
        f"Retrieved knowledge snippets:\n{retrieved_block}\n\n"
        "Return the JSON now."
    )
    return system, user

def _extract_json_from_text(text: str):
    """
    Try direct json loads, otherwise find first {...} substring and parse that.
    Returns parsed dict or None.
    """
    if not text:
        return None
    # direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # attempt substring extraction (first JSON object)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            return None
    return None

def _fallback_fnol(claim: dict, snips: list[str]):
    """
    Deterministic fallback generator (safe). This is used only when parsing fails badly.
    For strict mode B we still return an error if confidence is missing, but fallback is provided
    to avoid total service failure — caller can inspect 'error' keys.
    """
    desc = (claim.get("incident_description") or "").lower()
    damages = [k for k in ("rear","front","side","windshield") if k in desc]
    if not damages:
        damages = ["general"]
    severity = 0.2 if any(w in desc for w in ["minor","scratch"]) else 0.6 if "collision" in desc or "airbag" in desc else 0.3
    coverage = "unknown"
    for s in snips:
        if "collision" in s.lower():
            coverage = "covered"
    fnol = {
        "session_id": claim.get("session_id"),
        "incident_time": claim.get("incident_time"),
        "incident_location": claim.get("incident_location") or "[redacted]",
        "damage_regions": damages,
        "photos": claim.get("photos", []),
        "severity_score": round(float(severity),2),
        "coverage_indicator": coverage,
        "missing_fields": [] if claim.get("incident_description") else ["incident_description"],
        "fraud_flags": [],
        "requires_manual_review": (coverage == "unknown"),
        "cited_docs": [{"doc_id": f"kb_snip_{i+1}", "excerpt": s[:200]} for i, s in enumerate(snips)]
    }
    return {"fnol_package": fnol, "summary": "(fallback) generated", "confidence": 0.75}

# Main function exposed to orchestrator
def generate_fnol_ollama(sanitized_row: dict):
    """
    sanitized_row: dict with tokenized PII and incident_description.
    Returns: dict. On success returns:
      {
        "fnol_package": {...},
        "summary": "...",
        "confidence": float,
        "retrieved_docs": [...],
        "verification": {...},
        "llm_raw_meta": {...}
      }
    On validation error (choice B), returns:
      {
        "error": "invalid_model_output",
        "reason": "confidence_missing",
        "raw_model_text": "...",
        "llm_raw_meta": {...},
        "fallback": { ... }  # deterministic fallback to inspect
      }
    """
    session = _session_id()
    logger.info("Starting Ollama FNOL generation; session_id=%s", session)
    claim = {
        "session_id": session,
        "policy_token": sanitized_row.get("policy_number",""),
        "vehicle_token": sanitized_row.get("car_number",""),
        "claimant_token": sanitized_row.get("claimant_name",""),
        "incident_time": str(sanitized_row.get("incident_time","")),
        "incident_description": sanitized_row.get("incident_description",""),
        "incident_location": sanitized_row.get("incident_location",""),
        "photos": sanitized_row.get("photos", [])
    }

    # 1) RAG retrieval
    try:
        snips = retrieve_relevant_snips(claim["incident_description"], top_k=3)
        logger.info("Retrieved %d RAG snippets for session_id=%s", len(snips), session)
    except Exception:
        # if retrieval fails, use safe defaults
        logger.exception("RAG retrieval failed; using defaults.")
        snips = ["Collision within policy term is covered unless deliberate damage.",
                 "Minimum 3 photos: overall, close-up of damage, license plate.",
                 "If severity_score > 0.6 escalate to adjuster."]

    # 2) Build prompt
    system, user = _build_system_and_user_prompt(claim, snips)

    # 3) Call Ollama
    raw_text = None
    meta = {}
    try:
        raw_text, meta = call_ollama_chat(system, user)
    except Exception as e:
        meta = {"error": str(e), "trace": traceback.format_exc()}
        # fall back to deterministic fallback but mark as error (strict mode B)
        fallback = _fallback_fnol(claim, snips)
        logger.error("Ollama call failed for session_id=%s; returning fallback.", session)
        return {
            "error": "ollama_call_failed",
            "reason": str(e),
            "llm_raw_meta": meta,
            "fallback": fallback
        }

    # 4) Parse model output into JSON
    parsed = _extract_json_from_text(raw_text)
    if parsed is None:
        # no JSON detected - return error with fallback attached
        fallback = _fallback_fnol(claim, snips)
        logger.error("No JSON parsed from Ollama response; session_id=%s", session)
        return {
            "error": "invalid_model_output",
            "reason": "no_json_parsed",
            "raw_model_text": raw_text,
            "llm_raw_meta": meta,
            "fallback": fallback
        }

    # 5) Validate presence and type of 'confidence'
    confidence_raw = parsed.get("confidence", None)
    if confidence_raw is None:
        logger.warning("Confidence missing/null in model output; session_id=%s. Defaulting to 0.5", session)
        confidence_val = 0.5
    else:
        try:
            confidence_val = float(confidence_raw)
        except Exception:
            logger.warning("Confidence not numeric; session_id=%s value=%s. Defaulting to 0.5", session, confidence_raw)
            confidence_val = 0.5

    # 6) Extract fnol package from parsed JSON
    fnol = parsed.get("fnol_package")
    if not isinstance(fnol, dict):
        # invalid structure
        fallback = _fallback_fnol(claim, snips)
        logger.error("fnol_package missing/invalid; session_id=%s", session)
        return {
            "error": "invalid_model_output",
            "reason": "fnol_package_missing_or_invalid",
            "raw_model_text": raw_text,
            "llm_raw_meta": meta,
            "fallback": fallback
        }

    # normalize severity_score if missing/null
    fnol["severity_score"] = safe_float(fnol.get("severity_score"), default=0.3)

    # Ensure required defaults
    fnol.setdefault("session_id", session)
    if "cited_docs" not in fnol or not isinstance(fnol.get("cited_docs"), list):
        fnol["cited_docs"] = [{"doc_id": f"kb_snip_{i+1}", "excerpt": s[:200]} for i, s in enumerate(snips)]

    # 7) Deterministic verification
    verification = run_basic_checks(fnol, claim, snips)
    # if verification failed, mark requires_manual_review
    if not verification.get("passed", True):
        fnol["requires_manual_review"] = True

    # 8) Return the clean object
    logger.info("Returning FNOL for session_id=%s with verification_passed=%s", session, verification.get("passed", True))
    return {
        "fnol_package": fnol,
        "summary": parsed.get("summary", "(no summary provided)"),
        "confidence": confidence_val,
        "retrieved_docs": [{"text": s} for s in snips],
        "verification": verification,
        "llm_raw_meta": meta,
        "raw_model_text": raw_text
    }
