# schemas/claims.py
"""
Dataclasses for FNOL and claim assessment aligned to knowledge_base/json/KB-FNOL-SCHEMA-OUTPUT-GLOBAL.json.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any, Dict
from datetime import datetime


def _safe_date_str(val) -> Optional[str]:
    if val in (None, "", "null"):
        return None
    try:
        # attempt to parse dates/timestamps gracefully
        if isinstance(val, (datetime, )):
            return val.isoformat()
        return str(val)
    except Exception:
        return None


@dataclass
class WorkshopInfo:
    id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class PolicyInfo:
    policy_id: Optional[str] = None
    status: str = "Unknown"
    coverage_type: str = "Unknown"
    addons: List[str] = field(default_factory=list)
    usage: str = "Unknown"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class VehicleInfo:
    vin: Optional[str] = None
    registration_number: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[float] = None
    odometer: Optional[float] = None


@dataclass
class IncidentInfo:
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    impact_point: str = "Unknown"
    type: str = "Collision"
    description: str = ""
    third_party_involved: Optional[bool] = None


@dataclass
class DocumentInfo:
    police_report_present: bool = False
    dl_present: bool = False
    rc_present: bool = False
    photos_count: int = 0
    estimate_present: bool = False


@dataclass
class DetectedDamage:
    part_name: str
    damage_type: Optional[str] = None
    severity: str = "Minor"


@dataclass
class CVResults:
    damaged_parts: List[DetectedDamage] = field(default_factory=list)
    license_plate_ocr: Optional[str] = None
    vin_ocr: Optional[str] = None
    odometer_ocr: Optional[float] = None
    consistency_with_incident: str = "unknown"
    preexisting_damage_signals: List[str] = field(default_factory=list)


@dataclass
class FNOL:
    source: str = "Other"
    workshop: WorkshopInfo = field(default_factory=WorkshopInfo)
    policy: PolicyInfo = field(default_factory=PolicyInfo)
    vehicle: VehicleInfo = field(default_factory=VehicleInfo)
    incident: IncidentInfo = field(default_factory=IncidentInfo)
    documents: DocumentInfo = field(default_factory=DocumentInfo)
    cv_results: CVResults = field(default_factory=CVResults)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DamagePart:
    part_name: str
    severity: str = "Minor"


@dataclass
class DamageSummary:
    main_impact_area: str = "Unknown"
    severity: str = "Minor"
    damaged_parts: List[DamagePart] = field(default_factory=list)


@dataclass
class Recommendation:
    action: str = "Escalate_To_Human"
    notes_for_handler: str = ""


@dataclass
class AuditLogEntry:
    rule_id: str
    decision_effect: str
    note: str


@dataclass
class ClaimAssessment:
    claim_reference_id: str
    eligibility: str = "Review"
    eligibility_reason: str = ""
    coverage_applicable: List[str] = field(default_factory=list)
    excluded_reasons: List[str] = field(default_factory=list)
    required_followups: List[str] = field(default_factory=list)
    fraud_risk_level: str = "Low"
    fraud_flags: List[str] = field(default_factory=list)
    damage_summary: DamageSummary = field(default_factory=DamageSummary)
    recommendation: Recommendation = field(default_factory=Recommendation)
    audit_log: List[AuditLogEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def fnol_from_row(row: Dict[str, Any], session_id: str) -> FNOL:
    photos = row.get("photos") or []
    incident_time = row.get("incident_time") or ""
    incident_date = None
    incident_time_part = None
    if incident_time:
        # naive split: first date part, second time part
        parts = str(incident_time).split()
        if parts:
            incident_date = _safe_date_str(parts[0])
        if len(parts) > 1:
            incident_time_part = _safe_date_str(parts[1])
    policy_cov = row.get("policy_coverage_type") or row.get("coverage_type") or "Unknown"
    policy_addons = row.get("policy_addons") or row.get("addons") or []
    fnol = FNOL(
        source="Other",
        workshop=WorkshopInfo(email=None),
        policy=PolicyInfo(
            policy_id=row.get("policy_number") or None,
            coverage_type=policy_cov,
            addons=policy_addons if isinstance(policy_addons, list) else []
        ),
        vehicle=VehicleInfo(registration_number=row.get("car_number") or None),
        incident=IncidentInfo(
            date=incident_date,
            time=incident_time_part,
            location=row.get("incident_location") or None,
            impact_point="Unknown",
            type="Collision",
            description=row.get("incident_description") or "",
            third_party_involved=None
        ),
        documents=DocumentInfo(
            photos_count=len(photos) if isinstance(photos, list) else 0
        ),
    )
    return fnol


def validate_claim_assessment_dict(data: Dict[str, Any]) -> List[str]:
    errors = []
    required_top = ["claim_reference_id", "eligibility", "eligibility_reason", "fraud_risk_level", "recommendation"]
    for k in required_top:
        if k not in data or data.get(k) in (None, ""):
            errors.append(f"missing_{k}")
    rec = data.get("recommendation") or {}
    if not rec.get("action"):
        errors.append("missing_recommendation_action")
    return errors


def default_claim_assessment(session_id: str) -> ClaimAssessment:
    return ClaimAssessment(
        claim_reference_id=session_id,
        eligibility="Review",
        eligibility_reason="Validation fallback",
        fraud_risk_level="Medium",
        recommendation=Recommendation(
            action="Escalate_To_Human",
            notes_for_handler="Model output missing required fields; manual review needed."
        )
    )
