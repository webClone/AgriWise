"""R5.0: Forecast artifact and evaluation contracts.

Design rules:
  1. Forecast origin_time and valid_time are IMMUTABLE after creation.
  2. Future observations create ForecastEvaluations, not forecast mutations.
  3. Different weather/management scenarios produce different forecast identities.
  4. No post-origin evidence enters forecast initialization.
  5. Evaluation is in observation space, not hidden state space.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from services.agribrain.scientific_contracts.authority import AuthorityScope
from services.agribrain.scientific_contracts.exceptions import ContractViolation


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


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


    parsed: List[Tuple[float, float]] = []
    for k, v in quantiles.items():
        k_str = str(k).lower().strip()
        if k_str.startswith("p"):
            alpha = float(k_str[1:]) / 100.0
        else:
            alpha = float(k_str)
            if alpha > 1.0:
                alpha /= 100.0
        parsed.append((alpha, float(v)))

    # Sort by quantile level
    parsed.sort(key=lambda x: x[0])

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

    def validate(self) -> None:
        if not self.forecast_id or not str(self.forecast_id).strip():
            raise ContractViolation("ForecastRecord requires non-blank forecast_id")
        if not self.plot_id or not str(self.plot_id).strip():
            raise ContractViolation("ForecastRecord requires non-blank plot_id")
        if not self.target_variable or not str(self.target_variable).strip():
            raise ContractViolation("ForecastRecord requires non-blank target_variable")
        if not isinstance(self.issued_at_knowledge_time, datetime) or not isinstance(self.target_epoch, datetime):
            raise ContractViolation("issued_at_knowledge_time and target_epoch must be datetime objects")
        if self.target_epoch <= self.issued_at_knowledge_time:
            raise ContractViolation(
                f"target_epoch ({self.target_epoch}) must be strictly after "
                f"issued_at_knowledge_time ({self.issued_at_knowledge_time})"
            )
        if self.horizon_days <= 0.0:
            raise ContractViolation(f"horizon_days must be positive, got {self.horizon_days}")

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
    rmse: float
    sharpness: float
    coverage_hit: bool
    evaluated_at: datetime
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

    def store_forecast(self, forecast: ForecastRecord) -> ForecastRecord:
        """Store a forecast record with strict immutability check."""
        forecast.validate()
        fid = forecast.forecast_id

        # Contamination prevention: rejected forecasts cannot contaminate the archive
        meta = forecast.metadata or {}
        if (
            meta.get("status") in ("rejected", "aborted", "failed")
            or meta.get("is_rejected") is True
            or meta.get("rejected") is True
            or str(meta.get("rejection_reason") or "").strip() != ""
        ):
            raise ContractViolation(f"Rejected forecast {fid} cannot be committed to forecast archive")

        if fid in self._forecasts:

            existing = self._forecasts[fid]
            # Verify exact content match
            if existing.to_dict() != forecast.to_dict():
                raise ContractViolation(
                    f"Forecast immutability violation: forecast_id {fid} already exists with conflicting content"
                )
            return existing

        self._forecasts[fid] = forecast

        if self.root:
            fc_dir = self.root / "forecasts"
            fc_dir.mkdir(parents=True, exist_ok=True)
            path = fc_dir / f"{fid}.json"
            new_payload = forecast.to_dict()
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
                _atomic_write_json(path, new_payload)

        return forecast

    def get_forecast(self, forecast_id: str) -> Optional[ForecastRecord]:
        """Retrieve forecast by ID."""
        if forecast_id in self._forecasts:
            return self._forecasts[forecast_id]
        if self.root:
            path = self.root / "forecasts" / f"{forecast_id}.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
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
                        metadata=data.get("metadata", {}),
                        schema_version=data.get("schema_version", FORECAST_RECORD_SCHEMA_VERSION),
                    )
                    self._forecasts[forecast_id] = record
                    return record
                except Exception:
                    return None
        return None

    def list_forecasts(
        self,
        plot_id: Optional[str] = None,
        target_variable: Optional[str] = None,
        shadow_only: Optional[bool] = None,
    ) -> List[ForecastRecord]:
        """List archived forecasts matching optional filters."""
        results = list(self._forecasts.values())
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

        obs = float(observed_value)
        eval_time = evaluated_at or datetime.now(timezone.utc)

        # Compute CRPS
        if forecast.predicted_quantiles:
            crps = compute_crps_quantiles(forecast.predicted_quantiles, obs)
            p10 = forecast.predicted_quantiles.get("p10", forecast.predicted_quantiles.get("0.1", 0.0))
            p50 = forecast.predicted_quantiles.get("p50", forecast.predicted_quantiles.get("0.5", obs))
            p90 = forecast.predicted_quantiles.get("p90", forecast.predicted_quantiles.get("0.9", obs))
            sharpness = max(0.0, p90 - p10)
            coverage_hit = p10 <= obs <= p90
            rmse = abs(obs - p50)
        elif forecast.predicted_mean is not None and forecast.predicted_std is not None:
            crps = compute_crps_gaussian(forecast.predicted_mean, forecast.predicted_std, obs)
            sharpness = 2.0 * 1.645 * forecast.predicted_std
            p10 = forecast.predicted_mean - 1.645 * forecast.predicted_std
            p90 = forecast.predicted_mean + 1.645 * forecast.predicted_std
            coverage_hit = p10 <= obs <= p90
            rmse = abs(obs - forecast.predicted_mean)
        else:
            raise ContractViolation(
                f"Forecast {forecast_id} has neither predictive quantiles nor valid mean/std distribution"
            )

        eval_id = f"eval-{forecast_id[:16]}-{int(eval_time.timestamp())}"
        record = ForecastEvaluationRecord(
            evaluation_id=eval_id,
            forecast_id=forecast_id,
            target_variable=forecast.target_variable,
            verifying_evidence_ids=tuple(verifying_evidence_ids),
            observed_value=obs,
            crps=crps,
            rmse=rmse,
            sharpness=sharpness,
            coverage_hit=coverage_hit,
            evaluated_at=eval_time,
        )

        self._evaluations.setdefault(forecast_id, []).append(record)

        if self.root:
            eval_dir = self.root / "evaluations"
            eval_dir.mkdir(parents=True, exist_ok=True)
            path = eval_dir / f"{eval_id}.json"
            _atomic_write_json(path, record.to_dict())

        return record

    def list_evaluations(self, forecast_id: Optional[str] = None) -> List[ForecastEvaluationRecord]:
        """List evaluation records for a forecast or all forecasts."""
        if forecast_id:
            return list(self._evaluations.get(forecast_id, []))
        all_evals = []
        for evs in self._evaluations.values():
            all_evals.extend(evs)
        return all_evals
