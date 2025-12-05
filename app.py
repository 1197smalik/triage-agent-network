# streamlit_app/app.py
import json
import logging
import traceback
from datetime import datetime, date

import streamlit as st

from schemas.claims import default_claim_assessment
from streamlit_app.utils.excel_parser import parse_excel_to_df
from streamlit_app.utils.pii_sanitizer import mask_pii_df
from streamlit_app.utils.validator import assign_policy_tags
from core.use_cases import process_row


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _json_default(o):
    try:
        import pandas as pd
    except Exception:
        pd = None
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if pd and isinstance(o, pd.Timestamp):
        return o.isoformat()
    return str(o)


def _stringify_list(val):
    if not val:
        return ["None"]
    if isinstance(val, (str, bool)):
        return [str(val)]
    try:
        return [v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in val]
    except TypeError:
        return [str(val)]


def _go_to_detail(action: str, payload: dict, row_idx: int):
    st.session_state["nav_view"] = {"action": action, "payload": payload, "row_idx": row_idx}
    st.query_params["view"] = "detail"
    st.query_params["row"] = str(row_idx)


def _clear_nav_view():
    st.session_state.pop("nav_view", None)
    st.query_params.clear()


def _render_nav_view():
    nav = st.session_state.get("nav_view")
    query = st.query_params
    if not nav and query.get("view") == ["detail"]:
        row_q = query.get("row", [None])[0]
        if row_q is not None:
            try:
                idx = int(row_q)
                stored = st.session_state.get("fnol_results", [])
                if 0 <= idx < len(stored):
                    st.session_state["nav_view"] = {
                        "action": "process",
                        "payload": stored[idx],
                        "row_idx": idx,
                    }
                    nav = st.session_state["nav_view"]
            except Exception:
                pass
    if not nav:
        return
    action = nav.get("action", "Review")
    data = nav.get("payload", {})
    row_idx = nav.get("row_idx", 0)
    st.markdown(f"### {'✅' if action=='process' else '📝'} {action.title()} Claim (Row {row_idx+1})")
    ca = data.get("claim_assessment", {})
    fnol = data.get("fnol_package", {})
    st.write(f"Session: {fnol.get('session_id','n/a')}")
    st.write(f"Eligibility: {ca.get('eligibility','n/a')} — {ca.get('eligibility_reason','n/a')}")
    st.write(f"Fraud risk: {ca.get('fraud_risk_level','n/a')}")
    st.write(f"Recommendation: {ca.get('recommendation',{}).get('action','n/a')}")
    st.write(f"Followups: {', '.join(_stringify_list(ca.get('required_followups')))}")
    st.json(data, expanded=False)
    if st.button("Back to results", key="back-to-results"):
        _clear_nav_view()
    st.stop()


def _render_rows(rows, results_container, existing=False):
    for idx, out in enumerate(rows):
        with results_container:
            fnol_data = out.get("fnol_package") or {}
            if fnol_data:
                sid = fnol_data.get("session_id", "n/a")
                ca = out.get("claim_assessment") or default_claim_assessment(sid).to_dict()
                claim_ref = ca.get("claim_reference_id", sid)
                eligibility = ca.get("eligibility", "?")
                fraud_risk = ca.get("fraud_risk_level", "?")
                severity_val = (ca.get("damage_summary") or {}).get("severity", "")
                severity = severity_val.lower() if isinstance(severity_val, str) else ""
                color_map = {
                    "high": "red",
                    "severe": "red",
                    "medium": "darkorange",
                    "moderate": "darkorange",
                    "low": "gold"
                }
                sev_color = color_map.get(severity, "inherit")
                severity_text = f"<span style='color:{sev_color}; font-weight:600'>{severity.title() if severity else 'Unknown'}</span>"
                process_ready = (
                    ca.get("eligibility") == "Approved"
                    and not ca.get("required_followups")
                    and not fnol_data.get("requires_manual_review")
                    and out.get("verification", {}).get("passed", False)
                )
                row_number = idx + 1
                duration = out.get("_duration_s")
                duration_text = f" | {duration:.1f}s" if isinstance(duration, (int, float)) else ""
                summary_label = f"Row {row_number} — Ref {claim_ref} | Eligibility: {eligibility} | Fraud: {fraud_risk} | Severity: {severity.title() if severity else 'Unknown'}{duration_text}"
                row_container = st.container()
                if process_ready:
                    row_container.markdown("<div style='background-color:#e8f5e9; padding:8px; border-radius:6px;'>", unsafe_allow_html=True)
                with row_container.expander(summary_label, expanded=False):
                    st.markdown(f"Severity: {severity_text}", unsafe_allow_html=True)
                    st.write(f"Summary: {out.get('summary', '(no summary provided)')}")
                    st.write(f"Eligibility reason: {ca.get('eligibility_reason', 'n/a')}")
                    st.write(f"Fraud risk: {fraud_risk}")
                    rec_action = ca.get("recommendation", {}).get("action", "")
                    btn_label = "Process Claim" if rec_action == "Proceed_With_Claim" and not fnol_data.get("requires_manual_review") else "Review Claim"
                    st.button(
                        btn_label,
                        key=f"claim-action-prev-{idx}" if existing else f"claim-action-{idx}",
                        on_click=_go_to_detail,
                        args=("process" if "Process" in btn_label else "review", out, idx),
                    )
                    st.write(f"Required followups: {', '.join(_stringify_list(ca.get('required_followups')))}")
                    st.write(f"Fraud flags: {', '.join(_stringify_list(ca.get('fraud_flags')))}")
                    st.write(f"Coverage applicable: {', '.join(_stringify_list(ca.get('coverage_applicable')))}")
                    st.write(f"Excluded reasons: {', '.join(_stringify_list(ca.get('excluded_reasons')))}")
                    st.write(f"Recommendation: {ca.get('recommendation', {}).get('action', 'n/a')} — {ca.get('recommendation', {}).get('notes_for_handler', '')}")
                    with st.expander("More details", expanded=False):
                        policy = fnol_data.get("policy") if isinstance(fnol_data.get("policy"), dict) else {}
                        policy_cov = policy.get("coverage_type") or fnol_data.get("policy_coverage_type") or "n/a"
                        policy_addons = policy.get("addons") if isinstance(policy, dict) else []
                        st.write(f"Incident time: {fnol_data.get('incident_time', 'n/a')}")
                        st.write(f"Incident location: {fnol_data.get('incident_location', 'n/a')}")
                        st.write(f"Damage regions: {', '.join(fnol_data.get('damage_regions', []) or ['n/a'])}")
                        st.write(f"Missing fields: {', '.join(fnol_data.get('missing_fields', []) or ['None'])}")
                        st.write(f"Coverage indicator: {fnol_data.get('coverage_indicator', 'n/a')}")
                        st.write(f"Policy coverage type: {policy_cov}")
                        st.write(f"Policy addons: {', '.join(policy_addons or []) or 'n/a'}")
                        st.write(f"Manual review: {fnol_data.get('requires_manual_review', False)}")
                        st.write(f"Confidence: {out.get('confidence', 'n/a')}")
                        st.write(f"Verification passed: {out.get('verification', {}).get('passed', 'n/a')}")
                        st.write(f"Cited docs: {len(fnol_data.get('cited_docs', []) or [])}")
                if process_ready:
                    row_container.markdown("</div>", unsafe_allow_html=True)
            else:
                sid = out.get("session_id", "n/a")
                row_number = idx + 1
                label = f"Row {row_number} — error (session {sid})"
                with st.expander(label, expanded=False):
                    st.warning(out.get("error", "Unknown error"))
                    if out.get("reason"):
                        st.write(f"Reason: {out.get('reason')}")
                    fallback = out.get("fallback", {})
                    if isinstance(fallback, dict):
                        st.write("Fallback summary:", fallback.get("summary", "n/a"))

st.set_page_config(page_title="FNOL Intake Assistant (POC)", layout="wide")
st.title("🚗 FNOL Intake Assistant — Streamlit POC (PII masked)")

st.markdown("Upload a synthetic Excel file (sample in /sample_data). The app will mask PII, run validators and produce a synthetic FNOL package per row.")
_render_nav_view()

uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
sample_button = st.button("Load sample data")

if sample_button:
    logger.info("Sample data button clicked; preparing download.")
    with open("./sample_data/sample_claims.xlsx", "rb") as f:
        st.download_button("Download sample Excel", f.read(), file_name="sample_claims.xlsx")

if uploaded_file:
    try:
        logger.info("Uploaded file received: %s", uploaded_file.name)
        df = parse_excel_to_df(uploaded_file)
        logger.info("Excel parsed to dataframe with %d rows.", len(df))
        st.success("Excel parsed")
        st.subheader("Original (display only)")
        st.dataframe(df)

        st.subheader("Sanitized preview (tokens only)")
        masked = mask_pii_df(df)
        masked = assign_policy_tags(masked)
        logger.info("PII masked; proceeding to preview and processing.")
        st.dataframe(masked)

        if st.button("Process FNOL (Ollama)"):
            logger.info("FNOL processing triggered via Ollama.")
            rows = masked.to_dict(orient="records")
            total = len(rows)
            progress = st.progress(0, text=f"Processed 0/{total}")
            status_box = st.empty()
            results_container = st.container()
            results = []

            for idx, r in enumerate(rows):
                logger.info("Processing row %d for session build.", idx)
                row_start = datetime.now()
                status_box.info(f"Processing row {idx+1} of {total}...")
                out = process_row(r)
                row_duration = (datetime.now() - row_start).total_seconds()
                out["_duration_s"] = row_duration
                results.append(out)

                # update UI incrementally
                _render_rows([out], results_container)
                progress.progress((idx + 1) / total, text=f"Processing {idx+1}/{total}")

            logger.info("FNOL processing complete; %d rows.", len(results))
            st.session_state["fnol_results"] = results
            st.success("Processed via Ollama")
            st.download_button("Download results JSON", json.dumps(results, indent=2, default=_json_default), file_name="fnol_results.json")
        else:
            # If results already present, render them so they persist across reruns
            if st.session_state.get("fnol_results"):
                st.info("Showing previously processed results.")
                rows = st.session_state["fnol_results"]
                results_container = st.container()
                _render_rows(rows, results_container, existing=True)
    except Exception:
        logger.exception("Failed to process file via Streamlit app.")
        st.error("⚠️ Failed to process file. Full traceback below:")
        st.code(traceback.format_exc())
else:
    st.info("Waiting for Excel upload...")
