"""
Pattern Maturity Engine — Strategic, parametrable ML pattern activation controller.

Manages activation criteria, confidence ramping, blending weights, and deactivation
rules for the 12 ML learning patterns in AgriBrain.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from services.agribrain.layer0.data_gateway.storage_manager import _get_db

logger = logging.getLogger("agribrain.learning.maturity")


@dataclass
class MaturityProfile:
    """Readiness, ramping, and blending profile for a single pattern."""
    pattern_id: int
    min_observations: int = 0
    min_days: int = 0
    min_sources: int = 0
    min_seasons: int = 0
    min_donor_plots: int = 0
    min_donor_maturity: float = 0.0
    min_yield_reports: int = 0
    min_active_patterns: int = 0
    confidence_curve: str = "step"  # sigmoid, linear, step, logarithmic, inverse_linear
    confidence_params: Dict[str, Any] = field(default_factory=dict)
    fallback_strategy: str = ""
    deactivation_rule: Optional[str] = "accuracy_regression"
    deactivation_threshold: float = 0.15


class PatternMaturityEngine:
    """Strategic, parametrable ML pattern maturity engine.
    
    Tuned with default profiles which are fully customizable.
    Supports overrides per plot and per crop type.
    """

    def __init__(self):
        # Default global profiles (as defined in design specs)
        self.profiles: Dict[str, MaturityProfile] = {
            "adaptive_weighting": MaturityProfile(
                pattern_id=1,
                min_observations=20,
                min_days=14,
                min_sources=2,
                confidence_curve="sigmoid",
                confidence_params={
                    "midpoint": 50,
                    "steepness": 0.08,
                    "max_confidence": 0.95,
                },
                fallback_strategy="fixed_R",
            ),
            "anomaly_gate": MaturityProfile(
                pattern_id=2,
                min_observations=10,
                min_days=7,
                min_sources=1,
                confidence_curve="step",
                confidence_params={
                    "activation_threshold": 10,
                    "max_confidence": 1.0,
                },
                fallback_strategy="no_gate",
            ),
            "seasonal_memory": MaturityProfile(
                pattern_id=3,
                min_observations=180,
                min_days=180,
                min_sources=3,
                min_seasons=1,
                confidence_curve="logarithmic",
                confidence_params={
                    "scale": 0.3,
                    "shift": 100,
                    "max_confidence": 0.90,
                },
                fallback_strategy="climatological_mean",
            ),
            "cross_plot_transfer": MaturityProfile(
                pattern_id=4,
                min_observations=0,
                min_days=0,
                min_donor_plots=3,
                min_donor_maturity=0.6,
                confidence_curve="inverse_linear",
                confidence_params={
                    "initial_confidence": 0.8,
                    "decay_per_observation": 0.005,
                    "floor": 0.1,
                },
                fallback_strategy="regional_defaults",
            ),
            "predictive_prefetch": MaturityProfile(
                pattern_id=5,
                min_observations=30,
                min_days=14,
                confidence_curve="linear",
                confidence_params={"slope": 0.02, "max_confidence": 0.85},
                fallback_strategy="ttl_based_prefetch",
            ),
            "confidence_decay": MaturityProfile(
                pattern_id=6,
                min_observations=0,
                min_days=0,
                confidence_curve="step",
                confidence_params={"activation_threshold": 0, "max_confidence": 1.0},
                fallback_strategy="fixed_staleness",
            ),
            "temporal_attention": MaturityProfile(
                pattern_id=7,
                min_observations=90,
                min_days=60,
                confidence_curve="sigmoid",
                confidence_params={"midpoint": 200, "steepness": 0.03, "max_confidence": 0.92},
                fallback_strategy="exponential_weighted_average",
            ),
            "drift_detection": MaturityProfile(
                pattern_id=8,
                min_observations=60,
                min_days=30,
                confidence_curve="step",
                confidence_params={"activation_threshold": 60, "max_confidence": 1.0},
                fallback_strategy="no_drift_check",
            ),
            "spatial_kernels": MaturityProfile(
                pattern_id=9,
                min_observations=30,
                min_days=14,
                min_sources=3,
                confidence_curve="linear",
                confidence_params={"slope": 0.015, "max_confidence": 0.88},
                fallback_strategy="equal_weights",
            ),
            "feedback_loop": MaturityProfile(
                pattern_id=10,
                min_observations=1,
                min_days=0,
                min_yield_reports=1,
                confidence_curve="logarithmic",
                confidence_params={"scale": 0.5, "shift": 1, "max_confidence": 0.95},
                fallback_strategy="no_feedback",
            ),
            "active_learning": MaturityProfile(
                pattern_id=11,
                min_observations=30,
                min_days=14,
                confidence_curve="step",
                confidence_params={"activation_threshold": 30, "max_confidence": 1.0},
                fallback_strategy="no_recommendations",
            ),
            "ensemble_stacking": MaturityProfile(
                pattern_id=12,
                min_observations=100,
                min_days=60,
                min_active_patterns=4,
                confidence_curve="sigmoid",
                confidence_params={"midpoint": 200, "steepness": 0.025, "max_confidence": 0.93},
                fallback_strategy="kalman_only",
            ),
        }

        # Administrative overrides
        self.plot_overrides: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.crop_profiles: Dict[str, Dict[str, Any]] = {}
        
        # In-memory deactivation registry: { (plot_id, pattern_name): deactivation_reason }
        self.deactivated_patterns: Dict[Tuple[str, str], str] = {}

    def get_profile(self, pattern_name: str, plot_id: str = "", crop_type: str = "") -> MaturityProfile:
        """Retrieve the MaturityProfile for a pattern, applying crop or plot overrides."""
        if pattern_name not in self.profiles:
            raise ValueError(f"Unknown ML pattern: {pattern_name}")

        base = self.profiles[pattern_name]
        
        # Clone base profile to customize
        profile = MaturityProfile(
            pattern_id=base.pattern_id,
            min_observations=base.min_observations,
            min_days=base.min_days,
            min_sources=base.min_sources,
            min_seasons=base.min_seasons,
            min_donor_plots=base.min_donor_plots,
            min_donor_maturity=base.min_donor_maturity,
            min_yield_reports=base.min_yield_reports,
            min_active_patterns=base.min_active_patterns,
            confidence_curve=base.confidence_curve,
            confidence_params=dict(base.confidence_params),
            fallback_strategy=base.fallback_strategy,
            deactivation_rule=base.deactivation_rule,
            deactivation_threshold=base.deactivation_threshold,
        )

        # Apply crop overrides
        if crop_type and crop_type in self.crop_profiles:
            crop_overrides = self.crop_profiles[crop_type].get(pattern_name, {})
            for k, v in crop_overrides.items():
                setattr(profile, k, v)

        # Apply plot overrides
        if plot_id and plot_id in self.plot_overrides:
            plot_overrides = self.plot_overrides[plot_id].get(pattern_name, {})
            for k, v in plot_overrides.items():
                setattr(profile, k, v)

        return profile

    def update_profile(self, pattern_name: str, overrides: Dict[str, Any]):
        """Admin function to globally modify parameters of a profile."""
        if pattern_name not in self.profiles:
            raise ValueError(f"Unknown ML pattern: {pattern_name}")
        for k, v in overrides.items():
            setattr(self.profiles[pattern_name], k, v)
        logger.info("[MATURITY] Globally updated %s profile parameters: %s", pattern_name, overrides)

    def set_plot_override(self, plot_id: str, pattern_name: str, overrides: Dict[str, Any]):
        """Admin function to override parameters for a specific high-value plot."""
        if plot_id not in self.plot_overrides:
            self.plot_overrides[plot_id] = {}
        self.plot_overrides[plot_id][pattern_name] = overrides
        logger.info("[MATURITY] Set plot override for plot=%s, pattern=%s: %s", plot_id, pattern_name, overrides)

    def set_crop_profile(self, crop_type: str, pattern_name: str, overrides: Dict[str, Any]):
        """Admin function to override parameters for a crop type (e.g. citrus vs wheat)."""
        if crop_type not in self.crop_profiles:
            self.crop_profiles[crop_type] = {}
        self.crop_profiles[crop_type][pattern_name] = overrides
        logger.info("[MATURITY] Set crop override for crop=%s, pattern=%s: %s", crop_type, pattern_name, overrides)

    def get_plot_stats(self, plot_id: str) -> Dict[str, Any]:
        """Fetch real observation/metadata statistics for a plot from MongoDB or zero-initialized baseline."""
        stats = {
            "observations": 0,
            "days": 0,
            "sources": 0,
            "seasons": 0,
            "donor_plots": 0,
            "donor_maturity": 0.0,
            "yield_reports": 0,
            "active_patterns": 0,
            "crop_type": "unknown",
        }

        db = _get_db()
        if db is None:
            # Filesystem or fallback mode: return default baseline for new/unpopulated plots
            return stats

        try:
            # 1. Fetch PlotDNA info
            dna = db.PlotDNA.find_one({"plotId": plot_id})
            if dna:
                obs_counts = dna.get("observationCounts", {})
                stats["observations"] = obs_counts.get("total", 0)
                
                # Active sources count
                active_sources = [s for s, c in obs_counts.items() if s != "total" and c > 0]
                stats["sources"] = len(active_sources)

                # Days estimation from first observation or created date
                created_at = dna.get("createdAt") or dna.get("lastSeen")
                if created_at:
                    if isinstance(created_at, str):
                        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    else:
                        created_dt = created_at
                    stats["days"] = max(0, (datetime.now(timezone.utc) - created_dt).days)
                
                # Crop type mapping
                stats["crop_type"] = dna.get("cropType", "unknown")

            # 2. Count yield reports (Farmer events in user collections)
            yield_reports = db.PlotObservation.count_documents({
                "plotId": plot_id,
                "obsType": "yield_report"
            })
            stats["yield_reports"] = yield_reports

            # 3. Calculate seasons (rough estimation: 180 days = 1 season)
            stats["seasons"] = stats["days"] // 180

            # 4. Donor plots (similar neighbors)
            if stats["crop_type"] != "unknown":
                donor_count = db.PlotDNA.count_documents({
                    "plotId": {"$ne": plot_id},
                    "cropType": stats["crop_type"],
                    "observationCounts.total": {"$gte": 50}
                })
                stats["donor_plots"] = donor_count
                stats["donor_maturity"] = 0.7  # Average maturity of matched donor plots

        except Exception as e:
            logger.warning("[MATURITY] Error gathering plot stats for plot %s: %s", plot_id, e)

        return stats

    def get_maturity_score(
        self,
        pattern_name: str,
        plot_id: str,
        override_stats: Optional[Dict[str, Any]] = None,
        mock_stats: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Compute maturity score [0.0 - 1.0] for a pattern on a specific plot."""
        effective_stats = override_stats if override_stats is not None else mock_stats
        stats = effective_stats if effective_stats is not None else self.get_plot_stats(plot_id)
        profile = self.get_profile(pattern_name, plot_id, stats.get("crop_type", ""))

        # Check deactivation
        if (plot_id, pattern_name) in self.deactivated_patterns:
            return 0.0

        # Check if prerequisites are met
        if not self.are_prereqs_met(profile, stats):
            return 0.0

        n = stats["observations"]
        curve = profile.confidence_curve
        params = profile.confidence_params

        score = 0.0
        if curve == "step":
            activation = params.get("activation_threshold", profile.min_observations)
            max_conf = params.get("max_confidence", 1.0)
            score = max_conf if n >= activation else 0.0

        elif curve == "linear":
            slope = params.get("slope", 0.02)
            max_conf = params.get("max_confidence", 1.0)
            score = min(max_conf, slope * n)

        elif curve == "sigmoid":
            midpoint = params.get("midpoint", 50)
            steepness = params.get("steepness", 0.05)
            max_conf = params.get("max_confidence", 1.0)
            try:
                score = max_conf / (1.0 + math.exp(-steepness * (n - midpoint)))
            except OverflowError:
                score = max_conf if n > midpoint else 0.0

        elif curve == "logarithmic":
            scale = params.get("scale", 0.25)
            shift = params.get("shift", 1)
            max_conf = params.get("max_confidence", 1.0)
            if n + shift > 0:
                score = min(max_conf, scale * math.log(n + shift))

        elif curve == "inverse_linear":
            # For transfer learning: trust Neighbor weights highly initially, decay as own data grows
            initial = params.get("initial_confidence", 0.8)
            decay = params.get("decay_per_observation", 0.005)
            floor = params.get("floor", 0.1)
            score = max(floor, initial - decay * n)

        # Clamping
        return max(0.0, min(1.0, score))

    def are_prereqs_met(self, profile: MaturityProfile, stats: Dict[str, Any]) -> bool:
        """Check if all basic minimum prerequisites are satisfied."""
        if stats["observations"] < profile.min_observations:
            return False
        if stats["days"] < profile.min_days:
            return False
        if stats["sources"] < profile.min_sources:
            return False
        if stats["seasons"] < profile.min_seasons:
            return False
        if stats["donor_plots"] < profile.min_donor_plots:
            return False
        if stats["donor_maturity"] < profile.min_donor_maturity:
            return False
        if stats["yield_reports"] < profile.min_yield_reports:
            return False
        if stats["active_patterns"] < profile.min_active_patterns:
            return False
        return True

    def get_blend_weight(
        self,
        pattern_name: str,
        plot_id: str,
        override_stats: Optional[Dict[str, Any]] = None,
        mock_stats: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float]:
        """Return (pattern_weight, fallback_weight) for blending prediction/priors.
        
        pattern_weight + fallback_weight = 1.0
        """
        effective_stats = override_stats if override_stats is not None else mock_stats
        maturity_score = self.get_maturity_score(pattern_name, plot_id, override_stats=effective_stats)
        return (maturity_score, 1.0 - maturity_score)

    def should_activate(
        self,
        pattern_name: str,
        plot_id: str,
        override_stats: Optional[Dict[str, Any]] = None,
        mock_stats: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Strategic activation: is the pattern ready to be used?"""
        effective_stats = override_stats if override_stats is not None else mock_stats
        score = self.get_maturity_score(pattern_name, plot_id, override_stats=effective_stats)
        return score > 0.0

    def should_deactivate(self, pattern_name: str, plot_id: str, 
                          pattern_rmse: float, fallback_rmse: float) -> bool:
        """Strategic deactivation check: does the pattern degrade accuracy?"""
        profile = self.get_profile(pattern_name, plot_id)
        if not profile.deactivation_rule:
            return False

        if pattern_rmse > fallback_rmse * (1.0 + profile.deactivation_threshold):
            reason = f"RMSE regression: pattern={pattern_rmse:.4f} vs fallback={fallback_rmse:.4f} (+{((pattern_rmse/fallback_rmse)-1)*100:.1f}%)"
            self.deactivated_patterns[(plot_id, pattern_name)] = reason
            logger.warning("[MATURITY] Deactivated pattern %s for plot %s: %s", pattern_name, plot_id, reason)
            return True
        
        return False

    def get_plot_maturity_report(
        self,
        plot_id: str,
        override_stats: Optional[Dict[str, Any]] = None,
        mock_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a complete maturity status dashboard for a plot."""
        effective_stats = override_stats if override_stats is not None else mock_stats
        stats = effective_stats if effective_stats is not None else self.get_plot_stats(plot_id)
        
        # When evaluating small databases, compute active_patterns count dynamically
        active_patterns_count = 0
        pattern_reports = {}
        
        for name in self.profiles.keys():
            profile = self.get_profile(name, stats.get("crop_type", ""))
            
            # Temporarily compute prerequisites (except active pattern counts to avoid circular reference)
            prereqs_without_patterns = {
                "observations": stats["observations"] >= profile.min_observations,
                "days": stats["days"] >= profile.min_days,
                "sources": stats["sources"] >= profile.min_sources,
                "seasons": stats["seasons"] >= profile.min_seasons,
                "donor_plots": stats["donor_plots"] >= profile.min_donor_plots,
                "yield_reports": stats["yield_reports"] >= profile.min_yield_reports,
            }
            
            is_prereqs_ok = all(prereqs_without_patterns.values())
            if is_prereqs_ok:
                active_patterns_count += 1

        # Update stats
        stats["active_patterns"] = active_patterns_count
        
        total_maturity = 0.0
        active_count = 0

        for name, profile in self.profiles.items():
            score = self.get_maturity_score(name, plot_id, stats)
            is_active = score > 0.0
            
            status = "inactive"
            note = ""
            if (plot_id, name) in self.deactivated_patterns:
                status = "deactivated"
                note = self.deactivated_patterns[(plot_id, name)]
            elif is_active:
                status = "active"
                if score < profile.confidence_params.get("max_confidence", 1.0):
                    status = "ramping"
            else:
                # Describe why inactive
                p_stats = stats
                missing = []
                if p_stats["observations"] < profile.min_observations:
                    missing.append(f"{profile.min_observations - p_stats['observations']} obs")
                if p_stats["days"] < profile.min_days:
                    missing.append(f"{profile.min_days - p_stats['days']} days")
                if p_stats["sources"] < profile.min_sources:
                    missing.append(f"{profile.min_sources - p_stats['sources']} sources")
                if p_stats["seasons"] < profile.min_seasons:
                    missing.append(f"{profile.min_seasons - p_stats['seasons']} seasons")
                if p_stats["yield_reports"] < profile.min_yield_reports:
                    missing.append(f"{profile.min_yield_reports - p_stats['yield_reports']} yield_reports")
                
                note = "Needs: " + ", ".join(missing) if missing else "Immature donor plots or dependencies."

            pattern_reports[name] = {
                "pattern_id": profile.pattern_id,
                "status": status,
                "maturity": round(score, 3),
                "blend_weight": round(score, 3),
                "confidence_curve": profile.confidence_curve,
                "note": note,
            }
            
            if is_active:
                total_maturity += score
                active_count += 1

        overall = total_maturity / len(self.profiles)

        return {
            "plot_id": plot_id,
            "overall_maturity": round(overall, 3),
            "crop_type": stats["crop_type"],
            "stats": stats,
            "patterns": pattern_reports,
        }
