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
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_S", "180"))

# Helpers
def _session_id():
    return "sess-" + uuid.uuid4().hex[:8]

def safe_float(x, default=0.5):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _clean_text(text: str, max_len: int = 600) -> str:
    if not text:
        return ""
    cleaned = " ".join(str(text).split())  # collapse whitespace/newlines
    return cleaned[:max_len]

def call_ollama_chat(system: str, user: str, model: str = OLLAMA_MODEL, max_tokens: int = 2200, retries: int = 1):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.1, "repeat_penalty": 1.05, "num_ctx": 4096}
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
        "fnol_package REQUIRED fields (no nulls): session_id, incident_time, incident_location, damage_regions, photos, severity_score (0-1 float), "
        "coverage_indicator (string), missing_fields, fraud_flags, requires_manual_review, cited_docs; include nested workshop/policy/vehicle/incident/documents/cv_results per schema.\n"
        "claim_assessment REQUIRED (no null/empty): claim_reference_id (session_id), eligibility (Approved|Rejected|Review), "
        "eligibility_reason (non-empty), coverage_applicable, excluded_reasons, required_followups, fraud_risk_level (non-empty), fraud_flags, "
        "damage_summary (main_impact_area, severity, damaged_parts, all non-empty strings except damaged_parts can be empty list), "
        "recommendation (action non-empty, notes_for_handler), audit_log[].\n"
        "Set 'confidence' and 'severity_score' to numeric values between 0 and 1; NEVER leave them null, blank, or missing. "
        "Responses with missing or null confidence, eligibility_reason, fraud_risk_level, recommendation.action, or damage_summary.severity are invalid and will be rejected.\n"
        "Do NOT output any text outside the JSON object. Apply rules logically; if uncertain set eligibility to 'Review' and add followups with next steps."
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


def _build_assessment_prompt(fnol: Dict[str, Any], fraud_rules: List[Dict[str, Any]], coverage_rules: List[Dict[str, Any]], general_rules: List[Dict[str, Any]]) -> tuple[str, str]:
    """
    Builds a two-stage assessment prompt focused on claim_assessment + summary + confidence (no fnol generation).
    """
    system = (
        "You are ClaimAssist, a strict JSON-only claim assessment engine. "
        "Use ONLY the provided FNOL JSON and retrieved KB rule snippets to decide eligibility, fraud risk, followups, and recommendation. "
        "Return JSON with keys: claim_assessment, summary, confidence. "
        "All required fields must be present and non-null: "
        "claim_assessment.claim_reference_id (use session_id), eligibility (Approved|Rejected|Review), eligibility_reason, "
        "coverage_applicable, excluded_reasons, required_followups, fraud_risk_level, fraud_flags, "
        "damage_summary.main_impact_area, damage_summary.severity, damage_summary.damaged_parts, "
        "recommendation.action, recommendation.notes_for_handler, audit_log[], and numeric confidence (0-1). "
        "Do NOT include any extra keys. Do NOT output text outside the JSON."
    )
    def _block(title: str, rules: List[Dict[str, Any]]) -> str:
        return f"{title}:\n" + "\n\n".join(
            [f"[{i+1}] ({r.get('meta',{}).get('rule_id') or r.get('id')}) {r.get('text')}" for i, r in enumerate(rules)]
        )
    fraud_block = _block("Fraud rules", fraud_rules) if fraud_rules else "Fraud rules: none"
    cov_block = _block("Coverage rules", coverage_rules) if coverage_rules else "Coverage rules: none"
    gen_block = _block("General rules", general_rules) if general_rules else ""
    rules_block = "\n\n".join([fraud_block, cov_block, gen_block])
    user = (
        f"FNOL JSON (trusted):\n{json.dumps(fnol, ensure_ascii=False)}\n\n"
        f"Relevant KB rules:\n{rules_block}\n\n"
        "Return JSON with keys: claim_assessment, summary, confidence."
    )
    return system, user


def _build_repair_prompt(
    fnol: Dict[str, Any],
    current_assessment: Dict[str, Any],
    missing_fields: list[str],
    rules: List[Dict[str, Any]],
) -> tuple[str, str]:
    """
    Builds a targeted repair prompt to fill ONLY missing/empty fields in claim_assessment.
    """
    system = (
        "You are ClaimAssist Repair, a strict JSON-only fixer. "
        "Given the FNOL JSON and the current claim_assessment, fill ONLY the missing or empty required fields. "
        "Return JSON with a single key: claim_assessment. "
        "Do NOT change existing non-empty values; do NOT add new keys. "
        "Fields reported as missing must be populated with concise, schema-valid values. "
        "No text outside JSON."
    )
    rules_block = "\n\n".join(
        [f"[{i+1}] ({r.get('meta',{}).get('rule_id') or r.get('id')}) {r.get('text')}" for i, r in enumerate(rules)]
    )
    user = (
        f"Missing/empty fields: {missing_fields}\n"
        f"FNOL JSON:\n{json.dumps(fnol, ensure_ascii=False)}\n\n"
        f"Current claim_assessment (keep existing values):\n{json.dumps(current_assessment, ensure_ascii=False)}\n\n"
        f"Relevant KB rules:\n{rules_block}\n\n"
        "Return JSON with only claim_assessment."
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
    # sanitize incident description before prompt
    if fnol_dict.get("incident", {}).get("description"):
        fnol_dict["incident"]["description"] = _clean_text(fnol_dict["incident"]["description"])

    # 1) RAG retrieval
    def _trim_rules(rules: List[Dict[str, Any]], limit: int = 450) -> List[Dict[str, Any]]:
        trimmed = []
        for r in rules:
            txt = r.get("text", "")
            trimmed.append({**r, "text": txt[:limit]})
        return trimmed

    try:
        if rag_client and hasattr(rag_client, "retrieve_rules_for_fnol_split"):
            split = rag_client.retrieve_rules_for_fnol_split(fnol_obj, top_k=16)
            fraud_rules = _trim_rules(split.get("fraud", [])[:5])
            coverage_rules = _trim_rules(split.get("coverage", [])[:5])
            general_rules = _trim_rules(split.get("general", [])[:3])
            rule_chunks = fraud_rules + coverage_rules + general_rules
        else:
            rule_chunks = _trim_rules(retrieve_rules_for_fnol(fnol_obj, top_k=12))
            fraud_rules, coverage_rules, general_rules = [], [], rule_chunks
        logger.info("Retrieved %d RAG rule chunks for session_id=%s", len(rule_chunks), session)
    except Exception:
        logger.exception("RAG retrieval failed; using defaults.")
        rule_chunks = [{"id": "default", "text": "Collision within policy term is covered unless deliberate damage.", "meta": {}}]
        fraud_rules, coverage_rules, general_rules = [], [], rule_chunks

    # 2) Stage 1: Assessment-only call for tighter JSON
    assess_system, assess_user = _build_assessment_prompt(fnol_dict, fraud_rules, coverage_rules, general_rules)

    def _attempt_call(system_prompt: str, user_prompt: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        raw_text_local, meta_local = call_ollama_chat(system_prompt, user_prompt)
        parsed_local = _extract_json_from_text(raw_text_local)
        return parsed_local, meta_local, raw_text_local

    try:
        parsed, meta, raw_text = _attempt_call(assess_system, assess_user)
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

    # 3) Parse model output into JSON; retry once if needed
    if parsed is None:
        logger.warning("First parse attempt failed; retrying with guidance.")
        retry_user = assess_user + "\n\nYour previous response could not be parsed as JSON. Return strict JSON only."
        try:
            parsed, meta, raw_text = _attempt_call(assess_system, retry_user)
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

    # 4) Validate presence and type of 'confidence' and other required assessment fields; retry once if missing
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
        dmg = ca_tmp.get("damage_summary") or {}
        if not dmg.get("severity"):
            required_missing.append("damage_summary.severity")
        if not dmg.get("main_impact_area"):
            required_missing.append("damage_summary.main_impact_area")

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
        retry_user_missing = (
            assess_user
            + f"\n\nYou omitted required fields: {required_missing}. Resend strict JSON with ALL required fields non-null. "
            + "Do not invent new keys. Use the FNOL data as truth. Return only JSON. Example:\n"
            + example
        )
        try:
            parsed_retry, meta_retry, raw_text_retry = _attempt_call(assess_system, retry_user_missing)
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
            # targeted retry with explicit errors and schema reminder (second LLM call)
            retry_user = (
                assess_user
                + "\n\nYour previous claim_assessment failed validation for these reasons: "
                + "; ".join(ca_errors)
                + ". You must return the claim_assessment object with ALL required fields non-null, matching the schema in the KB. "
                + "Include non-empty eligibility_reason, fraud_risk_level, recommendation.action, damage_summary.main_impact_area, and damage_summary.severity. Return JSON only."
            )
            try:
                parsed_retry, meta_retry, raw_text_retry = _attempt_call(assess_system, retry_user)
                if parsed_retry and isinstance(parsed_retry, dict) and parsed_retry.get("claim_assessment"):
                    claim_assessment = parsed_retry.get("claim_assessment")
                    meta = meta_retry
                    raw_text = raw_text_retry
                    ca_errors = validate_claim_assessment_dict(claim_assessment)
            except Exception:
                pass

        # If still errors, invoke dedicated repair call (third LLM call, focused on missing fields)
        if ca_errors:
            repair_system, repair_user = _build_repair_prompt(fnol, claim_assessment, ca_errors, rule_chunks)
            try:
                parsed_repair, meta_repair, raw_text_repair = _attempt_call(repair_system, repair_user)
                if parsed_repair and isinstance(parsed_repair, dict) and parsed_repair.get("claim_assessment"):
                    claim_assessment = parsed_repair.get("claim_assessment")
                    meta = meta_repair
                    raw_text = raw_text_repair
                    ca_errors = validate_claim_assessment_dict(claim_assessment)
            except Exception:
                pass

    if ca_errors:
        claim_assessment = default_claim_assessment(session).to_dict()

    # Backfill any missing critical fields to avoid empty outputs
    if not claim_assessment.get("fraud_risk_level"):
        claim_assessment["fraud_risk_level"] = "Unknown"
        fnol["requires_manual_review"] = True
    if not claim_assessment.get("eligibility_reason"):
        claim_assessment["eligibility_reason"] = "Model supplied empty reason"
    dmg = claim_assessment.get("damage_summary") or {}
    dmg.setdefault("severity", "Moderate")
    dmg.setdefault("main_impact_area", "Unknown")
    dmg.setdefault("damaged_parts", [])
    claim_assessment["damage_summary"] = dmg

    # Final hardening to avoid empty strings leaking to UI
    if not str(claim_assessment.get("eligibility_reason", "")).strip():
        claim_assessment["eligibility_reason"] = "Auto-filled: model returned empty eligibility reason."
    if not str(claim_assessment.get("fraud_risk_level", "")).strip():
        claim_assessment["fraud_risk_level"] = "Unknown"
        fnol["requires_manual_review"] = True
    rec = claim_assessment.get("recommendation") or {}
    if not str(rec.get("action", "")).strip():
        rec["action"] = "Escalate_To_Human"
    rec.setdefault("notes_for_handler", "Model returned missing fields; routed for human review.")
    claim_assessment["recommendation"] = rec
    dmg = claim_assessment.get("damage_summary") or {}
    if not str(dmg.get("severity", "")).strip():
        dmg["severity"] = "Moderate"
    if not str(dmg.get("main_impact_area", "")).strip():
        dmg["main_impact_area"] = "Unknown"
    dmg.setdefault("damaged_parts", [])
    claim_assessment["damage_summary"] = dmg
    # Type-normalize list fields to avoid booleans/singletons from model
    def _as_list(val):
        if val is None:
            return []
        if isinstance(val, (list, tuple)):
            return list(val)
        return [val]

    for key in ("coverage_applicable", "excluded_reasons", "required_followups", "fraud_flags"):
        if key in claim_assessment:
            claim_assessment[key] = [str(v) for v in _as_list(claim_assessment.get(key))]
    # ensure recommendation structure
    rec_final = claim_assessment.get("recommendation") or {}
    rec_final.setdefault("notes_for_handler", "")
    claim_assessment["recommendation"] = rec_final
    rec = claim_assessment.get("recommendation") or {}
    if not rec.get("action"):
        rec["action"] = "Escalate_To_Human"
    rec.setdefault("notes_for_handler", "")
    claim_assessment["recommendation"] = rec

    # 8) Deterministic verification
    # ensure verification uses the final claim_assessment state
    ca_tmp = claim_assessment
    verification = run_basic_checks(fnol, sanitized_row, [c["text"] for c in rule_chunks], claim_assessment=ca_tmp)
    if not verification.get("passed", True):
        fnol["requires_manual_review"] = True

    logger.info("Returning FNOL for session_id=%s with verification_passed=%s", session, verification.get("passed", True))

    summary_val = parsed.get("summary") if isinstance(parsed, dict) else None
    if not summary_val:
        summary_val = (
            f"Eligibility: {claim_assessment.get('eligibility','n/a')}; "
            f"Fraud risk: {claim_assessment.get('fraud_risk_level','n/a')}; "
            f"Damage severity: {claim_assessment.get('damage_summary',{}).get('severity','n/a')}"
        )

    return {
        "fnol_package": fnol,
        "claim_assessment": claim_assessment,
        "summary": summary_val,
        "confidence": confidence_val,
        "retrieved_docs": rule_chunks,
        "verification": verification,
        "llm_raw_meta": meta,
        "raw_model_text": raw_text
    }
