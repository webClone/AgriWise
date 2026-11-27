"""W1 & P1-3: Bitemporal domain chronology, crop/tenant identity governance, and scouting verification (V2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

try:
    from services.agribrain.crop_database import get_crop_with_provenance, resolve_crop_code
except ImportError:
    from crop_database import get_crop_with_provenance, resolve_crop_code

from .world_model_contracts import (
    CONFIRMED_CROP_AUTHORITIES,
    CONFIRMED_SCOUTING_STATUSES,
    FALLBACK_TENANT_TOKENS,
    CropIntervalRecord,
    DomainIdentityContract,
    ManagementLogRecord,
    ScoutingRecord,
    SoilRevisionRecord,
)


def resolve_soil_key(raw: Any) -> str:
    return str(raw or "loam").strip().lower().replace(" ", "_").replace("-", "_") or "loam"


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


def _resolve_cycle_authority(cc: Mapping[str, Any], code: str) -> Tuple[str, bool, str]:
    """Separate registry recognition from confirmed farmer/agronomist crop authority (WM1-P1-02)."""
    if code == "unknown":
        return "UNKNOWN", False, "unknown"
    raw_auth = str(
        cc.get("declaredCropAuthority")
        or cc.get("cropAuthority")
        or cc.get("declared_crop_authority")
        or cc.get("authority")
        or ""
    ).strip().upper()
    explicit_src = str(
        cc.get("declaredCropSource") or cc.get("declared_crop_source") or cc.get("source") or ""
    ).strip()

    if raw_auth in CONFIRMED_CROP_AUTHORITIES:
        return raw_auth, True, explicit_src or "authenticated_cycle_declaration"
    if cc.get("confirmedByAgronomist") is True:
        return "AGRONOMIST_CONFIRMED", True, explicit_src or "agronomist_confirmation"
    if cc.get("confirmed") is True or cc.get("verified") is True or cc.get("cropConfirmedByUser") is True:
        return "FARMER_CONFIRMED", True, explicit_src or "explicit_cycle_confirmation_flag"
    return "REGISTRY_DECLARED", False, explicit_src or "crop_cycle_registry_entry"


def _resolve_confirmed_label_authority(lbl: Mapping[str, Any]) -> Tuple[str, bool, str]:
    """Resolve confirmation authority on a non-synthetic ConfirmedCropLabel record."""
    src_raw = str(lbl.get("labelSource") or lbl.get("source") or "").strip()
    src_low = src_raw.lower()
    raw_auth = str(
        lbl.get("authority")
        or lbl.get("declaredCropAuthority")
        or lbl.get("labelAuthority")
        or ""
    ).strip().upper()

    if raw_auth in CONFIRMED_CROP_AUTHORITIES:
        return raw_auth, True, src_raw or "confirmed_crop_label"
    if src_low in {"agronomist", "agronomist_confirmed"} or lbl.get("confirmedByAgronomist") is True:
        return "AGRONOMIST_CONFIRMED", True, src_raw
    if src_low in {"official_parcel_label", "official_registry", "parcel_registry"}:
        return "OFFICIAL_PARCEL_LABEL", True, src_raw
    if src_low in {"farmer_confirmed", "field_verified"} or (
        src_low in {"user_confirmed"} or lbl.get("confirmed") is True or lbl.get("verified") is True
    ):
        return ("USER_CONFIRMED" if src_low == "user_confirmed" else "FARMER_CONFIRMED"), True, (src_raw or "confirmed_crop_label")
    return "REGISTRY_DECLARED", False, src_raw or "unverified_label_source"


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
    raw_confirmer = (
        raw_obs.get("confirmedBy")
        or raw_obs.get("verifiedBy")
        or raw_obs.get("agronomistId")
        or raw_obs.get("confirmerId")
        or ""
    )
    confirmer_str = str(raw_confirmer).strip()
    has_verified_confirmer = bool(
        confirmer_str and confirmer_str.lower() not in {"unknown", "none", "null", "system", "auto", "mock"}
    )
    confirmed_ts_dt = _parse_iso_utc(
        raw_obs.get("confirmedAt")
        or raw_obs.get("verifiedAt")
        or raw_obs.get("confirmationTimestamp")
    )
    has_confirmation_claim = bool(explicit_flag or status_token in CONFIRMED_SCOUTING_STATUSES)
    is_confirmed = bool(has_confirmation_claim and has_verified_confirmer and confirmed_ts_dt is not None)
    if is_confirmed:
        confirmation_status = "OBSERVED_CONFIRMED"
        conf_reason = "affirmative_scouting_confirmation_with_verifier_and_timestamp"
    elif has_confirmation_claim:
        confirmation_status = "UNCONFIRMED_MISSING_CONFIRMER_OR_TIMESTAMP"
        conf_reason = "confirmation_claim_rejected_missing_confirmer_or_timestamp"
    else:
        confirmation_status = "UNCONFIRMED_SCOUTING"
        conf_reason = "missing_explicit_confirmation_status_or_flag"
    known_from_dt = confirmed_ts_dt or created_dt
    return ScoutingRecord(
        record_id=str(raw_obs.get("_id") or raw_obs.get("id") or f"scouting_{index:03d}"),
        obs_type=str(raw_obs.get("type") or raw_obs.get("obs_type") or "field_observation"),
        title=str(raw_obs.get("title") or "Field Scouting Record"),
        severity=(str(raw_obs.get("severity")) if raw_obs.get("severity") is not None else None),
        observed_at=_iso_or_none(observed_dt),
        created_at=_iso_or_none(known_from_dt),
        is_confirmed=is_confirmed,
        confirmation_status=confirmation_status,
        confirmation_evidence={
            "explicit_confirmed_flag": bool(raw_obs.get("confirmed") is True),
            "explicit_verified_flag": bool(raw_obs.get("verified") is True),
            "status_token": status_token or None,
            "confirmed_by": confirmer_str or None,
            "confirmed_at": _iso_or_none(confirmed_ts_dt),
            "observed_at_distinct_from_created_at": bool(
                raw_obs.get("observedAt") or raw_obs.get("observed_at") or raw_obs.get("timestamp")
            ),
            "reason": conf_reason,
        },
        description=(str(raw_obs.get("description")) if raw_obs.get("description") is not None else None),
        crop_cycle_id=(str(raw_obs.get("cropCycleId")) if raw_obs.get("cropCycleId") is not None else None),
    )


def _interval_rank(rec: CropIntervalRecord) -> Tuple[int, float, float]:
    auth_priority = 2 if (rec.confirmed and rec.authority in CONFIRMED_CROP_AUTHORITIES) else (1 if rec.registry_recognized else 0)
    vf_ts = (_parse_iso_utc(rec.valid_from) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()
    kf_ts = (_parse_iso_utc(rec.known_from) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()
    return (auth_priority, kf_ts, vf_ts)


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

        known_intervals = [
            rec for rec in self.crop_intervals
            if not rec.synthetic_rejected
            and (rec.confirmed or rec.registry_recognized)
            and self._filter_bitemporal(None, rec.known_from, t_dt, k_dt)
        ]

        active_candidates: List[CropIntervalRecord] = []
        upcoming_candidates: List[CropIntervalRecord] = []
        past_harvested_candidates: List[CropIntervalRecord] = []
        for rec in known_intervals:
            vf = _parse_iso_utc(rec.valid_from)
            vt = _parse_iso_utc(rec.valid_to)
            if vf is not None and t_dt < vf:
                upcoming_candidates.append(rec)
                continue
            if vt is not None and rec.architecture_class not in {"perennial", "tropical_tree"} and t_dt > vt:
                past_harvested_candidates.append(rec)
                continue
            active_candidates.append(rec)

        confirmed_active = sorted(
            [r for r in active_candidates if r.confirmed and r.verified],
            key=_interval_rank,
            reverse=True,
        )
        all_active = sorted(active_candidates, key=_interval_rank, reverse=True)
        active_confirmed = confirmed_active[0] if confirmed_active else None
        active_cycle = all_active[0] if all_active else None
        upcoming_cycle = (
            sorted(upcoming_candidates, key=lambda r: (_parse_iso_utc(r.valid_from) or datetime.max.replace(tzinfo=timezone.utc)))[0]
            if upcoming_candidates
            else None
        )

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

        # Independent fallow / soil-prep verification (WM1-P2-11)
        has_independent_prep = any(
            rec.task_type.upper() in {"SOIL_PREP", "TILLAGE", "PLOWING", "FALLOW_PREP"}
            and (_parse_iso_utc(rec.valid_from) or t_dt) >= (t_dt - timedelta(days=90))
            for rec in mgmt_confirmed
        ) or any(
            "fallow" in f"{s.obs_type} {s.title} {s.description or ''}".lower()
            or "bare_soil" in f"{s.obs_type} {s.title} {s.description or ''}".lower()
            for s in scouting_confirmed
        )

        regime = "UNVERIFIED_CROP_REGIME"
        crop_code = "unknown"
        crop_verified_as_of_k = active_confirmed is not None
        crop_declared_as_of_k = active_cycle is not None
        crop_authority = active_cycle.authority if active_cycle is not None else "UNKNOWN"
        crop_age_days: Optional[float] = None
        fallow_support_source: Optional[str] = None

        if active_cycle is not None:
            crop_code = active_cycle.crop_code
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
            # WM1-P2-11: Do NOT infer historical fallow solely from a future planting record.
            if has_independent_prep:
                regime = "PRE_PLANTING_FALLOW_OR_PREP"
                fallow_support_source = "confirmed_management_or_scouting"
            else:
                regime = "PRE_KNOWN_CYCLE_UNKNOWN"
                fallow_support_source = "none_future_cycle_only"
        elif past_harvested_candidates:
            regime = "POST_HARVEST_RESIDUE_OR_FALLOW"
        elif has_independent_prep:
            regime = "PRE_PLANTING_FALLOW_OR_PREP"
            fallow_support_source = "confirmed_management_or_scouting"

        total_recognized_intervals = len(
            [r for r in self.crop_intervals if not r.synthetic_rejected and (r.confirmed or r.registry_recognized)]
        )
        return {
            "valid_time_T": t_dt.isoformat(),
            "knowledge_cutoff_K": k_dt.isoformat(),
            "crop_verified_as_of_k": crop_verified_as_of_k,
            "crop_declared_as_of_k": crop_declared_as_of_k,
            "verified_crop_code": active_confirmed.crop_code if active_confirmed is not None else None,
            "declared_crop_code": crop_code if crop_declared_as_of_k else None,
            "crop_authority": crop_authority,
            "crop_declared_at": active_cycle.declared_at if active_cycle is not None else None,
            "crop_declared_source": active_cycle.confirmation_source if active_cycle is not None else "unknown",
            "active_crop_cycle": active_cycle.to_dict() if active_cycle is not None else None,
            "upcoming_known_cycle": upcoming_cycle.to_dict() if upcoming_cycle is not None else None,
            "physical_regime": regime,
            "fallow_support_source": fallow_support_source,
            "crop_age_days": round(crop_age_days, 2) if crop_age_days is not None else None,
            "soil_revisions": [rec.to_dict() for rec in soils_as_of],
            "confirmed_management": [rec.to_dict() for rec in mgmt_confirmed],
            "confirmed_scouting": [rec.to_dict() for rec in scouting_confirmed],
            "unconfirmed_scouting": [rec.to_dict() for rec in scouting_unconfirmed],
            "withheld_future_crop_cycles_count": max(0, total_recognized_intervals - len(known_intervals)),
        }

    def to_summary(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "crop_intervals_count": len(self.crop_intervals),
            "verified_crop_intervals_count": len([r for r in self.crop_intervals if r.confirmed and r.verified]),
            "registry_declared_intervals_count": len([r for r in self.crop_intervals if r.registry_recognized and not r.confirmed]),
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
    """Construct verified DomainIdentityContract + bitemporal DomainChronology without silent privilege elevation."""
    p_doc = dict(plot_doc or {})
    f_doc = dict(farm_doc or {})

    # WM1-P1-01: Resolve tenant verification strictly from DB Plot/Farm ownership (Farm.userId matches Prisma/Mongo)
    db_tenant = str(p_doc.get("tenantId") or f_doc.get("tenantId") or "").strip() or None
    farm_user_id = str(f_doc.get("userId") or "").strip() or None
    plot_farm_ref = str(p_doc.get("farmId") or "").strip()
    farm_doc_id = str(f_doc.get("_id") or f_doc.get("id") or "").strip()
    farm_matches_plot = (not plot_farm_ref) or (not farm_doc_id) or (plot_farm_ref == farm_doc_id)

    if db_tenant and db_tenant.lower() not in FALLBACK_TENANT_TOKENS:
        tenant_id = db_tenant
        tenant_verified = True
        is_isolated_dev_fixture = False
        tenant_source = "plot_or_farm_doc_tenant_id"
    elif farm_user_id and farm_matches_plot and farm_user_id.lower() not in FALLBACK_TENANT_TOKENS:
        tenant_id = farm_user_id
        tenant_verified = True
        is_isolated_dev_fixture = False
        tenant_source = "farm_doc_user_id"
    elif explicit_tenant_id and str(explicit_tenant_id).strip().lower() not in FALLBACK_TENANT_TOKENS:
        tenant_id = str(explicit_tenant_id).strip()
        # Isolated/explicit partition string without DB ownership proof is neither dev fixture nor verified!
        tenant_verified = False
        is_isolated_dev_fixture = False
        tenant_source = "explicit_pilot_partition_db_tenant_missing"
    else:
        tenant_id = "default_tenant"
        tenant_verified = False
        is_isolated_dev_fixture = True
        tenant_source = "fallback_default_tenant"

    farm_id = plot_farm_ref or farm_doc_id or None
    plot_name = str(p_doc.get("name") or "").strip() or None

    intervals: List[CropIntervalRecord] = []
    for idx, cc in enumerate(crop_cycles or []):
        if not isinstance(cc, Mapping):
            continue
        code, arch = _resolve_verified_crop_from_fields(
            cc.get("cropCode"), cc.get("cropType"), cc.get("crop"), cc.get("variety")
        )
        authority, is_confirmed, conf_source = _resolve_cycle_authority(cc, code)
        valid_from_dt = _parse_iso_utc(cc.get("plantDate") or cc.get("startDate") or cc.get("createdAt"))
        valid_to_dt = _parse_iso_utc(cc.get("harvestDate") or cc.get("actualHarvest") or cc.get("expectedHarvest") or cc.get("endDate"))
        declared_at_dt = _parse_iso_utc(cc.get("declaredCropAt") or cc.get("confirmedAt"))
        base_created_dt = _parse_iso_utc(cc.get("createdAt") or cc.get("updatedAt") or valid_from_dt)
        known_from_dt = max(declared_at_dt, base_created_dt) if (declared_at_dt and base_created_dt) else (declared_at_dt or base_created_dt)
        intervals.append(CropIntervalRecord(
            record_id=str(cc.get("_id") or cc.get("id") or f"cc_{idx:03d}"),
            crop_code=code,
            variety=(str(cc.get("variety")) if cc.get("variety") is not None else None),
            status=str(cc.get("status") or cc.get("stage") or "UNKNOWN").upper(),
            valid_from=_iso_or_none(valid_from_dt),
            valid_to=_iso_or_none(valid_to_dt),
            known_from=_iso_or_none(known_from_dt),
            source="crop_cycle" if cc.get("cropCode") or cc.get("cropType") else "crop_cycle_variety",
            verified=bool(is_confirmed and code != "unknown"),
            synthetic_rejected=False,
            architecture_class=arch,
            estimated_yield=(float(cc["estimatedYield"]) if isinstance(cc.get("estimatedYield"), (int, float)) else None),
            notes=(str(cc.get("notes")) if cc.get("notes") is not None else None),
            authority=authority,
            confirmed=bool(is_confirmed and code != "unknown"),
            registry_recognized=(code != "unknown"),
            declared_at=_iso_or_none(declared_at_dt),
            confirmation_source=conf_source,
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
                authority="SYNTHETIC_REJECTED",
                confirmed=False,
                registry_recognized=False,
                declared_at=None,
                confirmation_source="synthetic_rejected",
            ))
            continue
        code, arch = _resolve_verified_crop_from_fields(lbl.get("cropCode"), lbl.get("cropGroup"))
        if code != "unknown":
            authority, is_confirmed, conf_source = _resolve_confirmed_label_authority(lbl)
            declared_at_dt = _parse_iso_utc(lbl.get("declaredAt") or lbl.get("confirmedAt") or lbl.get("createdAt"))
            valid_from_dt = _parse_iso_utc(
                lbl.get("plantingDate")
                or lbl.get("validFrom")
                or lbl.get("plantDate")
                or lbl.get("startDate")
                or lbl.get("createdAt")
            )
            valid_to_dt = _parse_iso_utc(
                lbl.get("harvestDate")
                or lbl.get("validTo")
                or lbl.get("expectedHarvest")
                or lbl.get("endDate")
            )
            rec = CropIntervalRecord(
                record_id=str(lbl.get("labelId") or lbl.get("_id") or f"ccl_{idx:03d}"),
                crop_code=code,
                variety=None,
                status="CONFIRMED_LABEL" if is_confirmed else "DECLARED_LABEL",
                valid_from=_iso_or_none(valid_from_dt),
                valid_to=_iso_or_none(valid_to_dt),
                known_from=_iso_or_none(declared_at_dt or valid_from_dt),
                source="confirmed_crop_label_non_synthetic",
                verified=is_confirmed,
                synthetic_rejected=False,
                architecture_class=arch,
                notes=(str(lbl.get("notes")) if lbl.get("notes") else None),
                authority=authority,
                confirmed=is_confirmed,
                registry_recognized=True,
                declared_at=_iso_or_none(declared_at_dt),
                confirmation_source=conf_source,
            )
            verified_ccl.append(rec)

    # WM1-P2-10: Merge ALL verified/declared crop labels unconditionally regardless of existing CropCycles
    intervals.extend(verified_ccl)

    confirmed_records = [rec for rec in intervals if rec.confirmed and rec.verified and not rec.synthetic_rejected]
    declared_records = [rec for rec in intervals if rec.registry_recognized and not rec.synthetic_rejected]
    if confirmed_records:
        latest = sorted(confirmed_records, key=_interval_rank, reverse=True)[0]
        resolved_crop_code = latest.crop_code
        crop_variety = latest.variety
        crop_arch = latest.architecture_class
        crop_verified = True
        crop_registry_recognized = True
        crop_authority = latest.authority
        crop_declared_at = latest.declared_at
        crop_declared_source = latest.confirmation_source
        crop_source = latest.source
    elif declared_records:
        latest_decl = sorted(declared_records, key=_interval_rank, reverse=True)[0]
        resolved_crop_code = latest_decl.crop_code
        crop_variety = latest_decl.variety
        crop_arch = latest_decl.architecture_class
        crop_verified = False
        crop_registry_recognized = True
        crop_authority = latest_decl.authority
        crop_declared_at = latest_decl.declared_at
        crop_declared_source = latest_decl.confirmation_source
        crop_source = f"{latest_decl.source}_unconfirmed_registry_only"
    else:
        resolved_crop_code = "unknown"
        crop_variety = None
        crop_arch = None
        crop_verified = False
        crop_registry_recognized = False
        crop_authority = "UNKNOWN"
        crop_declared_at = None
        crop_declared_source = "unknown"
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

    # WM1-P1-01 & WM1-P1-02: Enforce booleans directly in block reasons
    block_reasons: List[str] = []
    if not crop_verified:
        block_reasons.append("unverified_crop_identity")
        if crop_registry_recognized:
            block_reasons.append("unconfirmed_crop_declaration")
    if synthetic_rejected and not crop_verified:
        block_reasons.append("synthetic_crop_label_rejected")
    if not tenant_verified:
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
        crop_declaration_authority=crop_authority,
        crop_registry_recognized=crop_registry_recognized,
        crop_declared_at=crop_declared_at,
        crop_declared_source=crop_declared_source,
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
    "resolve_soil_key",
]
