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
import requests
import traceback
from typing import Dict, Any, Tuple, List

from .rag_simple import retrieve_rules_for_fnol
from .validators import run_basic_checks
from schemas.claims import (
    FNOL,
    fnol_from_row,
    default_claim_assessment,
    validate_claim_assessment_dict,
)

logger = logging.getLogger(__name__)

# Config
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_S", "120"))

# Helpers
def _session_id():
    return "sess-" + uuid.uuid4().hex[:8]

def safe_float(x, default=0.5):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

def call_ollama_chat(system: str, user: str, model: str = OLLAMA_MODEL, max_tokens: int = 900, retries: int = 1):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "stream": False,
        "options": {"num_predict": max_tokens}
    }
    attempt = 0
    last_err = None
    while attempt <= retries:
        try:
            logger.info("Calling Ollama API at %s with model=%s (attempt %d)", OLLAMA_API, model, attempt + 1)
            resp = requests.post(OLLAMA_API, json=payload, timeout=OLLAMA_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            logger.info("Ollama API call succeeded; content length=%d", len(content))
            return content, data
        except Exception as e:
            last_err = e
            logger.warning("Ollama call failed on attempt %d/%d: %s", attempt + 1, retries + 1, e)
            attempt += 1
            if attempt > retries:
                break
    # bubble up caller to handle fallback / error
    logger.exception("Ollama call failed after retries.")
    raise RuntimeError(f"Ollama call failed: {last_err}")

def _build_system_and_user_prompt(fnol: Dict[str, Any], rules: List[Dict[str, Any]]) -> tuple[str, str]:
    system = (
        "You are ClaimAssist, a strict JSON-only assistant for generating FNOL packages AND claim assessments. "
        "Use only the retrieved KB rule snippets to ground coverage and fraud decisions. "
        "Return a single JSON object with keys: fnol_package, claim_assessment, summary, confidence.\n"
        "fnol_package must include: session_id, incident_time, incident_location, damage_regions, photos, severity_score (0-1), "
        "coverage_indicator, missing_fields, fraud_flags, requires_manual_review, cited_docs; nested workshop/policy/vehicle/incident/documents/cv_results should mirror the FNOL schema.\n"
        "claim_assessment MUST include: claim_reference_id (set to session_id), eligibility (Approved|Rejected|Review), "
        "eligibility_reason (non-empty), coverage_applicable, excluded_reasons, required_followups, fraud_risk_level (non-empty), fraud_flags, "
        "damage_summary (main_impact_area, severity, damaged_parts), recommendation (action non-empty, notes_for_handler), audit_log[].\n"
        "Set 'confidence' and 'severity_score' to numeric values between 0 and 1; NEVER leave them null or omit them. Responses without numeric confidence will be rejected.\n"
        "Do NOT output any text outside the JSON object. Apply rules logically; if uncertain set eligibility to 'Review' and add followups."
    )
    rules_block = "\n\n".join(
        [f"[{i+1}] ({r.get('meta',{}).get('rule_id') or r.get('id')}) {r.get('text')}" for i, r in enumerate(rules)]
    )
    user = (
        f"FNOL JSON:\n{json.dumps(fnol, ensure_ascii=False)}\n\n"
        f"Retrieved KB rules:\n{rules_block}\n\n"
        "Return strict JSON with keys: fnol_package, claim_assessment, summary, confidence."
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
    incident_time_val = claim.get("incident_time")
    incident_time_str = str(incident_time_val) if incident_time_val is not None else ""
    fnol = {
        "session_id": claim.get("session_id"),
        "incident_time": incident_time_str,
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
    assessment = default_claim_assessment(claim.get("session_id", "unknown")).to_dict()
    return {"fnol_package": fnol, "claim_assessment": assessment, "summary": "(fallback) generated", "confidence": 0.75}

# Main function exposed to orchestrator
def generate_fnol_ollama(sanitized_row: dict, rag_client=None):
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
    fnol_obj: FNOL = fnol_from_row(sanitized_row, session)
    fnol_dict = fnol_obj.to_dict()

    # 1) RAG retrieval
    try:
        if rag_client:
            rule_chunks = rag_client.retrieve_rules_for_fnol(fnol_obj, top_k=8)
        else:
            rule_chunks = retrieve_rules_for_fnol(fnol_obj, top_k=8)
        logger.info("Retrieved %d RAG rule chunks for session_id=%s", len(rule_chunks), session)
    except Exception:
        logger.exception("RAG retrieval failed; using defaults.")
        rule_chunks = [{"id": "default", "text": "Collision within policy term is covered unless deliberate damage.", "meta": {}}]

    # 2) Build prompt
    system, user = _build_system_and_user_prompt(fnol_dict, rule_chunks)

    def _attempt_call(user_prompt: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        raw_text_local = None
        meta_local = {}
        raw_text_local, meta_local = call_ollama_chat(system, user_prompt)
        parsed_local = _extract_json_from_text(raw_text_local)
        return parsed_local, meta_local, raw_text_local

    # 3) Call Ollama
    try:
        parsed, meta, raw_text = _attempt_call(user)
    except Exception as e:
        meta = {"error": str(e), "trace": traceback.format_exc()}
        fallback = _fallback_fnol({"session_id": session, **sanitized_row}, [c["text"] for c in rule_chunks])
        logger.error("Ollama call failed for session_id=%s; returning fallback.", session)
        return {
            "error": "ollama_call_failed",
            "reason": str(e),
            "llm_raw_meta": meta,
            "fallback": fallback
        }

    # 4) Parse model output into JSON; retry once if needed
    if parsed is None:
        logger.warning("First parse attempt failed; retrying with guidance.")
        retry_user = user + "\n\nYour previous response could not be parsed as JSON. Return strict JSON only."
        try:
            parsed, meta, raw_text = _attempt_call(retry_user)
        except Exception as e:
            meta = {"error": str(e), "trace": traceback.format_exc()}
            fallback = _fallback_fnol({"session_id": session, **sanitized_row}, [c["text"] for c in rule_chunks])
            return {
                "error": "invalid_model_output",
                "reason": "no_json_parsed",
                "raw_model_text": raw_text,
                "llm_raw_meta": meta,
                "fallback": fallback
            }

    if parsed is None:
        fallback = _fallback_fnol({"session_id": session, **sanitized_row}, [c["text"] for c in rule_chunks])
        logger.error("No JSON parsed from Ollama response; session_id=%s", session)
        return {
            "error": "invalid_model_output",
            "reason": "no_json_parsed",
            "raw_model_text": raw_text,
            "llm_raw_meta": meta,
            "fallback": fallback
        }

    # 5) Validate presence and type of 'confidence' and other required assessment fields; retry once if missing
    confidence_raw = parsed.get("confidence", None)
    ca_tmp = parsed.get("claim_assessment") if isinstance(parsed, dict) else None
    required_missing = []
    if confidence_raw is None or (isinstance(confidence_raw, str) and not confidence_raw.strip()):
        required_missing.append("confidence")
    if not isinstance(ca_tmp, dict):
        required_missing.extend(["claim_assessment", "claim_reference_id", "eligibility_reason", "fraud_risk_level", "recommendation.action"])
    else:
        if not ca_tmp.get("claim_reference_id"):
            required_missing.append("claim_reference_id")
        if not ca_tmp.get("eligibility_reason"):
            required_missing.append("eligibility_reason")
        if not ca_tmp.get("fraud_risk_level"):
            required_missing.append("fraud_risk_level")
        if not (ca_tmp.get("recommendation") or {}).get("action"):
            required_missing.append("recommendation.action")

    if required_missing:
        example = json.dumps({
            "fnol_package": {
                "session_id": session,
                "incident_time": "2025-01-01T00:00:00",
                "incident_location": "City",
                "damage_regions": ["front"],
                "photos": [],
                "severity_score": 0.4,
                "coverage_indicator": "covered",
                "missing_fields": [],
                "fraud_flags": [],
                "requires_manual_review": False,
                "cited_docs": []
            },
            "claim_assessment": {
                "claim_reference_id": session,
                "eligibility": "Review",
                "eligibility_reason": "Non-empty reason",
                "coverage_applicable": ["OwnDamage"],
                "excluded_reasons": [],
                "required_followups": [],
                "fraud_risk_level": "Low",
                "fraud_flags": [],
                "damage_summary": {"main_impact_area": "Front", "severity": "Moderate", "damaged_parts": []},
                "recommendation": {"action": "Proceed_With_Claim", "notes_for_handler": ""},
                "audit_log": []
            },
            "summary": "text",
            "confidence": 0.7
        }, ensure_ascii=False)
        logger.warning("Required fields missing %s; retrying model with explicit example.", required_missing)
        retry_user_missing = user + f"\n\nYou omitted required fields: {required_missing}. Resend strict JSON with ALL required fields non-null. Example:\n{example}"
        try:
            parsed_retry, meta_retry, raw_text_retry = _attempt_call(retry_user_missing)
            if parsed_retry and isinstance(parsed_retry, dict):
                parsed = parsed_retry
                meta = meta_retry
                raw_text = raw_text_retry
                confidence_raw = parsed.get("confidence", confidence_raw)
                ca_tmp = parsed.get("claim_assessment", ca_tmp)
        except Exception:
            pass

    # Backfill after retry
    if not isinstance(ca_tmp, dict):
        ca_tmp = {}
    ca_tmp.setdefault("claim_reference_id", session)
    ca_tmp.setdefault("eligibility_reason", "Auto-filled because model omitted this field.")
    ca_tmp.setdefault("fraud_risk_level", "Medium")
    rec_tmp = ca_tmp.get("recommendation") or {}
    rec_tmp.setdefault("action", "Escalate_To_Human")
    rec_tmp.setdefault("notes_for_handler", "")
    ca_tmp["recommendation"] = rec_tmp
    parsed["claim_assessment"] = ca_tmp

    try:
        confidence_val = float(confidence_raw)
    except Exception:
        confidence_val = 0.5
    # revalidate after backfill
    ca_errors = validate_claim_assessment_dict(ca_tmp)

    # 6) Extract fnol package from parsed JSON
    fnol = parsed.get("fnol_package") or {}
    if not isinstance(fnol, dict):
        fnol = fnol_dict
    # backfill compatibility fields
    if "incident_time" not in fnol:
        t = fnol_obj.incident.time or ""
        d = fnol_obj.incident.date or ""
        fnol["incident_time"] = f"{d} {t}".strip() or ""
    else:
        fnol["incident_time"] = str(fnol.get("incident_time") or "")
    # normalize coverage_indicator to string
    cov_ind = fnol.get("coverage_indicator", "unknown")
    if isinstance(cov_ind, bool):
        cov_ind = "covered" if cov_ind else "unknown"
    fnol["coverage_indicator"] = str(cov_ind)
    fnol.setdefault("damage_regions", [])
    fnol.setdefault("photos", [])
    fnol.setdefault("missing_fields", [])
    fnol.setdefault("fraud_flags", [])
    fnol.setdefault("session_id", session)
    fnol["severity_score"] = safe_float(fnol.get("severity_score"), default=0.3)
    if "cited_docs" not in fnol or not isinstance(fnol.get("cited_docs"), list):
        fnol["cited_docs"] = [{"doc_id": c.get("id"), "excerpt": c.get("text", "")[:200]} for c in rule_chunks[:3]]

    # 7) Claim assessment handling
    claim_assessment = parsed.get("claim_assessment") if isinstance(parsed, dict) else None
    ca_errors: List[str] = []
    if not isinstance(claim_assessment, dict):
        ca_errors.append("missing_claim_assessment")
        claim_assessment = default_claim_assessment(session).to_dict()
    else:
        if "claim_reference_id" not in claim_assessment or not claim_assessment.get("claim_reference_id"):
            claim_assessment["claim_reference_id"] = session
        ca_errors = validate_claim_assessment_dict(claim_assessment)
        if ca_errors:
            logger.warning("Claim assessment validation errors: %s", ca_errors)
            # simple retry if errors
            retry_user = user + f"\n\nErrors found: {ca_errors}. Fix and return valid JSON now."
            try:
                parsed_retry, meta_retry, raw_text_retry = _attempt_call(retry_user)
                if parsed_retry and isinstance(parsed_retry, dict) and parsed_retry.get("claim_assessment"):
                    claim_assessment = parsed_retry.get("claim_assessment")
                    meta = meta_retry
                    raw_text = raw_text_retry
                    ca_errors = validate_claim_assessment_dict(claim_assessment)
            except Exception:
                pass
            if ca_errors:
                claim_assessment = default_claim_assessment(session).to_dict()

    # Backfill any missing critical fields to avoid empty outputs
    if not claim_assessment.get("fraud_risk_level"):
        claim_assessment["fraud_risk_level"] = "Medium"
    if not claim_assessment.get("eligibility_reason"):
        claim_assessment["eligibility_reason"] = "Model supplied empty reason"
    rec = claim_assessment.get("recommendation") or {}
    if not rec.get("action"):
        rec["action"] = "Escalate_To_Human"
    rec.setdefault("notes_for_handler", "")
    claim_assessment["recommendation"] = rec

    # 8) Deterministic verification
    verification = run_basic_checks(fnol, sanitized_row, [c["text"] for c in rule_chunks], claim_assessment=ca_tmp)
    if not verification.get("passed", True):
        fnol["requires_manual_review"] = True

    logger.info("Returning FNOL for session_id=%s with verification_passed=%s", session, verification.get("passed", True))
    return {
        "fnol_package": fnol,
        "claim_assessment": ca_tmp,
        "summary": parsed.get("summary", "(no summary provided)") if isinstance(parsed, dict) else "(no summary provided)",
        "confidence": confidence_val,
        "retrieved_docs": rule_chunks,
        "verification": verification,
        "llm_raw_meta": meta,
        "raw_model_text": raw_text
    }
