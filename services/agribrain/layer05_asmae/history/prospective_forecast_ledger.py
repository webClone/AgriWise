"""Append-only, tamper-evident V3 Prospective Forecast & Observation Scoring Ledger.

Records forecasts strictly AT issuance time (`issued_at`), locking the complete
model state, crop posterior, weather forecast, channel calibration, specialist
outputs, and immutable input-manifest hashes into a hash-chained JSONL ledger.
Realized future observations are scored only when `obs_committed_at > issued_at`
and never mutate original issuance records.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from services.agribrain.world_model.canonical_worldline import _parse_utc_iso


class ProspectiveLedgerError(ValueError):
    """Base error for causal or immutability violations in the prospective ledger."""


class ImmutableIssuanceError(ProspectiveLedgerError):
    """Raised on duplicate forecast IDs or attempts to modify stored issuances."""


class CausalIssuanceViolation(ProspectiveLedgerError):
    """Raised when knowledge cutoff or horizon violates prospective causality."""


class RetroactiveOutcomeViolation(ProspectiveLedgerError):
    """Raised when attempting to score an observation committed before forecast issuance."""


class ImmutableScoreError(ProspectiveLedgerError):
    """Raised on duplicate scoring of the same (forecast_id, channel) pair."""


class IntegrityTamperError(ProspectiveLedgerError):
    """Raised when hash-chain or SHA-256 verification fails."""


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True)


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _norm_utc_iso(value: Any, *, field_name: str) -> datetime:
    dt = _parse_utc_iso(str(value or "").strip())
    if dt is None:
        raise ProspectiveLedgerError(f"Invalid or missing UTC ISO timestamp for {field_name}: {value!r}")
    return dt.astimezone(timezone.utc)


def _finite_float_or_none(val: Any) -> Optional[float]:
    if isinstance(val, bool) or val is None:
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _gaussian_crps(y_obs: float, mu: float, sigma: float) -> float:
    sig = max(1e-4, float(sigma))
    z = (y_obs - mu) / sig
    pdf = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return sig * (z * (2.0 * cdf - 1.0) + 2.0 * pdf - 1.0 / math.sqrt(math.pi))


@dataclass(frozen=True)
class ProspectiveForecastIssuance:
    """Immutable snapshot of a single issued prospective forecast."""

    ledger_schema_version: str
    forecast_id: str
    plot_id: str
    tenant_id: str
    farm_id: Optional[str]
    geometry_hash: str
    issued_at: str
    knowledge_cutoff_time: str
    target_valid_time: str
    target_window_start: str
    target_window_end: str
    horizon_days: int
    model_version: str
    calibration_version: str
    state_schema_version: str
    input_manifest_hash: str
    observation_lineage_hash: str
    crop_chronology_hash: str
    weather_lineage_hash: str
    specialist_config_hash: str
    complete_model_state: Dict[str, Any]
    crop_posterior: Dict[str, Any]
    weather_forecast: Dict[str, Any]
    channel_calibration: Dict[str, Any]
    specialist_outputs: Dict[str, Any]
    bma_weights: Dict[str, float]
    predicted_channels: Dict[str, Any]
    prev_record_sha256: str
    record_sha256: str

    def body_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("record_sha256", None)
        return d

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProspectiveScoreReceipt:
    """Immutable companion score receipt attached once realized future observation arrives."""

    score_schema_version: str
    score_id: str
    forecast_id: str
    issuance_record_sha256: str
    plot_id: str
    tenant_id: str
    channel: str
    observed_at: str
    obs_committed_at: str
    observation_content_hash: str
    y_obs: float
    y_pred: float
    pred_sigma: float
    y_pers: Optional[float]
    error: float
    abs_error: float
    squared_error: float
    persistence_squared_error: Optional[float]
    abs_z: float
    within_1sigma: bool
    within_2sigma: bool
    crps: float
    scored_at: str
    prev_score_sha256: str
    score_sha256: str

    def body_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("score_sha256", None)
        return d

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProspectiveForecastLedger:
    """File-backed append-only hash-chained ledger separating issuance from future outcome scoring."""

    GENESIS_HASH = "0" * 64

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = Path(root_dir)

    def _scope_dir(self, *, plot_id: str, tenant_id: str) -> Path:
        safe_tenant = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(tenant_id or "default"))
        safe_plot = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(plot_id or "plot"))
        return self.root_dir / safe_tenant / safe_plot

    def _issuance_path(self, *, plot_id: str, tenant_id: str) -> Path:
        return self._scope_dir(plot_id=plot_id, tenant_id=tenant_id) / "issuances.jsonl"

    def _scores_path(self, *, plot_id: str, tenant_id: str) -> Path:
        return self._scope_dir(plot_id=plot_id, tenant_id=tenant_id) / "scores.jsonl"

    @staticmethod
    def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
        if not path.is_file():
            return []
        rows: List[Dict[str, Any]] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    @staticmethod
    def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical_json(row) + "\n")

    def verify_chain_integrity(self, *, plot_id: str, tenant_id: str) -> Dict[str, Any]:
        """Verify cryptographic hash chains over every stored issuance and score receipt."""
        iss_rows = self._read_jsonl(self._issuance_path(plot_id=plot_id, tenant_id=tenant_id))
        scr_rows = self._read_jsonl(self._scores_path(plot_id=plot_id, tenant_id=tenant_id))

        iss_by_id: Dict[str, Dict[str, Any]] = {}
        prev_iss = self.GENESIS_HASH
        for idx, row in enumerate(iss_rows):
            stored_prev = str(row.get("prev_record_sha256") or "")
            stored_sha = str(row.get("record_sha256") or "")
            if stored_prev != prev_iss:
                raise IntegrityTamperError(f"Issuance chain link mismatch at index {idx}")
            body = {k: v for k, v in row.items() if k != "record_sha256"}
            expected_sha = _sha256_payload(body)
            if stored_sha != expected_sha:
                raise IntegrityTamperError(f"Issuance content hash tampered at index {idx} ({row.get('forecast_id')})")
            prev_iss = stored_sha
            iss_by_id[str(row.get("forecast_id"))] = row

        prev_scr = self.GENESIS_HASH
        for idx, row in enumerate(scr_rows):
            stored_prev = str(row.get("prev_score_sha256") or "")
            stored_sha = str(row.get("score_sha256") or "")
            if stored_prev != prev_scr:
                raise IntegrityTamperError(f"Score chain link mismatch at index {idx}")
            fid = str(row.get("forecast_id") or "")
            iss = iss_by_id.get(fid)
            if iss is None or str(row.get("issuance_record_sha256") or "") != str(iss.get("record_sha256") or ""):
                raise IntegrityTamperError(f"Score references missing or mismatched issuance {fid}")
            body = {k: v for k, v in row.items() if k != "score_sha256"}
            expected_sha = _sha256_payload(body)
            if stored_sha != expected_sha:
                raise IntegrityTamperError(f"Score content hash tampered at index {idx} ({row.get('score_id')})")
            prev_scr = stored_sha

        return {
            "chain_valid": True,
            "issuance_count": len(iss_rows),
            "score_count": len(scr_rows),
            "issuance_head_sha256": prev_iss if iss_rows else None,
            "score_head_sha256": prev_scr if scr_rows else None,
        }

    def record_forecast_issuance(
        self,
        *,
        forecast_id: str,
        plot_id: str,
        tenant_id: str,
        farm_id: Optional[str],
        geometry_hash: str,
        issued_at: str,
        knowledge_cutoff_time: str,
        target_valid_time: str,
        target_window_start: Optional[str] = None,
        target_window_end: Optional[str] = None,
        horizon_days: int,
        model_version: str,
        calibration_version: str,
        state_schema_version: str,
        input_manifest_hash: str,
        observation_lineage_hash: str,
        crop_chronology_hash: str,
        weather_lineage_hash: str,
        specialist_config_hash: str,
        complete_model_state: Mapping[str, Any],
        crop_posterior: Mapping[str, Any],
        weather_forecast: Mapping[str, Any],
        channel_calibration: Mapping[str, Any],
        specialist_outputs: Mapping[str, Any],
        bma_weights: Mapping[str, Any],
        predicted_channels: Mapping[str, Any],
    ) -> ProspectiveForecastIssuance:
        """Append an immutable forward forecast issuance; rejects retroactive targets or duplicates."""
        fid = str(forecast_id or "").strip()
        if not fid:
            raise ProspectiveLedgerError("forecast_id is required")
        if not str(input_manifest_hash or "").strip():
            raise ProspectiveLedgerError("input_manifest_hash is required")

        issued_dt = _norm_utc_iso(issued_at, field_name="issued_at")
        k_dt = _norm_utc_iso(knowledge_cutoff_time, field_name="knowledge_cutoff_time")
        target_dt = _norm_utc_iso(target_valid_time, field_name="target_valid_time")
        win_start_dt = _norm_utc_iso(target_window_start or target_valid_time, field_name="target_window_start")
        win_end_dt = _norm_utc_iso(target_window_end or target_valid_time, field_name="target_window_end")

        if k_dt > issued_dt:
            raise CausalIssuanceViolation("knowledge_cutoff_time cannot exceed issued_at")
        if int(horizon_days) < 1:
            raise CausalIssuanceViolation("horizon_days must be >= 1 for a prospective forecast")
        if target_dt <= issued_dt or win_start_dt <= issued_dt:
            raise CausalIssuanceViolation("Prospective target window must lie strictly after issued_at")
        if win_end_dt < win_start_dt:
            raise CausalIssuanceViolation("target_window_end cannot precede target_window_start")

        chain_state = self.verify_chain_integrity(plot_id=plot_id, tenant_id=tenant_id)
        existing = self._read_jsonl(self._issuance_path(plot_id=plot_id, tenant_id=tenant_id))
        if any(str(r.get("forecast_id")) == fid for r in existing):
            raise ImmutableIssuanceError(f"duplicate_forecast_id_immutable:{fid}")

        prev_sha = chain_state["issuance_head_sha256"] or self.GENESIS_HASH
        body = {
            "ledger_schema_version": "asmae_prospective_issuance_v1",
            "forecast_id": fid,
            "plot_id": str(plot_id),
            "tenant_id": str(tenant_id),
            "farm_id": str(farm_id) if farm_id else None,
            "geometry_hash": str(geometry_hash or ""),
            "issued_at": issued_dt.isoformat(),
            "knowledge_cutoff_time": k_dt.isoformat(),
            "target_valid_time": target_dt.isoformat(),
            "target_window_start": win_start_dt.isoformat(),
            "target_window_end": win_end_dt.isoformat(),
            "horizon_days": int(horizon_days),
            "model_version": str(model_version),
            "calibration_version": str(calibration_version),
            "state_schema_version": str(state_schema_version),
            "input_manifest_hash": str(input_manifest_hash),
            "observation_lineage_hash": str(observation_lineage_hash),
            "crop_chronology_hash": str(crop_chronology_hash),
            "weather_lineage_hash": str(weather_lineage_hash),
            "specialist_config_hash": str(specialist_config_hash),
            "complete_model_state": dict(complete_model_state),
            "crop_posterior": dict(crop_posterior),
            "weather_forecast": dict(weather_forecast),
            "channel_calibration": dict(channel_calibration),
            "specialist_outputs": dict(specialist_outputs),
            "bma_weights": {str(k): float(v) for k, v in bma_weights.items() if _finite_float_or_none(v) is not None},
            "predicted_channels": dict(predicted_channels),
            "prev_record_sha256": prev_sha,
        }
        rec_sha = _sha256_payload(body)
        issuance = ProspectiveForecastIssuance(**body, record_sha256=rec_sha)
        self._append_jsonl(self._issuance_path(plot_id=plot_id, tenant_id=tenant_id), issuance.to_dict())
        return issuance

    def attach_realized_observation(
        self,
        *,
        forecast_id: str,
        plot_id: str,
        tenant_id: str,
        channel: str,
        observed_at: str,
        obs_committed_at: str,
        observation_content_hash: str,
        y_obs: float,
        prediction_source: str = "calibrated",
        scored_at: Optional[str] = None,
    ) -> ProspectiveScoreReceipt:
        """Attach a post-issuance realized observation as an immutable companion score receipt."""
        chain_state = self.verify_chain_integrity(plot_id=plot_id, tenant_id=tenant_id)
        issuances = {
            str(r["forecast_id"]): r
            for r in self._read_jsonl(self._issuance_path(plot_id=plot_id, tenant_id=tenant_id))
        }
        iss = issuances.get(str(forecast_id))
        if iss is None:
            raise ProspectiveLedgerError(f"Unknown prospective forecast_id: {forecast_id}")

        ch_key = str(channel or "").strip()
        existing_scores = self._read_jsonl(self._scores_path(plot_id=plot_id, tenant_id=tenant_id))
        if any(str(s.get("forecast_id")) == str(forecast_id) and str(s.get("channel")) == ch_key for s in existing_scores):
            raise ImmutableScoreError(f"forecast_already_scored_immutable:{forecast_id}:{ch_key}")

        issued_dt = _norm_utc_iso(iss["issued_at"], field_name="issued_at")
        win_start_dt = _norm_utc_iso(iss["target_window_start"], field_name="target_window_start")
        win_end_dt = _norm_utc_iso(iss["target_window_end"], field_name="target_window_end")
        obs_dt = _norm_utc_iso(observed_at, field_name="observed_at")
        committed_dt = _norm_utc_iso(obs_committed_at, field_name="obs_committed_at")

        if committed_dt <= issued_dt:
            raise RetroactiveOutcomeViolation(
                f"Observation committed at {committed_dt.isoformat()} is not strictly after issuance {issued_dt.isoformat()}"
            )
        if obs_dt < win_start_dt or obs_dt > win_end_dt:
            raise CausalIssuanceViolation(
                f"Observation {obs_dt.isoformat()} falls outside target window [{win_start_dt.isoformat()}, {win_end_dt.isoformat()}]"
            )

        pred_entry = (iss.get("predicted_channels") or {}).get(ch_key)
        if not isinstance(pred_entry, Mapping):
            raise ProspectiveLedgerError(f"Issuance {forecast_id} has no forecast for channel {ch_key!r}")

        y_pred = _finite_float_or_none(
            pred_entry.get("bma_mean") if prediction_source == "bma" else pred_entry.get("mean")
        )
        sigma = _finite_float_or_none(pred_entry.get("sigma"))
        if y_pred is None or sigma is None:
            raise ProspectiveLedgerError(f"Issuance {forecast_id} channel {ch_key!r} missing finite prediction or sigma")
        y_obs_f = float(y_obs)
        if not math.isfinite(y_obs_f):
            raise ProspectiveLedgerError("y_obs must be finite")

        y_pers = _finite_float_or_none(pred_entry.get("y_pers"))
        err = y_pred - y_obs_f
        sq_err = err * err
        pers_sq_err = ((y_pers - y_obs_f) ** 2) if y_pers is not None else None
        sig_eff = max(1e-4, sigma)
        abs_z = abs(err) / sig_eff
        crps = _gaussian_crps(y_obs_f, y_pred, sig_eff)

        prev_scr = chain_state["score_head_sha256"] or self.GENESIS_HASH
        scored_iso = (_norm_utc_iso(scored_at, field_name="scored_at") if scored_at else datetime.now(timezone.utc)).isoformat()
        score_id = hashlib.sha256(f"{forecast_id}:{ch_key}:{iss['record_sha256']}".encode("utf-8")).hexdigest()[:24]
        body = {
            "score_schema_version": "asmae_prospective_score_v1",
            "score_id": f"pscore_{score_id}",
            "forecast_id": str(forecast_id),
            "issuance_record_sha256": str(iss["record_sha256"]),
            "plot_id": str(plot_id),
            "tenant_id": str(tenant_id),
            "channel": ch_key,
            "observed_at": obs_dt.isoformat(),
            "obs_committed_at": committed_dt.isoformat(),
            "observation_content_hash": str(observation_content_hash or ""),
            "y_obs": round(y_obs_f, 6),
            "y_pred": round(y_pred, 6),
            "pred_sigma": round(sig_eff, 6),
            "y_pers": round(y_pers, 6) if y_pers is not None else None,
            "error": round(err, 6),
            "abs_error": round(abs(err), 6),
            "squared_error": round(sq_err, 8),
            "persistence_squared_error": round(pers_sq_err, 8) if pers_sq_err is not None else None,
            "abs_z": round(abs_z, 6),
            "within_1sigma": bool(abs_z <= 1.0),
            "within_2sigma": bool(abs_z <= 2.0),
            "crps": round(crps, 6),
            "scored_at": scored_iso,
            "prev_score_sha256": prev_scr,
        }
        scr_sha = _sha256_payload(body)
        receipt = ProspectiveScoreReceipt(**body, score_sha256=scr_sha)
        self._append_jsonl(self._scores_path(plot_id=plot_id, tenant_id=tenant_id), receipt.to_dict())
        return receipt

    def summarize(self, *, plot_id: str, tenant_id: str) -> Dict[str, Any]:
        """Summarize pending vs scored genuinely prospective forecast issuances for one plot."""
        chain_info = self.verify_chain_integrity(plot_id=plot_id, tenant_id=tenant_id)
        issuances = self._read_jsonl(self._issuance_path(plot_id=plot_id, tenant_id=tenant_id))
        scores = self._read_jsonl(self._scores_path(plot_id=plot_id, tenant_id=tenant_id))
        scored_fids = {str(s.get("forecast_id")) for s in scores}
        pending = [r for r in issuances if str(r.get("forecast_id")) not in scored_fids]

        iss_by_id = {str(r["forecast_id"]): r for r in issuances}
        by_horizon: Dict[str, List[Dict[str, Any]]] = {}
        for s in scores:
            fid = str(s.get("forecast_id"))
            h = int((iss_by_id.get(fid) or {}).get("horizon_days") or 0)
            bucket = (
                "short_1_7d" if h <= 7
                else "medium_8_16d" if h <= 16
                else "extended_17_35d" if h <= 35
                else "exploratory_gt35d"
            )
            by_horizon.setdefault(bucket, []).append(s)

        def _agg(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
            if not rows:
                return {"n": 0, "rmse": None, "mse_skill_vs_persistence": None, "mean_crps": None, "coverage_1sigma": None, "coverage_2sigma": None}
            sq = [float(r["squared_error"]) for r in rows]
            pers_rows = [r for r in rows if r.get("persistence_squared_error") is not None]
            mse_pers = (
                round(1.0 - (sum(float(r["squared_error"]) for r in pers_rows) / max(1e-12, sum(float(r["persistence_squared_error"]) for r in pers_rows))), 6)
                if pers_rows
                else None
            )
            return {
                "n": len(rows),
                "rmse": round(math.sqrt(sum(sq) / len(sq)), 6),
                "mse_skill_vs_persistence": mse_pers,
                "mean_crps": round(sum(float(r["crps"]) for r in rows) / len(rows), 6),
                "coverage_1sigma": round(sum(1 for r in rows if r.get("within_1sigma")) / len(rows), 4),
                "coverage_2sigma": round(sum(1 for r in rows if r.get("within_2sigma")) / len(rows), 4),
            }

        return {
            "ledger_schema_version": "asmae_prospective_ledger_v1",
            "epistemic_scope": "genuinely_prospective_post_issuance_only",
            "chain_integrity_valid": bool(chain_info["chain_valid"]),
            "issuance_count": len(issuances),
            "pending_issuance_count": len(pending),
            "scored_forecast_count": len(scored_fids),
            "scored_channel_receipt_count": len(scores),
            "issuance_head_sha256": chain_info["issuance_head_sha256"],
            "score_head_sha256": chain_info["score_head_sha256"],
            "aggregate_prospective_metrics": _agg(scores),
            "by_horizon": {b: _agg(rows) for b, rows in sorted(by_horizon.items())},
            "status": (
                "evaluated_prospective_records_present"
                if scores
                else ("awaiting_future_observations" if issuances else "no_prospective_issuances_recorded_yet")
            ),
        }


def summarize_cohort_prospective_ledger(
    ledger_root: Path,
    plot_scopes: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate prospective forecast ledger health across a cohort of (plot_id, tenant_id) scopes."""
    ledger = ProspectiveForecastLedger(ledger_root)
    per_plot: List[Dict[str, Any]] = []
    tot_iss = 0
    tot_pending = 0
    tot_scored = 0
    all_valid = True
    for sc in plot_scopes:
        pid = str(sc.get("plot_id") or "")
        tid = str(sc.get("tenant_id") or "default_tenant")
        if not pid:
            continue
        s = ledger.summarize(plot_id=pid, tenant_id=tid)
        tot_iss += int(s["issuance_count"])
        tot_pending += int(s["pending_issuance_count"])
        tot_scored += int(s["scored_forecast_count"])
        all_valid = all_valid and bool(s["chain_integrity_valid"])
        per_plot.append({
            "plot_id": pid,
            "issuance_count": s["issuance_count"],
            "pending_issuance_count": s["pending_issuance_count"],
            "scored_forecast_count": s["scored_forecast_count"],
            "chain_integrity_valid": s["chain_integrity_valid"],
            "status": s["status"],
        })
    return {
        "ledger_schema_version": "asmae_prospective_ledger_v1",
        "chain_integrity_valid": all_valid,
        "total_issuances": tot_iss,
        "total_pending_issuances": tot_pending,
        "total_scored_forecasts": tot_scored,
        "per_plot": per_plot,
    }


__all__ = [
    "CausalIssuanceViolation",
    "ImmutableIssuanceError",
    "ImmutableScoreError",
    "IntegrityTamperError",
    "ProspectiveForecastIssuance",
    "ProspectiveForecastLedger",
    "ProspectiveLedgerError",
    "ProspectiveScoreReceipt",
    "RetroactiveOutcomeViolation",
    "summarize_cohort_prospective_ledger",
]
