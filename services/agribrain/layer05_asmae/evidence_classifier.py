from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, date, timezone
import os
import hashlib
import hmac

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@dataclass(frozen=True)
class TrustedEvidenceTrustRoot:
    """Independently provisioned evidence trust root."""
    root_id: str
    verifier_key: Any  # Ed25519PublicKey or bytes (for explicitly registered HMAC)
    source: str = ""    # e.g., "sentinel2", "sentinel1", "drone"
    purpose: str = "kalman_state_observation"


# Verifier-only: starts strictly EMPTY by default.
# Never contains hardcoded production signing secrets or embedded trust keys (IR04-X01).
_TRUSTED_PROOF_VERIFIERS: Dict[str, TrustedEvidenceTrustRoot] = {}


def register_evidence_trust_root(
    root_id: str,
    verifier_key: Any,
    source: str = "",
    purpose: str = "kalman_state_observation",
) -> None:
    """Register an independently provisioned verification key or public key in the trust store.
    
    Starts strictly empty in production. Fails closed if unconfigured.
    """
    if not isinstance(root_id, str) or not root_id.strip():
        raise ValueError("invalid root_id: must be non-empty string")
    clean_id = root_id.strip()

    if isinstance(verifier_key, Ed25519PublicKey):
        vk = verifier_key
    elif isinstance(verifier_key, bytes):
        if len(verifier_key) == 32:
            try:
                vk = Ed25519PublicKey.from_public_bytes(verifier_key)
            except Exception:
                vk = verifier_key
        else:
            vk = verifier_key
    elif isinstance(verifier_key, str):
        clean_k = verifier_key.strip()
        if clean_k.startswith("ed25519:"):
            clean_k = clean_k[len("ed25519:"):]
            vk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(clean_k))
        else:
            vk = clean_k.encode("utf-8")
    else:
        raise TypeError(f"unsupported verifier_key type: {type(verifier_key).__name__}")

    _TRUSTED_PROOF_VERIFIERS[clean_id] = TrustedEvidenceTrustRoot(
        root_id=clean_id,
        verifier_key=vk,
        source=str(source).lower().strip(),
        purpose=str(purpose).strip(),
    )


def clear_evidence_trust_roots() -> None:
    """Clear all registered evidence trust roots (restores fail-closed state)."""
    _TRUSTED_PROOF_VERIFIERS.clear()


def get_trusted_evidence_roots() -> Dict[str, TrustedEvidenceTrustRoot]:
    """Return copy of currently registered evidence trust roots."""
    return dict(_TRUSTED_PROOF_VERIFIERS)


def _is_valid_proof(s: Any) -> bool:
    """Cryptographically verify evidence authenticity. Fails closed on unconfigured or forged roots (IR04-X01)."""
    # 1. Check for modern positive admission receipt first
    adm_receipt = _attr(s, "admission_receipt", None)
    if not adm_receipt:
        bp_maybe = _attr(s, "binding_proof", None)
        if isinstance(bp_maybe, dict):
            adm_receipt = bp_maybe.get("admission_receipt")
    if adm_receipt:
        try:
            from .resolution.observation_footprint_adapter import verify_scene_admission_receipt
            valid, _ = verify_scene_admission_receipt(
                adm_receipt,
                scene=s,
                tenant_id=str(_attr(s, "tenant_id", "") or ""),
                farm_id=str(_attr(s, "farm_id", "") or ""),
                plot_id=str(_attr(s, "plot_id", "") or ""),
                geometry_sha256=str(_attr(s, "geometry_hash", "") or ""),
                operator_sha256=str(_attr(s, "operator_sha256", "") or ""),
                calibrated_operator_sha256=_attr(s, "calibrated_operator_sha256", None),
                valid_time=str(_attr(s, "acquisition_time", "") or ""),
                committed_at=str(_attr(s, "committed_at", "") or ""),
            )
            if valid:
                return True
        except Exception:
            pass

    # 2. Legacy proof verification
    bp = _attr(s, "binding_proof", None) or {}
    meta = _attr(s, "metadata", None) or {}
    hp = (
        _attr(s, "holdout_proof", None)
        or _attr(bp, "holdout_proof", None)
        or _attr(meta, "holdout_proof", None)
    )
    rp = (
        _attr(s, "registration_proof", None)
        or _attr(bp, "registration_proof", None)
        or _attr(meta, "registration_proof", None)
    )
    fa_raw = _attr(s, "field_approval", None)
    if fa_raw is None:
        fa_raw = _attr(bp, "field_approval", None)
    if fa_raw is None:
        fa_raw = _attr(meta, "field_approval", False)
    if isinstance(fa_raw, dict):
        fa = fa_raw.get("approved") is True
    else:
        fa = bool(fa_raw)
    if not (isinstance(hp, dict) and isinstance(rp, dict) and fa):
        return False
    trust_root = str(_attr(hp, "trust_root_id", None) or _attr(s, "trust_root_id", None) or "").strip()
    sig = str(_attr(hp, "signature", None) or _attr(s, "signature", None) or "").strip()
    geom_hash = str(_attr(hp, "geometry_hash", None) or _attr(rp, "geometry_hash", None) or "").strip()
    valid_until = _attr(hp, "valid_until", None) or _attr(hp, "expires_at", None)
    if not trust_root or trust_root in ("revoked", "unverified", "none", "invalid"):
        return False
    if not sig or sig in ("invalid", "unverified", "revoked", "none"):
        return False

    # Strict expiry check: valid_until is mandatory and must not be expired
    if not valid_until:
        return False
    try:
        if isinstance(valid_until, str):
            exp_dt = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
        elif isinstance(valid_until, (datetime, date)):
            exp_dt = valid_until if isinstance(valid_until, datetime) else datetime(valid_until.year, valid_until.month, valid_until.day, tzinfo=timezone.utc)
        else:
            return False
        now_dt = datetime.now(timezone.utc) if exp_dt.tzinfo is not None else datetime.now()
        if exp_dt <= now_dt:
            return False
    except Exception:
        return False

    # Strict geometry binding: geometry_hash must match target scene geometry
    target_geom = str(_attr(s, "geometry_hash", "") or _attr(_attr(s, "runtime", None), "geometry_hash", "") or "").strip()
    if not geom_hash:
        return False
    if target_geom and geom_hash != target_geom:
        return False

    # FAIL-CLOSED: Check enrolled trust roots in memory registry
    if not _TRUSTED_PROOF_VERIFIERS:
        return False
    if trust_root not in _TRUSTED_PROOF_VERIFIERS:
        return False

    trusted = _TRUSTED_PROOF_VERIFIERS[trust_root]

    # Check sensor scope / cross-sensor rejection
    if trusted.source:
        s_sensor = str(_attr(s, "sensor", "") or _attr(_attr(s, "runtime", None), "sensor", "") or "").strip().lower()
        if trusted.source in ("sentinel2", "s2"):
            if s_sensor not in ("sentinel2", "s2"):
                return False
        elif trusted.source in ("sentinel1", "s1"):
            if s_sensor not in ("sentinel1", "s1"):
                return False
        elif trusted.source != s_sensor:
            return False

    # Verify signature
    valid_until_str = valid_until if isinstance(valid_until, str) else exp_dt.isoformat()
    payload = f"{trust_root}:{geom_hash or target_geom}:{valid_until_str}".encode("utf-8")

    if isinstance(trusted.verifier_key, Ed25519PublicKey):
        clean_sig = sig
        if clean_sig.startswith("ed25519:"):
            clean_sig = clean_sig[len("ed25519:"):]
        try:
            sig_bytes = bytes.fromhex(clean_sig)
            trusted.verifier_key.verify(sig_bytes, payload)
            return True
        except Exception:
            return False
    elif isinstance(trusted.verifier_key, (bytes, bytearray)):
        expected_sig = hmac.new(trusted.verifier_key, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig.lower(), expected_sig.lower())

    return False


@dataclass
class ASMAEEvidenceClassification:
    state: str  # "full_scene_stack" | "archive_backed_asmae" | "composite_assimilated_asmae" | "plot_level_observation_evidence" | "unavailable"
    real_asmae_evidence: bool
    current_1m_approval_allowed: bool
    visual_fusion_allowed: bool
    archive_context_allowed: bool
    experimental_visual_allowed: bool
    source_reality: str
    real_scene_count: int
    s2_real_scene_count: int
    s1_real_scene_count: int
    missing_bands: List[str]
    reason: str
    allowed_outputs: List[str]
    blocked_outputs: List[str]
    test_override: bool
    real_provider_product: bool
    production_usable: bool
    diagnostic_only: bool
    asmae_advisory_evidence: bool = False
    composite_fusion_allowed: bool = False
    authority: str = "none"
    visualization_allowed: bool = True
    composite_advisory_allowed: bool = False
    scientific_surface_allowed: bool = False
    prescription_driver_allowed: bool = False
    state_update_allowed: bool = False


def classify_asmae_evidence(
    scenes: list,
    archive_metrics_status: Optional[str],
    archive_metrics_hash: Optional[str],
    archive_baselines: dict,
    retrovalidation_residuals: dict,
    archive_bma: dict,
    raster_composites: dict,
    layer0_source_packages: dict,
    is_pseudo: bool = False,
    telemetry: Optional[dict] = None,
) -> ASMAEEvidenceClassification:
    """
    Classifies the ASMAE evidence state into one of five tiers:
      1. full_scene_stack: Real Sentinel acquisition loadable (S2: B04+B08, S1: VV or VH, transform/crs/timestamp present)
      2. archive_backed_asmae: Archive backing metadata present (EnKF, BMA, retro, baselines available) but no current scenes
      3. composite_assimilated_asmae: Experimental NDVI/NDMI/SAR composite grids only
      4. plot_level_observation_evidence: Local sensors/weather packets only
      5. unavailable: No data at all
    """
    test_override = os.environ.get("ASMAE_TEST_OVERRIDE", "false").lower() == "true"
    
    # Count real Sentinel scenes that are validly loaded
    s2_real_count = 0
    s1_real_count = 0
    missing_bands = []
    
    # Track test override and provider detail flags across valid scenes
    has_test_override = False
    has_real_provider_product = False
    has_production_usable = False
    has_diagnostic_only = False
    
    for s_item in scenes:
        if isinstance(s_item, dict):
            s = s_item.get("runtime") or s_item
            reality = s_item.get("source_reality") or getattr(s, "source_reality", "unknown")
            is_test = s_item.get("test_override", getattr(s, "test_override", False))
            is_prod_usable = bool(s_item.get("production_usable", getattr(s, "production_usable", False)))
            is_real_prov = bool(s_item.get("real_provider_product", getattr(s, "real_provider_product", False)))
            is_diag_only = bool(s_item.get("diagnostic_only", getattr(s, "diagnostic_only", False)))
        else:
            s = s_item
            reality = getattr(s, "source_reality", "unknown")
            is_test = getattr(s, "test_override", False)
            is_prod_usable = bool(getattr(s, "production_usable", False))
            is_real_prov = bool(getattr(s, "real_provider_product", False))
            is_diag_only = bool(getattr(s, "diagnostic_only", False))
            
        if not s:
            continue
            
        sensor = _attr(s, "sensor", "")
        if reality != "real_raster":
            continue
            
        if is_test and not test_override:
            continue
            
        # Verify basic geometry and timestamp presence
        w = _attr(s, "width", 0) or 0
        h = _attr(s, "height", 0) or 0
        crs = _attr(s, "crs", "") or ""
        transform = _attr(s, "transform", None)
        acq_time = _attr(s, "acquisition_time", _attr(s, "acquisition_datetime", None))
        
        has_geom = w > 0 and h > 0 and crs and transform and len(transform) == 6 and acq_time is not None
        if not has_geom:
            continue
            
        # Quality score >= 0.60
        qa_score = _attr(s, "qa_score", 0.0)
        if qa_score < 0.60:
            continue
            
        bands = _attr(s, "bands", {}) or {}
        # S2: B04 + B08 loaded
        if sensor == "S2":
            if "B04" in bands and "B08" in bands:
                s2_real_count += 1
                if is_test:
                    has_test_override = True
                if getattr(s, "real_provider_product", False):
                    has_real_provider_product = True
                if is_prod_usable:
                    has_production_usable = True
                if getattr(s, "diagnostic_only", False):
                    has_diagnostic_only = True
            else:
                if "B04" not in bands:
                    missing_bands.append("B04")
                if "B08" not in bands:
                    missing_bands.append("B08")
        # S1: VV or VH loaded
        elif sensor == "S1":
            has_vv = "VV" in bands or "vv" in bands
            has_vh = "VH" in bands or "vh" in bands
            if has_vv or has_vh:
                s1_real_count += 1
                if is_test:
                    has_test_override = True
                if getattr(s, "real_provider_product", False):
                    has_real_provider_product = True
                if is_prod_usable:
                    has_production_usable = True
                if getattr(s, "diagnostic_only", False):
                    has_diagnostic_only = True
            else:
                missing_bands.extend(["VV", "VH"])
 
    # Determine stack mode
    if s2_real_count >= 3 and s1_real_count >= 2:
        stack_mode = "sar_assisted"
    elif s2_real_count >= 3:
        stack_mode = "optical"
    elif s1_real_count >= 2:
        stack_mode = "sar_only"
    else:
        stack_mode = "degraded"
        
    is_stack_valid = (stack_mode in ("optical", "sar_assisted", "sar_only"))
 
    # Check archive status & metadata completeness
    archive_ok = (
        archive_metrics_status in ("available", "success") and
        archive_metrics_hash is not None and
        isinstance(archive_baselines, dict) and len(archive_baselines) > 0 and
        isinstance(retrovalidation_residuals, dict) and len(retrovalidation_residuals) > 0 and
        isinstance(archive_bma, dict) and len(archive_bma) > 0
    )
 
    # Check raster composites
    has_raster_composites = False
    if raster_composites:
        valid_keys = [k for k in ["NDVI", "NDVI_CLEAN", "SAR", "ndmi"] if k in raster_composites]
        for k in valid_keys:
            comp = raster_composites[k]
            if isinstance(comp, dict):
                grid = comp.get("values") or comp.get("pixel_array")
                if grid and isinstance(grid, list) and len(grid) > 0 and isinstance(grid[0], list):
                    has_raster_composites = True
                    break
 
    # Check plot-level observations
    has_plot_observations = False
    if layer0_source_packages:
        for key in ["sentinel2", "sentinel1", "sensor", "environment"]:
            pkgs = layer0_source_packages.get(key) or layer0_source_packages.get(f"{key}_packages") or []
            if pkgs:
                if not isinstance(pkgs, list):
                    pkgs = [pkgs]
                for p in pkgs:
                    packets = getattr(p, "packets", []) or []
                    if packets:
                        has_plot_observations = True
                        break
                if has_plot_observations:
                    break
 
    # Get telemetry reasons
    s2_reason = None
    s1_reason = None
    if telemetry:
        s2_reason = telemetry.get("s2", {}).get("reason")
        s1_reason = telemetry.get("s1", {}).get("reason")
    if not s2_reason and isinstance(layer0_source_packages, dict):
        s2_reason = layer0_source_packages.get("s2_telemetry_reason")
    if not s1_reason and isinstance(layer0_source_packages, dict):
        s1_reason = layer0_source_packages.get("s1_telemetry_reason")
    telemetry_reason = s2_reason or s1_reason or None
 
    # Resolve State
    if (s2_real_count >= 1 or s1_real_count >= 1) and not is_pseudo:
        if has_production_usable and not has_test_override and is_stack_valid:
            state = "full_scene_stack"
        else:
            state = "diagnostic_scene_stack"
    elif is_stack_valid and not is_pseudo:
        state = "full_scene_stack"
    elif archive_ok and not is_pseudo:
        state = "archive_backed_asmae"
    elif has_raster_composites:
        state = "composite_assimilated_asmae"
    elif has_plot_observations:
        state = "plot_level_observation_evidence"
    else:
        state = "unavailable"
 
    # Set authority flags and output access
    asmae_advisory_evidence = False
    composite_fusion_allowed = False
    authority = "none"

    has_certification_proof = any(_is_valid_proof(s) for s in scenes)

    if state == "full_scene_stack":
        real_asmae_evidence = True
        current_1m_approval_allowed = False  # 1m spatial certification strictly ON HOLD (IR08-665-04)
        visual_fusion_allowed = True
        archive_context_allowed = True
        experimental_visual_allowed = True
        source_reality = "real_raster"
        allowed_outputs = ["ASMAE_VISUAL_FUSION_CANOPY", "canopy_water", "vigor"]
        blocked_outputs = ["ASMAE_1M_ADVISORY_MASK"]  # 1m advisory mask strictly blocked
        if has_certification_proof:
            authority = "authenticated_observation_stack"
            reason = "ok"
        else:
            authority = "advisory_only"
            reason = "1m_approval_unavailable_certification_proof_missing"
    elif state == "diagnostic_scene_stack":
        real_asmae_evidence = True
        current_1m_approval_allowed = False
        visual_fusion_allowed = True
        archive_context_allowed = True
        experimental_visual_allowed = True
        source_reality = "real_raster"
        allowed_outputs = ["canopy_water", "vigor", "NDVI_CLEAN"]
        blocked_outputs = ["ASMAE_1M_ADVISORY_MASK"]
        reason = "diagnostic_spatial_assimilation"
        authority = "diagnostic_spatial_assimilation"
    elif state == "archive_backed_asmae":
        real_asmae_evidence = True
        current_1m_approval_allowed = False
        visual_fusion_allowed = False
        archive_context_allowed = True
        experimental_visual_allowed = True
        source_reality = "archive"
        allowed_outputs = ["canopy_water", "vigor"]
        blocked_outputs = ["ASMAE_VISUAL_FUSION_CANOPY", "ASMAE_1M_ADVISORY_MASK"]
        reason = telemetry_reason or "archive_backed_only_blocks_current_1m"
        authority = "asmae_archive_advisory"
    elif state == "composite_assimilated_asmae":
        real_asmae_evidence = False
        asmae_advisory_evidence = True
        current_1m_approval_allowed = False
        visual_fusion_allowed = False
        composite_fusion_allowed = True
        archive_context_allowed = False
        experimental_visual_allowed = True
        source_reality = "composite"
        authority = "composite_advisory"
        allowed_outputs = [
            "COMPOSITE_ADVISORY_CANOPY",
            "COMPOSITE_VEG_ATTENTION",
            "COMPOSITE_WATER_SUPPORT",
            "COMPOSITE_NUTRIENT_SUPPORT",
            "COMPOSITE_SALINITY_STRESS",
            "COMPOSITE_RISK_DIAGNOSTIC",
            "COMPOSITE_CONFIDENCE",
            "COMPOSITE_EFFECTIVE_RESOLUTION",
            "COMPOSITE_UNCERTAINTY",
            "COMPOSITE_BMA_DISAGREEMENT",
            "COMPOSITE_ARCHIVE_SUPPORT",
            "COMPOSITE_RETRO_SCORE",
            "COMPOSITE_ML_SUPPORT",
            "COMPOSITE_TEXTURE_DETAIL",
            "EXPERIMENTAL_TEXTURE_SUPPORT_MASK"
        ]
        blocked_outputs = ["ASMAE_VISUAL_FUSION_CANOPY", "ASMAE_1M_ADVISORY_MASK"]
        reason = telemetry_reason or "composite_only"
    elif state == "plot_level_observation_evidence":
        real_asmae_evidence = False
        current_1m_approval_allowed = False
        visual_fusion_allowed = False
        archive_context_allowed = False
        experimental_visual_allowed = False
        source_reality = "plot_level_observation_evidence"
        allowed_outputs = ["NDVI_CLEAN", "FALLBACK_CANOPY_PROXY"]
        blocked_outputs = ["ASMAE_VISUAL_FUSION_CANOPY", "ASMAE_1M_ADVISORY_MASK"]
        reason = telemetry_reason or "plot_level_observation_only"
    else:
        real_asmae_evidence = False
        current_1m_approval_allowed = False
        visual_fusion_allowed = False
        archive_context_allowed = False
        experimental_visual_allowed = False
        source_reality = "unknown"
        allowed_outputs = ["NDVI_CLEAN"]
        blocked_outputs = ["ASMAE_VISUAL_FUSION_CANOPY", "ASMAE_1M_ADVISORY_MASK"]
        reason = telemetry_reason or "no_scene_and_no_composite_evidence"
 
    res_test_override = False
    res_real_provider_product = False
    res_production_usable = False
    res_diagnostic_only = True
    
    state_update_allowed = False
    visualization_allowed = True
    composite_advisory_allowed = False
    scientific_surface_allowed = False
    prescription_driver_allowed = False
    current_1m_approval_allowed_val = False

    if state == "full_scene_stack":
        res_test_override = has_test_override
        res_real_provider_product = has_real_provider_product
        if has_test_override:
            res_production_usable = False
            res_diagnostic_only = True
            res_real_provider_product = False
            
            state_update_allowed = False
            visualization_allowed = True
            composite_advisory_allowed = True
            scientific_surface_allowed = False
            prescription_driver_allowed = False
            current_1m_approval_allowed_val = False
        else:
            res_production_usable = has_certification_proof
            res_diagnostic_only = not has_certification_proof
            res_real_provider_product = True
            
            state_update_allowed = has_certification_proof
            visualization_allowed = True
            composite_advisory_allowed = True
            scientific_surface_allowed = has_certification_proof
            prescription_driver_allowed = has_certification_proof
            current_1m_approval_allowed_val = False  # 1m spatial certification strictly ON HOLD (IR08-665-04)
            if not has_certification_proof:
                authority = "advisory_only"
                reason = "1m_approval_unavailable_certification_proof_missing"
            else:
                authority = "authenticated_observation_stack"
                reason = "ok"
    elif state == "diagnostic_scene_stack":
        res_test_override = has_test_override
        res_real_provider_product = has_real_provider_product
        res_production_usable = False
        res_diagnostic_only = True
        state_update_allowed = False
        visualization_allowed = True
        composite_advisory_allowed = True
        scientific_surface_allowed = False
        prescription_driver_allowed = False
        current_1m_approval_allowed_val = False
    elif state == "archive_backed_asmae":
        res_real_provider_product = has_real_provider_product
        res_production_usable = False
        res_diagnostic_only = True
        state_update_allowed = False
        visualization_allowed = True
        composite_advisory_allowed = True
        scientific_surface_allowed = False
        prescription_driver_allowed = False
        current_1m_approval_allowed_val = False
    elif state == "composite_assimilated_asmae":
        res_real_provider_product = False
        res_production_usable = False
        res_diagnostic_only = True
        state_update_allowed = False
        visualization_allowed = True
        composite_advisory_allowed = True
        scientific_surface_allowed = False
        prescription_driver_allowed = False
        current_1m_approval_allowed_val = False
    else:
        res_real_provider_product = False
        res_production_usable = False
        res_diagnostic_only = True
        state_update_allowed = False
        visualization_allowed = True
        composite_advisory_allowed = False
        scientific_surface_allowed = False
        prescription_driver_allowed = False
        current_1m_approval_allowed_val = False

    return ASMAEEvidenceClassification(
        state=state,
        real_asmae_evidence=real_asmae_evidence,
        current_1m_approval_allowed=current_1m_approval_allowed_val,
        visual_fusion_allowed=visual_fusion_allowed,
        archive_context_allowed=archive_context_allowed,
        experimental_visual_allowed=experimental_visual_allowed,
        source_reality=source_reality,
        real_scene_count=s2_real_count + s1_real_count,
        s2_real_scene_count=s2_real_count,
        s1_real_scene_count=s1_real_count,
        missing_bands=missing_bands,
        reason=reason,
        allowed_outputs=allowed_outputs,
        blocked_outputs=blocked_outputs,
        test_override=res_test_override,
        real_provider_product=res_real_provider_product,
        production_usable=res_production_usable,
        diagnostic_only=res_diagnostic_only,
        asmae_advisory_evidence=asmae_advisory_evidence,
        composite_fusion_allowed=composite_fusion_allowed,
        authority=authority,
        visualization_allowed=visualization_allowed,
        composite_advisory_allowed=composite_advisory_allowed,
        scientific_surface_allowed=scientific_surface_allowed,
        prescription_driver_allowed=prescription_driver_allowed,
        state_update_allowed=state_update_allowed
    )
