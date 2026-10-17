"""R5.0: Forecast artifact and evaluation contracts.

Design rules:
  1. Forecast origin_time and valid_time are IMMUTABLE after creation.
  2. Future observations create ForecastEvaluations, not forecast mutations.
  3. Different weather/management scenarios produce different forecast identities.
  4. No post-origin evidence enters forecast initialization.
  5. Evaluation is in observation space, not hidden state space.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import threading
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from services.agribrain.scientific_contracts.authority import AuthorityScope
from services.agribrain.scientific_contracts.exceptions import ContractViolation


def _atomic_write_json(path: Path, data: Dict[str, Any], exclusive: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive:
            try:
                os.link(str(tmp_path), str(path))
            except FileExistsError:
                try:
                    existing_payload = json.loads(path.read_text(encoding="utf-8"))
                    new_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
                    existing_hash = hashlib.sha256(json.dumps(existing_payload, sort_keys=True).encode("utf-8")).hexdigest()
                    if new_hash != existing_hash:
                        raise ContractViolation(f"Forecast immutability violation: conflicting content exists at {path}")
                    return
                except json.JSONDecodeError:
                    raise ContractViolation(f"Corrupted forecast file at {path}")
        else:
            os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass



FORECAST_SCHEMA_VERSION = "forecast_artifact_v1"
EVALUATION_SCHEMA_VERSION = "forecast_evaluation_v1"
FORECAST_RECORD_SCHEMA_VERSION = "forecast_record_v1"
FORECAST_EVAL_RECORD_SCHEMA_VERSION = "forecast_eval_record_v1"


class EvaluationSpace(Enum):
    """In what space the forecast was evaluated."""
    OBSERVATION_SPACE = "observation_space"
    INDEPENDENT_REFERENCE = "independent_reference"
    POSTERIOR_DIAGNOSTIC = "posterior_diagnostic"


class DomainStatus(Enum):
    """Whether the forecast was in-domain for the evaluated region/crop."""
    IN_DOMAIN = "in_domain"
    PARTIAL_SUPPORT = "partial_support"
    OUT_OF_DOMAIN = "out_of_domain"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ForecastArtifact:
    """Immutable forecast artifact.

    Once created, origin_time and valid_time cannot change.
    Different weather/management scenarios produce different forecast IDs.
    """
    forecast_id: str
    origin_belief_id: str
    origin_time: datetime
    valid_time: datetime
    horizon_days: float

    # Scenario identity
    weather_scenario_id: str = ""
    management_scenario_id: str = ""

    # Distribution references
    state_distribution_ref: Optional[str] = None
    observation_projection_ref: Optional[str] = None

    # Provenance
    model_version: str = ""
    calibration_version: str = ""

    # Schema
    schema_version: str = FORECAST_SCHEMA_VERSION

    def validate(self) -> None:
        """Check forecast immutability invariants."""
        if self.valid_time <= self.origin_time:
            raise ValueError(
                f"valid_time ({self.valid_time}) must be after "
                f"origin_time ({self.origin_time})"
            )
        actual_horizon = (
            self.valid_time - self.origin_time
        ).total_seconds() / 86400.0
        if abs(actual_horizon - self.horizon_days) > 1.0:
            raise ValueError(
                f"horizon_days ({self.horizon_days}) inconsistent with "
                f"origin-valid gap ({actual_horizon:.1f} days)"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "origin_belief_id": self.origin_belief_id,
            "origin_time": self.origin_time.isoformat(),
            "valid_time": self.valid_time.isoformat(),
            "horizon_days": self.horizon_days,
            "weather_scenario_id": self.weather_scenario_id,
            "management_scenario_id": self.management_scenario_id,
            "state_distribution_ref": self.state_distribution_ref,
            "observation_projection_ref": self.observation_projection_ref,
            "model_version": self.model_version,
            "calibration_version": self.calibration_version,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ForecastEvaluation:
    """Immutable evaluation of a forecast against later evidence.

    Created when new observations arrive AFTER a forecast's origin_time.
    The forecast itself is NEVER mutated.
    """
    evaluation_id: str
    forecast_id: str
    reference_evidence_ids: Tuple[str, ...] = ()
    evaluation_space: EvaluationSpace = EvaluationSpace.OBSERVATION_SPACE

    # Metrics (per-variable)
    metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Calibration
    calibration_bin: Optional[str] = None
    domain_status: DomainStatus = DomainStatus.UNKNOWN

    # Metadata
    evaluated_at: Optional[datetime] = None
    schema_version: str = EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "forecast_id": self.forecast_id,
            "reference_evidence_ids": list(self.reference_evidence_ids),
            "evaluation_space": self.evaluation_space.value,
            "metrics": dict(self.metrics),
            "calibration_bin": self.calibration_bin,
            "domain_status": self.domain_status.value,
            "evaluated_at": (
                self.evaluated_at.isoformat() if self.evaluated_at else None
            ),
            "schema_version": self.schema_version,
        }


# ============================================================================
# PROBABILISTIC SCORING & CALIBRATION (CRPS, SHARPNESS, COVERAGE)
# ============================================================================

def parse_quantile_level(k: Any) -> float:
    """Normalize and validate quantile level key (e.g. 'p50', '50%', '0.5', '50', 'q50') to float in [0.0, 1.0]."""
    k_str = str(k).lower().strip()
    try:
        if k_str.startswith("p") or k_str.startswith("q"):
            val = float(k_str[1:])
            if val > 1.0:
                val /= 100.0
        elif k_str.endswith("%"):
            val = float(k_str[:-1]) / 100.0
        else:
            val = float(k_str)
            if val > 1.0:
                val /= 100.0
        val = round(val, 6)
    except Exception as exc:
        raise ContractViolation(f"Invalid quantile level key: {k}") from exc
    if not (0.0 <= val <= 1.0) or math.isnan(val) or math.isinf(val):
        raise ContractViolation(f"Invalid quantile level {k}: level must be in [0.0, 1.0]")
    return val


def compute_crps_quantiles(quantiles: Dict[str, float], observed: float) -> float:
    """Continuous Ranked Probability Score (CRPS) for quantile forecasts via pinball loss.

    Parameters
    ----------
    quantiles : Dict[str, float]
        Mapping from quantile key (e.g. 'p10', 'p50', 'p90' or '0.1', '0.5', '0.9') to value.
    observed : float
        Realized ground truth observation value.
    """
    if not quantiles:
        raise ContractViolation("Cannot compute CRPS: predictive quantiles are missing or empty; cannot return synthetic perfect score")

    if isinstance(observed, bool) or not isinstance(observed, (int, float)) or not math.isfinite(observed):
        raise ContractViolation(f"Observed value must be finite real number, got {observed}")

    level_map: Dict[float, float] = {}
    for k, v in quantiles.items():
        alpha = parse_quantile_level(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ContractViolation(f"Invalid quantile value {v} for level {k}: must be numeric")
        val = float(v)
        if math.isnan(val) or math.isinf(val):
            raise ContractViolation(f"Invalid quantile value {v} for level {k}: must be finite")
        if alpha in level_map and abs(level_map[alpha] - val) > 1e-6:
            raise ContractViolation(f"Conflicting duplicate quantile level {alpha}: {level_map[alpha]} vs {val}")
        level_map[alpha] = val

    # Sort by quantile level, deduplicating aliases via level_map
    parsed: List[Tuple[float, float]] = sorted(level_map.items(), key=lambda x: x[0])

    # Validate monotonicity of quantile values
    for i in range(len(parsed) - 1):
        if parsed[i][1] > parsed[i + 1][1]:
            raise ContractViolation(
                f"Quantile values must be monotonic: level {parsed[i][0]} value {parsed[i][1]} > level {parsed[i+1][0]} value {parsed[i+1][1]}"
            )

    losses: List[float] = []
    for alpha, q in parsed:
        if observed < q:
            loss = 2.0 * (1.0 - alpha) * (q - observed)
        else:
            loss = 2.0 * alpha * (observed - q)
        losses.append(loss)

    return sum(losses) / float(len(losses))


def compute_crps_gaussian(mean: float, std: float, observed: float) -> float:
    """Analytical CRPS for a univariate normal distribution N(mean, std^2)."""
    if isinstance(mean, bool) or not isinstance(mean, (int, float)) or not math.isfinite(mean):
        raise ContractViolation(f"Gaussian mean must be a finite real number, got {mean}")
    if isinstance(observed, bool) or not isinstance(observed, (int, float)) or not math.isfinite(observed):
        raise ContractViolation(f"Observed value must be a finite real number, got {observed}")
    if isinstance(std, bool) or not isinstance(std, (int, float)) or std < 0.0 or not math.isfinite(std):
        raise ContractViolation(f"Gaussian sigma must be finite non-negative, got {std}")
    if std <= 1e-9:
        return abs(observed - mean)

    z = (observed - mean) / std
    # Normal CDF Phi(z) = 0.5 * (1 + erf(z / sqrt(2)))
    phi_cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    # Normal PDF phi(z)
    phi_pdf = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * z * z)

    crps = std * (z * (2.0 * phi_cdf - 1.0) + 2.0 * phi_pdf - (1.0 / math.sqrt(math.pi)))
    return max(0.0, float(crps))


def compute_interval_coverage(
    intervals: Sequence[Tuple[float, float]],
    observations: Sequence[float],
) -> float:
    """Compute empirical coverage probability: fraction of observations in interval [lower, upper]."""
    if not intervals or not observations or len(intervals) != len(observations):
        return 0.0
    hits = 0
    for (lower, upper), obs in zip(intervals, observations):
        if lower <= obs <= upper:
            hits += 1
    return float(hits) / float(len(observations))


# ============================================================================
# IMMUTABLE FORECAST RECORD & EVALUATION RECORD (WP12 / P05.1 / P06.2)
# ============================================================================

def compute_forecast_id(
    plot_id: str,
    target_variable: str,
    issued_at: datetime,
    target_epoch: datetime,
    model_version: str,
    predicted_quantiles: Dict[str, float],
) -> str:
    """Deterministic content hash for a forecast record."""
    payload = {
        "plot_id": plot_id,
        "target_variable": target_variable,
        "issued_at": issued_at.isoformat(),
        "target_epoch": target_epoch.isoformat(),
        "model_version": model_version,
        "quantiles": {k: float(v) for k, v in sorted(predicted_quantiles.items())},
    }
    raw = json.dumps(payload, sort_keys=True)
    return "fc-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class ForecastRecord:
    """Immutable forecast record archived prior to future observation arrival (WP12 / P05.1).

    Invariants:
    1. target_epoch must be strictly after issued_at_knowledge_time.
    2. Once stored, forecast_id and predicted distribution are immutable.
    3. Shadow forecasts carry AuthorityScope.OPERATIONAL_SHADOW and cannot actuate machinery.
    """

    forecast_id: str
    plot_id: str
    target_variable: str
    issued_at_knowledge_time: datetime
    target_epoch: datetime
    horizon_days: float
    predicted_quantiles: Dict[str, float] = field(default_factory=dict)
    predicted_mean: Optional[float] = None
    predicted_std: Optional[float] = None
    model_id: str = ""
    model_version: str = ""
    calibration_version: str = ""
    authority_scope: AuthorityScope = AuthorityScope.OPERATIONAL_SHADOW
    is_shadow: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = FORECAST_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()
        object.__setattr__(self, "predicted_quantiles", copy.deepcopy(self.predicted_quantiles))
        object.__setattr__(self, "metadata", copy.deepcopy(self.metadata))

    def validate(self) -> None:
        if not self.forecast_id or not str(self.forecast_id).strip():
            raise ContractViolation("ForecastRecord requires non-blank forecast_id")
        fid = str(self.forecast_id)
        if ".." in fid or "/" in fid or "\\" in fid or Path(fid).name != fid or fid in (".", ".."):
            raise ContractViolation(f"ForecastRecord forecast_id contains unsafe path segments: {fid}")
        if not self.plot_id or not str(self.plot_id).strip():
            raise ContractViolation("ForecastRecord requires non-blank plot_id")
        if not self.target_variable or not str(self.target_variable).strip():
            raise ContractViolation("ForecastRecord requires non-blank target_variable")
        if not isinstance(self.issued_at_knowledge_time, datetime) or not isinstance(self.target_epoch, datetime):
            raise ContractViolation("issued_at_knowledge_time and target_epoch must be datetime objects")
        if (
            self.issued_at_knowledge_time.tzinfo is None
            or self.issued_at_knowledge_time.utcoffset() is None
            or self.target_epoch.tzinfo is None
            or self.target_epoch.utcoffset() is None
        ):
            raise ContractViolation("issued_at_knowledge_time and target_epoch must be timezone-aware datetime objects with defined utcoffset")
        if self.target_epoch <= self.issued_at_knowledge_time:
            raise ContractViolation(
                f"target_epoch ({self.target_epoch}) must be strictly after "
                f"issued_at_knowledge_time ({self.issued_at_knowledge_time})"
            )
        if isinstance(self.horizon_days, bool) or not isinstance(self.horizon_days, (int, float)) or not math.isfinite(self.horizon_days) or self.horizon_days <= 0.0:
            raise ContractViolation(f"horizon_days must be finite positive number, got {self.horizon_days}")
        actual_days = (self.target_epoch - self.issued_at_knowledge_time).total_seconds() / 86400.0
        if abs(self.horizon_days - actual_days) > 0.05:
            raise ContractViolation(f"horizon_days ({self.horizon_days}) is inconsistent with target_epoch - issued_at interval ({actual_days:.2f} days)")
        if self.predicted_mean is not None:
            if isinstance(self.predicted_mean, bool) or not isinstance(self.predicted_mean, (int, float)) or not math.isfinite(self.predicted_mean):
                raise ContractViolation(f"predicted_mean must be finite, got {self.predicted_mean}")
        if self.predicted_std is not None:
            if isinstance(self.predicted_std, bool) or not isinstance(self.predicted_std, (int, float)) or self.predicted_std < 0.0 or not math.isfinite(self.predicted_std):
                raise ContractViolation(f"predicted_std must be non-negative finite, got {self.predicted_std}")
        if self.predicted_quantiles:
            if not isinstance(self.predicted_quantiles, dict):
                raise ContractViolation("predicted_quantiles must be a dictionary")
            level_map: Dict[float, float] = {}
            for k, v in self.predicted_quantiles.items():
                alpha = parse_quantile_level(k)
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ContractViolation(f"Invalid quantile value {v} for level {k}: must be numeric")
                val = float(v)
                if math.isnan(val) or math.isinf(val):
                    raise ContractViolation(f"Invalid quantile value {v} for level {k}: must be finite")
                if alpha in level_map and abs(level_map[alpha] - val) > 1e-6:
                    raise ContractViolation(f"Conflicting duplicate quantile level {alpha}: {level_map[alpha]} vs {val}")
                level_map[alpha] = val

            parsed_q = sorted(level_map.items(), key=lambda x: x[0])
            for i in range(len(parsed_q) - 1):
                if parsed_q[i][1] > parsed_q[i + 1][1]:
                    raise ContractViolation(
                        f"Quantile values must be monotonic: level {parsed_q[i][0]} value {parsed_q[i][1]} > level {parsed_q[i+1][0]} value {parsed_q[i+1][1]}"
                    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "plot_id": self.plot_id,
            "target_variable": self.target_variable,
            "issued_at_knowledge_time": self.issued_at_knowledge_time.isoformat(),
            "target_epoch": self.target_epoch.isoformat(),
            "horizon_days": self.horizon_days,
            "predicted_quantiles": dict(self.predicted_quantiles),
            "predicted_mean": self.predicted_mean,
            "predicted_std": self.predicted_std,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "calibration_version": self.calibration_version,
            "authority_scope": self.authority_scope.value,
            "is_shadow": self.is_shadow,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ForecastEvaluationRecord:
    """Immutable evaluation of a ForecastRecord against realized observations."""

    evaluation_id: str
    forecast_id: str
    target_variable: str
    verifying_evidence_ids: Tuple[str, ...]
    observed_value: float
    crps: float
    rmse: Optional[float] = None
    sharpness: Optional[float] = None
    coverage_hit: Optional[bool] = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    domain_status: DomainStatus = DomainStatus.IN_DOMAIN
    evaluation_space: EvaluationSpace = EvaluationSpace.OBSERVATION_SPACE
    schema_version: str = FORECAST_EVAL_RECORD_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "forecast_id": self.forecast_id,
            "target_variable": self.target_variable,
            "verifying_evidence_ids": list(self.verifying_evidence_ids),
            "observed_value": self.observed_value,
            "crps": self.crps,
            "rmse": self.rmse,
            "sharpness": self.sharpness,
            "coverage_hit": self.coverage_hit,
            "evaluated_at": self.evaluated_at.isoformat(),
            "domain_status": self.domain_status.value,
            "evaluation_space": self.evaluation_space.value,
            "schema_version": self.schema_version,
        }


class ImmutableForecastArchive:
    """Durable, immutable forecast archive and evaluation ledger.

    Invariants:
    1. Forecast records cannot be overwritten with differing content.
    2. Forecast evaluations are stored in observation space without mutating the forecast.
    3. Shadow forecasts cannot alter operational belief state or Layer 8 prescriptions.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else None
        self._forecasts: Dict[str, ForecastRecord] = {}
        self._evaluations: Dict[str, List[ForecastEvaluationRecord]] = {}
        self._lock = threading.RLock()

    def store_forecast(self, forecast: ForecastRecord) -> ForecastRecord:
        """Store a forecast record with strict immutability check."""
        snapshot = copy.deepcopy(forecast)
        snapshot.validate()
        fid = snapshot.forecast_id

        if ".." in fid or "/" in fid or "\\" in fid or Path(fid).name != fid or fid in (".", ".."):
            raise ContractViolation(f"Unsafe forecast_id: {fid}")

        # Contamination prevention: rejected forecasts cannot contaminate the archive
        meta = snapshot.metadata or {}
        if (
            meta.get("status") in ("rejected", "aborted", "failed")
            or meta.get("is_rejected") is True
            or meta.get("rejected") is True
            or str(meta.get("rejection_reason") or "").strip() != ""
        ):
            raise ContractViolation(f"Rejected forecast {fid} cannot be committed to forecast archive")

        with self._lock:
            if fid in self._forecasts:
                existing = self._forecasts[fid]
                if existing.to_dict() != snapshot.to_dict():
                    raise ContractViolation(
                        f"Forecast immutability violation: forecast_id {fid} already exists with conflicting content"
                    )

            if self.root:
                fc_dir = self.root / "forecasts"
                fc_dir.mkdir(parents=True, exist_ok=True)
                path = fc_dir / f"{fid}.json"
                new_payload = snapshot.to_dict()
                if path.exists():
                    try:
                        existing_payload = json.loads(path.read_text(encoding="utf-8"))
                        new_hash = hashlib.sha256(json.dumps(new_payload, sort_keys=True).encode("utf-8")).hexdigest()
                        existing_hash = hashlib.sha256(json.dumps(existing_payload, sort_keys=True).encode("utf-8")).hexdigest()
                        if new_hash != existing_hash:
                            raise ContractViolation(
                                f"Forecast immutability violation: file {path} exists with conflicting content"
                            )
                    except json.JSONDecodeError:
                        raise ContractViolation(f"Corrupted forecast file at {path}")
                else:
                    _atomic_write_json(path, new_payload, exclusive=True)

            self._forecasts[fid] = copy.deepcopy(snapshot)

        return copy.deepcopy(snapshot)

    def get_forecast(self, forecast_id: str) -> Optional[ForecastRecord]:
        """Retrieve forecast by ID."""
        fid = str(forecast_id)
        if ".." in fid or "/" in fid or "\\" in fid or Path(fid).name != fid or fid in (".", ".."):
            return None

        with self._lock:
            if fid in self._forecasts:
                rec = self._forecasts[fid]
                meta = rec.metadata or {}
                if (
                    meta.get("status") in ("rejected", "aborted", "failed")
                    or meta.get("is_rejected") is True
                    or meta.get("rejected") is True
                    or str(meta.get("rejection_reason") or "").strip() != ""
                ):
                    return None
                return copy.deepcopy(rec)
            if self.root:
                path = self.root / "forecasts" / f"{fid}.json"
                if path.exists():
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if not isinstance(data, dict):
                            raise ContractViolation(f"Corrupt forecast record at {path}: expected dict, got {type(data).__name__}")
                        meta = data.get("metadata", {})
                        if not isinstance(meta, dict):
                            raise ContractViolation(f"Corrupt forecast metadata at {path}: expected dict, got {type(meta).__name__}")
                        if (
                            meta.get("status") in ("rejected", "aborted", "failed")
                            or meta.get("is_rejected") is True
                            or meta.get("rejected") is True
                            or str(meta.get("rejection_reason") or "").strip() != ""
                        ):
                            return None
                        record = ForecastRecord(
                            forecast_id=data["forecast_id"],
                            plot_id=data["plot_id"],
                            target_variable=data["target_variable"],
                            issued_at_knowledge_time=datetime.fromisoformat(data["issued_at_knowledge_time"]),
                            target_epoch=datetime.fromisoformat(data["target_epoch"]),
                            horizon_days=data["horizon_days"],
                            predicted_quantiles=data.get("predicted_quantiles", {}),
                            predicted_mean=data.get("predicted_mean"),
                            predicted_std=data.get("predicted_std"),
                            model_id=data.get("model_id", ""),
                            model_version=data.get("model_version", ""),
                            calibration_version=data.get("calibration_version", ""),
                            authority_scope=AuthorityScope(data.get("authority_scope", "OPERATIONAL_SHADOW")),
                            is_shadow=data.get("is_shadow", True),
                            metadata=meta,
                            schema_version=data.get("schema_version", FORECAST_RECORD_SCHEMA_VERSION),
                        )
                        self._forecasts[fid] = record
                        return copy.deepcopy(record)
                    except Exception as e:
                        if isinstance(e, (ContractViolation, json.JSONDecodeError, KeyError, ValueError, AttributeError, TypeError)):
                            raise ContractViolation(f"Corrupt or unreadable forecast record at {path}: {e}") from e
                        return None
        return None

    def list_forecasts(
        self,
        plot_id: Optional[str] = None,
        target_variable: Optional[str] = None,
        shadow_only: Optional[bool] = None,
    ) -> List[ForecastRecord]:
        """List archived forecasts matching optional filters."""
        results = [copy.deepcopy(f) for f in self._forecasts.values()]
        if plot_id:
            results = [f for f in results if f.plot_id == plot_id]
        if target_variable:
            results = [f for f in results if f.target_variable == target_variable]
        if shadow_only is not None:
            results = [f for f in results if f.is_shadow == shadow_only]
        return results

    def evaluate_forecast(
        self,
        forecast_id: str,
        observed_value: float,
        verifying_evidence_ids: Sequence[str],
        evaluated_at: Optional[datetime] = None,
    ) -> ForecastEvaluationRecord:
        """Evaluate an archived forecast against realized observation.

        The forecast record is NEVER mutated.
        """
        forecast = self.get_forecast(forecast_id)
        if not forecast:
            raise ContractViolation(f"Forecast {forecast_id} not found in archive")

        meta = forecast.metadata or {}
        if (
            meta.get("status") in ("rejected", "aborted", "failed")
            or meta.get("is_rejected") is True
            or meta.get("rejected") is True
            or str(meta.get("rejection_reason") or "").strip() != ""
        ):
            raise ContractViolation(f"Forecast {forecast_id} is rejected/aborted and cannot be evaluated")

        if isinstance(observed_value, bool) or not isinstance(observed_value, (int, float)):
            raise ContractViolation(f"Observed value must be a real finite number, got {type(observed_value).__name__}: {observed_value!r}")
        obs = float(observed_value)
        if not math.isfinite(obs):
            raise ContractViolation(f"Observed value must be finite, got {obs}")

        if isinstance(verifying_evidence_ids, (str, bytes)) or not hasattr(verifying_evidence_ids, "__iter__"):
            raise ContractViolation("verifying_evidence_ids must be a collection of string IDs")
        if not verifying_evidence_ids:
            raise ContractViolation("Verifying evidence IDs cannot be empty")
        cleaned_evidence = []
        for x in verifying_evidence_ids:
            if x is None or not isinstance(x, str) or not x.strip():
                raise ContractViolation(f"Verifying evidence ID must be non-blank string, got: {x!r}")
            cleaned_evidence.append(x.strip())
        if not cleaned_evidence:
            raise ContractViolation("Verifying evidence IDs cannot be empty")
        canon_evidence = tuple(sorted(cleaned_evidence))

        if not (forecast.predicted_quantiles or (forecast.predicted_mean is not None and forecast.predicted_std is not None)):
            raise ContractViolation(
                f"Forecast {forecast_id} has neither predictive quantiles nor valid mean/std"
            )

        eval_time = evaluated_at or datetime.now(timezone.utc)
        if forecast.target_epoch and eval_time < forecast.target_epoch:
            raise ContractViolation(f"Evaluation time {eval_time} cannot precede forecast target epoch {forecast.target_epoch}")
        if forecast.issued_at_knowledge_time and eval_time < forecast.issued_at_knowledge_time:
            raise ContractViolation(f"Evaluation time {eval_time} cannot precede forecast issuance time {forecast.issued_at_knowledge_time}")

        # Compute CRPS and evaluation metrics
        if forecast.predicted_quantiles:
            crps = compute_crps_quantiles(forecast.predicted_quantiles, obs)

            norm_q = {}
            for k, v in forecast.predicted_quantiles.items():
                try:
                    alpha = parse_quantile_level(k)
                    norm_q[alpha] = float(v)
                except Exception:
                    continue

            p50 = norm_q.get(0.5)
            if p50 is None and forecast.predicted_mean is not None:
                p50 = float(forecast.predicted_mean)

            if p50 is not None:
                rmse = abs(obs - p50)
            else:
                rmse = None

            p10 = norm_q.get(0.1)
            p90 = norm_q.get(0.9)

            if p10 is not None and p90 is not None:
                sharpness = max(0.0, p90 - p10)
                coverage_hit = (p10 <= obs <= p90)
            else:
                sharpness = None
                coverage_hit = None

        elif forecast.predicted_mean is not None and forecast.predicted_std is not None:
            crps = compute_crps_gaussian(forecast.predicted_mean, forecast.predicted_std, obs)
            sharpness = 2.0 * 1.28155 * forecast.predicted_std
            p10 = forecast.predicted_mean - 1.28155 * forecast.predicted_std
            p90 = forecast.predicted_mean + 1.28155 * forecast.predicted_std
            coverage_hit = (p10 <= obs <= p90)
            rmse = abs(obs - forecast.predicted_mean)
        else:
            raise ContractViolation(
                f"Forecast {forecast_id} has neither predictive quantiles nor valid mean/std distribution"
            )

        ev_sig = hashlib.sha256(json.dumps(list(canon_evidence)).encode("utf-8")).hexdigest()
        h = hashlib.sha256(f"{forecast_id}:{obs}:{ev_sig}:{eval_time.isoformat()}".encode("utf-8")).hexdigest()[:12]
        eval_id = f"eval-{forecast_id[:16]}-{int(eval_time.timestamp())}-{h}"

        record = ForecastEvaluationRecord(
            evaluation_id=eval_id,
            forecast_id=forecast_id,
            target_variable=forecast.target_variable,
            verifying_evidence_ids=canon_evidence,
            observed_value=obs,
            crps=crps,
            rmse=rmse,
            sharpness=sharpness,
            coverage_hit=coverage_hit,
            evaluated_at=eval_time,
        )

        with self._lock:
            if self.root:
                eval_dir = self.root / "evaluations"
                eval_dir.mkdir(parents=True, exist_ok=True)
                path = eval_dir / f"{eval_id}.json"
                _atomic_write_json(path, record.to_dict(), exclusive=True)

            existing_evals = self._evaluations.setdefault(forecast_id, [])
            if not any(e.evaluation_id == record.evaluation_id for e in existing_evals):
                existing_evals.append(record)

        return record

    def list_evaluations(self, forecast_id: Optional[str] = None) -> List[ForecastEvaluationRecord]:
        """List evaluation records for a forecast or all forecasts."""
        if forecast_id:
            return list(self._evaluations.get(forecast_id, []))
        all_evals = []
        for evs in self._evaluations.values():
            all_evals.extend(evs)
        return all_evals
