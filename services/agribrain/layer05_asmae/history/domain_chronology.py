"""W1 & P1-3: Bitemporal domain chronology, crop/tenant identity governance, and scouting verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

try:
    from services.agribrain.crop_database import get_crop_with_provenance, resolve_crop_code
except ImportError:
    from crop_database import get_crop_with_provenance, resolve_crop_code

def resolve_soil_key(raw: Any) -> str:
    return str(raw or "loam").strip().lower().replace(" ", "_").replace("-", "_") or "loam"

from .world_model_contracts import (
    CONFIRMED_SCOUTING_STATUSES,
    FALLBACK_TENANT_TOKENS,
    CropIntervalRecord,
    DomainIdentityContract,
    ManagementLogRecord,
    ScoutingRecord,
    SoilRevisionRecord,
)


def _parse_iso_utc(raw: Any) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _iso_or_none(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _is_synthetic_label(doc: Mapping[str, Any]) -> bool:
    if doc.get("synthetic") is True or doc.get("isSynthetic") is True:
        return True
    notes = str(doc.get("notes") or "").lower()
    src = str(doc.get("labelSource") or doc.get("source") or "").lower()
    seed_id = str(doc.get("seed_run_id") or "").lower()
    return ("synthetic" in notes) or ("synthetic" in src) or bool(seed_id)


def _resolve_verified_crop_from_fields(*candidates: Any) -> Tuple[str, Optional[str]]:
    for cand in candidates:
        if cand is None:
            continue
        text = str(cand).strip()
        if not text:
            continue
        code = resolve_crop_code(text)
        if code and code != "unknown":
            spec, canon, used_default = get_crop_with_provenance(code)
            if not used_default:
                return canon, spec.architecture
    return "unknown", None


def evaluate_scouting_record(raw_obs: Mapping[str, Any], index: int = 0) -> ScoutingRecord:
    """Apply strict P1-3 confirmation semantics to one CropObservation document."""
    observed_dt = (
        _parse_iso_utc(raw_obs.get("observedAt"))
        or _parse_iso_utc(raw_obs.get("observed_at"))
        or _parse_iso_utc(raw_obs.get("timestamp"))
        or _parse_iso_utc(raw_obs.get("date"))
        or _parse_iso_utc(raw_obs.get("createdAt"))
    )
    created_dt = (
        _parse_iso_utc(raw_obs.get("createdAt"))
        or _parse_iso_utc(raw_obs.get("updatedAt"))
        or observed_dt
    )
    status_token = str(
        raw_obs.get("confirmationStatus")
        or raw_obs.get("confirmation_status")
        or raw_obs.get("status")
        or ""
    ).strip().upper()
    explicit_flag = raw_obs.get("confirmed") is True or raw_obs.get("verified") is True
    confirmed_by = raw_obs.get("confirmedBy") or raw_obs.get("verifiedBy") or raw_obs.get("agronomistId")
    is_confirmed = bool(explicit_flag or status_token in CONFIRMED_SCOUTING_STATUSES)
    confirmation_status = "OBSERVED_CONFIRMED" if is_confirmed else "UNCONFIRMED_SCOUTING"
    return ScoutingRecord(
        record_id=str(raw_obs.get("_id") or raw_obs.get("id") or f"scouting_{index:03d}"),
        obs_type=str(raw_obs.get("type") or raw_obs.get("obs_type") or "field_observation"),
        title=str(raw_obs.get("title") or "Field Scouting Record"),
        severity=(str(raw_obs.get("severity")) if raw_obs.get("severity") is not None else None),
        observed_at=_iso_or_none(observed_dt),
        created_at=_iso_or_none(created_dt),
        is_confirmed=is_confirmed,
        confirmation_status=confirmation_status,
        confirmation_evidence={
            "explicit_confirmed_flag": bool(raw_obs.get("confirmed") is True),
            "explicit_verified_flag": bool(raw_obs.get("verified") is True),
            "status_token": status_token or None,
            "confirmed_by": str(confirmed_by) if confirmed_by else None,
            "observed_at_distinct_from_created_at": bool(
                raw_obs.get("observedAt") or raw_obs.get("observed_at") or raw_obs.get("timestamp")
            ),
            "reason": (
                "affirmative_scouting_confirmation"
                if is_confirmed
                else "missing_explicit_confirmation_status_or_flag"
            ),
        },
        description=(str(raw_obs.get("description")) if raw_obs.get("description") is not None else None),
        crop_cycle_id=(str(raw_obs.get("cropCycleId")) if raw_obs.get("cropCycleId") is not None else None),
    )


@dataclass
class DomainChronology:
    """Bitemporal agronomic timeline supporting (valid_time_T, knowledge_cutoff_K) queries."""

    identity: DomainIdentityContract
    crop_intervals: List[CropIntervalRecord] = field(default_factory=list)
    soil_revisions: List[SoilRevisionRecord] = field(default_factory=list)
    management_records: List[ManagementLogRecord] = field(default_factory=list)
    scouting_records: List[ScoutingRecord] = field(default_factory=list)

    @property
    def confirmed_scouting_records(self) -> List[ScoutingRecord]:
        return [rec for rec in self.scouting_records if rec.is_confirmed]

    @property
    def unconfirmed_scouting_records(self) -> List[ScoutingRecord]:
        return [rec for rec in self.scouting_records if not rec.is_confirmed]

    def _filter_bitemporal(
        self,
        valid_from_raw: Optional[str],
        known_from_raw: Optional[str],
        valid_time_T: datetime,
        knowledge_cutoff_K: datetime,
    ) -> bool:
        vf = _parse_iso_utc(valid_from_raw)
        kf = _parse_iso_utc(known_from_raw) or vf
        if vf is not None and vf > valid_time_T:
            return False
        if kf is not None and kf > knowledge_cutoff_K:
            return False
        return True

    def as_of(
        self,
        valid_time_T: datetime,
        knowledge_cutoff_K: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return only domain facts valid at valid_time_T and known at knowledge_cutoff_K."""
        t_dt = _parse_iso_utc(valid_time_T) or datetime.now(timezone.utc)
        k_dt = _parse_iso_utc(knowledge_cutoff_K) or t_dt

        known_cycles = [
            rec for rec in self.crop_intervals
            if rec.verified and self._filter_bitemporal(None, rec.known_from, t_dt, k_dt)
        ]
        # Active cycle at T among cycles known at K
        active_cycle: Optional[CropIntervalRecord] = None
        upcoming_cycle: Optional[CropIntervalRecord] = None
        for rec in sorted(
            known_cycles,
            key=lambda r: (_parse_iso_utc(r.valid_from) or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        ):
            vf = _parse_iso_utc(rec.valid_from)
            vt = _parse_iso_utc(rec.valid_to)
            if vf is not None and t_dt < vf:
                upcoming_cycle = rec
                continue
            if vt is not None and rec.architecture_class not in {"perennial", "tropical_tree"} and t_dt > vt:
                continue
            active_cycle = rec
            break

        # Physical regime classification at (T, K)
        regime = "UNVERIFIED_CROP_REGIME"
        crop_code = "unknown"
        crop_verified_as_of_k = False
        crop_age_days: Optional[float] = None
        if active_cycle is not None:
            crop_code = active_cycle.crop_code
            crop_verified_as_of_k = True
            vf = _parse_iso_utc(active_cycle.valid_from)
            vt = _parse_iso_utc(active_cycle.valid_to)
            crop_age_days = max(0.0, (t_dt - vf).total_seconds() / 86400.0) if vf is not None else None
            status_up = active_cycle.status.upper()
            if vt is not None and t_dt > vt and active_cycle.architecture_class not in {"perennial", "tropical_tree"}:
                regime = "POST_HARVEST_RESIDUE_OR_FALLOW"
            elif status_up in {"PLANTED", "SEEDED", "TRANSPLANTED"} and (crop_age_days is None or crop_age_days <= 120.0):
                regime = "EARLY_ESTABLISHMENT"
            elif crop_age_days is not None and crop_age_days <= 45.0:
                regime = "EARLY_ESTABLISHMENT"
            else:
                regime = f"ACTIVE_{status_up or 'CROP'}"
        elif upcoming_cycle is not None:
            # Known cycle is scheduled AFTER T -> parcel is pre-planting at valid_time_T
            regime = "PRE_PLANTING_FALLOW_OR_PREP"
        elif any(
            rec.verified and _parse_iso_utc(rec.known_from) is not None and _parse_iso_utc(rec.known_from) <= k_dt
            and _parse_iso_utc(rec.valid_to) is not None and t_dt > _parse_iso_utc(rec.valid_to)
            for rec in self.crop_intervals
        ):
            regime = "POST_HARVEST_RESIDUE_OR_FALLOW"

        soils_as_of = [
            rec for rec in self.soil_revisions
            if self._filter_bitemporal(rec.valid_from, rec.known_from, t_dt, k_dt)
        ]
        mgmt_confirmed = [
            rec for rec in self.management_records
            if rec.is_confirmed_execution and self._filter_bitemporal(rec.valid_from, rec.known_from, t_dt, k_dt)
        ]
        scouting_all = [
            rec for rec in self.scouting_records
            if self._filter_bitemporal(rec.observed_at, rec.created_at, t_dt, k_dt)
        ]
        scouting_confirmed = [rec for rec in scouting_all if rec.is_confirmed]
        scouting_unconfirmed = [rec for rec in scouting_all if not rec.is_confirmed]

        return {
            "valid_time_T": t_dt.isoformat(),
            "knowledge_cutoff_K": k_dt.isoformat(),
            "crop_verified_as_of_k": crop_verified_as_of_k,
            "verified_crop_code": crop_code if crop_verified_as_of_k else None,
            "active_crop_cycle": active_cycle.to_dict() if active_cycle is not None else None,
            "upcoming_known_cycle": upcoming_cycle.to_dict() if upcoming_cycle is not None else None,
            "physical_regime": regime,
            "crop_age_days": round(crop_age_days, 2) if crop_age_days is not None else None,
            "soil_revisions": [rec.to_dict() for rec in soils_as_of],
            "confirmed_management": [rec.to_dict() for rec in mgmt_confirmed],
            "confirmed_scouting": [rec.to_dict() for rec in scouting_confirmed],
            "unconfirmed_scouting": [rec.to_dict() for rec in scouting_unconfirmed],
            "withheld_future_crop_cycles_count": max(0, len([r for r in self.crop_intervals if r.verified]) - len(known_cycles)),
        }

    def to_summary(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "crop_intervals_count": len(self.crop_intervals),
            "verified_crop_intervals_count": len([r for r in self.crop_intervals if r.verified]),
            "crop_intervals": [r.to_dict() for r in self.crop_intervals],
            "soil_revisions_count": len(self.soil_revisions),
            "soil_revisions": [r.to_dict() for r in self.soil_revisions],
            "confirmed_management_count": len([r for r in self.management_records if r.is_confirmed_execution]),
            "planned_unconfirmed_tasks_count": len([r for r in self.management_records if not r.is_confirmed_execution]),
            "confirmed_scouting_count": len(self.confirmed_scouting_records),
            "unconfirmed_scouting_count": len(self.unconfirmed_scouting_records),
            "scouting_confirmation_enforced": True,
        }


def build_domain_chronology(
    *,
    plot_id: str,
    plot_doc: Optional[Mapping[str, Any]] = None,
    farm_doc: Optional[Mapping[str, Any]] = None,
    crop_cycles: Optional[Iterable[Mapping[str, Any]]] = None,
    confirmed_crop_labels: Optional[Iterable[Mapping[str, Any]]] = None,
    soil_analyses: Optional[Iterable[Mapping[str, Any]]] = None,
    crop_tasks: Optional[Iterable[Mapping[str, Any]]] = None,
    crop_observations: Optional[Iterable[Mapping[str, Any]]] = None,
    explicit_tenant_id: Optional[str] = None,
) -> Tuple[DomainIdentityContract, DomainChronology]:
    """Construct verified DomainIdentityContract + bitemporal DomainChronology without silent guessing."""
    p_doc = dict(plot_doc or {})
    f_doc = dict(farm_doc or {})

    db_tenant = str(p_doc.get("tenantId") or f_doc.get("tenantId") or "").strip() or None
    if db_tenant and db_tenant.lower() not in FALLBACK_TENANT_TOKENS:
        tenant_id = db_tenant
        tenant_verified = True
        is_isolated_dev_fixture = False
        tenant_source = "plot_or_farm_doc_tenant_id"
    elif explicit_tenant_id and str(explicit_tenant_id).strip().lower() not in FALLBACK_TENANT_TOKENS:
        tenant_id = str(explicit_tenant_id).strip()
        # Explicit partition exists for sandbox/pilot isolation, but DB doc itself lacked tenantId
        tenant_verified = False
        is_isolated_dev_fixture = True
        tenant_source = "explicit_pilot_partition_db_tenant_missing"
    else:
        tenant_id = "default_tenant"
        tenant_verified = False
        is_isolated_dev_fixture = True
        tenant_source = "fallback_default_tenant"

    farm_id = str(p_doc.get("farmId") or f_doc.get("_id") or "").strip() or None
    plot_name = str(p_doc.get("name") or "").strip() or None

    # Sort CropCycles newest createdAt/plantDate first, retaining ALL intervals chronologically
    intervals: List[CropIntervalRecord] = []
    for idx, cc in enumerate(crop_cycles or []):
        if not isinstance(cc, Mapping):
            continue
        code, arch = _resolve_verified_crop_from_fields(
            cc.get("cropCode"), cc.get("cropType"), cc.get("crop"), cc.get("variety")
        )
        valid_from_dt = _parse_iso_utc(cc.get("plantDate") or cc.get("startDate") or cc.get("createdAt"))
        valid_to_dt = _parse_iso_utc(cc.get("harvestDate") or cc.get("actualHarvest") or cc.get("expectedHarvest") or cc.get("endDate"))
        known_from_dt = _parse_iso_utc(cc.get("createdAt") or cc.get("updatedAt") or valid_from_dt)
        verified = code != "unknown"
        intervals.append(CropIntervalRecord(
            record_id=str(cc.get("_id") or cc.get("id") or f"cc_{idx:03d}"),
            crop_code=code,
            variety=(str(cc.get("variety")) if cc.get("variety") is not None else None),
            status=str(cc.get("status") or cc.get("stage") or "UNKNOWN").upper(),
            valid_from=_iso_or_none(valid_from_dt),
            valid_to=_iso_or_none(valid_to_dt),
            known_from=_iso_or_none(known_from_dt),
            source="crop_cycle" if cc.get("cropCode") or cc.get("cropType") else "crop_cycle_variety",
            verified=verified,
            synthetic_rejected=False,
            architecture_class=arch,
            estimated_yield=(float(cc["estimatedYield"]) if isinstance(cc.get("estimatedYield"), (int, float)) else None),
            notes=(str(cc.get("notes")) if cc.get("notes") is not None else None),
        ))

    synthetic_rejected = False
    verified_ccl: List[CropIntervalRecord] = []
    for idx, lbl in enumerate(confirmed_crop_labels or []):
        if not isinstance(lbl, Mapping):
            continue
        if _is_synthetic_label(lbl):
            synthetic_rejected = True
            intervals.append(CropIntervalRecord(
                record_id=str(lbl.get("labelId") or lbl.get("_id") or f"ccl_{idx:03d}"),
                crop_code=str(lbl.get("cropCode") or "unknown"),
                variety=None,
                status="SYNTHETIC_REJECTED",
                valid_from=_iso_or_none(_parse_iso_utc(lbl.get("plantingDate"))),
                valid_to=_iso_or_none(_parse_iso_utc(lbl.get("harvestDate"))),
                known_from=_iso_or_none(_parse_iso_utc(lbl.get("createdAt"))),
                source="confirmed_crop_label_synthetic",
                verified=False,
                synthetic_rejected=True,
                notes=str(lbl.get("notes") or ""),
            ))
            continue
        code, arch = _resolve_verified_crop_from_fields(lbl.get("cropCode"), lbl.get("cropGroup"))
        if code != "unknown" and str(lbl.get("labelSource") or "").lower() not in {"", "synthetic"}:
            verified_ccl.append(CropIntervalRecord(
                record_id=str(lbl.get("labelId") or lbl.get("_id") or f"ccl_{idx:03d}"),
                crop_code=code,
                variety=None,
                status="CONFIRMED_LABEL",
                valid_from=_iso_or_none(_parse_iso_utc(lbl.get("plantingDate") or lbl.get("createdAt"))),
                valid_to=_iso_or_none(_parse_iso_utc(lbl.get("harvestDate"))),
                known_from=_iso_or_none(_parse_iso_utc(lbl.get("createdAt"))),
                source="confirmed_crop_label_non_synthetic",
                verified=True,
                synthetic_rejected=False,
                architecture_class=arch,
                notes=(str(lbl.get("notes")) if lbl.get("notes") else None),
            ))

    verified_cycles = [rec for rec in intervals if rec.verified]
    if verified_cycles:
        latest_verified = sorted(
            verified_cycles,
            key=lambda r: (_parse_iso_utc(r.known_from) or _parse_iso_utc(r.valid_from) or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )[0]
        resolved_crop_code = latest_verified.crop_code
        crop_variety = latest_verified.variety
        crop_arch = latest_verified.architecture_class
        crop_verified = True
        crop_source = latest_verified.source
    elif verified_ccl:
        latest_ccl = verified_ccl[-1]
        resolved_crop_code = latest_ccl.crop_code
        crop_variety = None
        crop_arch = latest_ccl.architecture_class
        crop_verified = True
        crop_source = latest_ccl.source
        intervals.extend(verified_ccl)
    else:
        resolved_crop_code = "unknown"
        crop_variety = None
        crop_arch = None
        crop_verified = False
        crop_source = "none_eo_crop_posterior_required"

    # Soil identity resolution
    raw_soils = [dict(sa) for sa in (soil_analyses or []) if isinstance(sa, Mapping)]
    soil_revs: List[SoilRevisionRecord] = []
    for idx, sa in enumerate(raw_soils):
        tex = str(sa.get("texture") or "").strip() or None
        dt_v = _parse_iso_utc(sa.get("date") or sa.get("createdAt"))
        dt_k = _parse_iso_utc(sa.get("createdAt") or dt_v)
        soil_revs.append(SoilRevisionRecord(
            record_id=str(sa.get("_id") or sa.get("id") or f"soil_{idx:03d}"),
            texture=tex,
            ph=(float(sa["ph"]) if isinstance(sa.get("ph"), (int, float)) else None),
            ec=(float(sa["ec"]) if isinstance(sa.get("ec"), (int, float)) else None),
            organic_matter=(float(sa["organicMatter"]) if isinstance(sa.get("organicMatter"), (int, float)) else None),
            nitrogen=(float(sa["nitrogen"]) if isinstance(sa.get("nitrogen"), (int, float)) else None),
            phosphorus=(float(sa["phosphorus"]) if isinstance(sa.get("phosphorus"), (int, float)) else None),
            potassium=(float(sa["potassium"]) if isinstance(sa.get("potassium"), (int, float)) else None),
            depth_from_cm=(float(sa["depthFrom"]) if isinstance(sa.get("depthFrom"), (int, float)) else None),
            depth_to_cm=(float(sa["depthTo"]) if isinstance(sa.get("depthTo"), (int, float)) else None),
            valid_from=_iso_or_none(dt_v),
            known_from=_iso_or_none(dt_k),
            source="soil_analysis",
            verified=bool(tex or any(sa.get(k) is not None for k in ("ph", "ec", "organicMatter"))),
        ))

    if any(r.texture for r in soil_revs):
        latest_soil = [r for r in soil_revs if r.texture][-1]
        soil_texture = resolve_soil_key(latest_soil.texture)
        soil_verified = True
        soil_source = "soil_analysis"
    elif p_doc.get("soilType"):
        soil_texture = resolve_soil_key(str(p_doc["soilType"]))
        soil_verified = True
        soil_source = "plot_doc_soil_type"
    else:
        soil_texture = "loam"
        soil_verified = False
        soil_source = "fallback_unverified"

    mgmt_records: List[ManagementLogRecord] = []
    for idx, tk in enumerate(crop_tasks or []):
        if not isinstance(tk, Mapping):
            continue
        status_tok = str(tk.get("status") or "").strip().upper()
        is_comp = bool(tk.get("completed") is True or status_tok in {"COMPLETED", "APPLIED", "EXECUTED", "OBSERVED_CONFIRMED"})
        vf_dt = _parse_iso_utc(tk.get("completedAt") or tk.get("executedAt") or tk.get("appliedDate") or tk.get("dueDate") or tk.get("createdAt"))
        kf_dt = _parse_iso_utc(tk.get("updatedAt") or tk.get("createdAt") or vf_dt)
        mgmt_records.append(ManagementLogRecord(
            record_id=str(tk.get("_id") or tk.get("id") or f"task_{idx:03d}"),
            task_type=str(tk.get("type") or "TASK"),
            title=str(tk.get("title") or "Agronomic Task"),
            completed=bool(tk.get("completed") is True),
            is_confirmed_execution=is_comp,
            valid_from=_iso_or_none(vf_dt),
            known_from=_iso_or_none(kf_dt),
            source="crop_task",
            crop_cycle_id=(str(tk.get("cropCycleId")) if tk.get("cropCycleId") is not None else None),
        ))

    scouting_list = [
        evaluate_scouting_record(obs, idx)
        for idx, obs in enumerate(crop_observations or [])
        if isinstance(obs, Mapping)
    ]

    block_reasons: List[str] = []
    if not crop_verified:
        block_reasons.append("unverified_crop_identity")
    if synthetic_rejected and not crop_verified:
        block_reasons.append("synthetic_crop_label_rejected")
    if tenant_id in FALLBACK_TENANT_TOKENS:
        block_reasons.append("unverified_tenant_identity")
    if not soil_verified:
        block_reasons.append("unverified_soil_identity")

    identity = DomainIdentityContract(
        plot_id=str(plot_id),
        tenant_id=tenant_id,
        farm_id=farm_id,
        tenant_identity_verified=tenant_verified,
        is_isolated_dev_fixture=is_isolated_dev_fixture,
        tenant_resolution_source=tenant_source,
        crop_identity_verified=crop_verified,
        synthetic_label_rejected=synthetic_rejected,
        crop_resolution_source=crop_source,
        resolved_crop_code=resolved_crop_code,
        crop_variety=crop_variety,
        crop_architecture_class=crop_arch,
        soil_identity_verified=soil_verified,
        soil_texture=soil_texture,
        soil_resolution_source=soil_source,
        identity_block_reasons=tuple(block_reasons),
        diagnostic_fallback_crop=None,
        plot_name=plot_name,
    )
    chronology = DomainChronology(
        identity=identity,
        crop_intervals=intervals,
        soil_revisions=soil_revs,
        management_records=mgmt_records,
        scouting_records=scouting_list,
    )
    return identity, chronology


__all__ = [
    "DomainChronology",
    "build_domain_chronology",
    "evaluate_scouting_record",
]
