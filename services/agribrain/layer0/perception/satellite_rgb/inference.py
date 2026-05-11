"""
Satellite RGB Structural Inference — V1

Extracts plot-scale structural intelligence from a georeferenced RGB image.
This is the perception core. All outputs carry sigma and confidence.

V1 scope:
  - Vegetation / soil segmentation (green-index thresholding)
  - Anomaly detection (spatial heterogeneity analysis)
  - Coarse canopy summary (density class, phenology hint)
  - Confidence map

What this does NOT do:
  - NDVI computation (no NIR band)
  - Disease type classification
  - Water content indexing
  - Fertilizer recommendation
  - Row detection (deferred to V1.5)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math

from layer0.perception.satellite_rgb.preprocess import PlotImageContext
from layer0.perception.common.contracts import PerceptionVariable, PerceptionArtifact, ZoneOutput
from layer0.perception.common.base_types import FeasibilityGate

try:
    from layer0.perception.satellite_rgb.llm_vision import LLMVisionResult, analyze_tile
except ImportError:
    LLMVisionResult = None
    analyze_tile = None


# ============================================================================
# Inference Output
# ============================================================================

@dataclass
class SatelliteRGBInferenceResult:
    """
    Structured output from satellite RGB structural inference.
    
    All values carry sigma (uncertainty) estimates.
    No raw ML outputs — everything is wrapped in confidence.
    """
    # Plot-level observations
    vegetation_fraction: float = 0.0
    vegetation_sigma: float = 0.10
    bare_soil_fraction: float = 0.0
    bare_soil_sigma: float = 0.10
    anomaly_fraction: float = 0.0
    anomaly_sigma: float = 0.20
    
    # Canopy summary
    canopy_density_class: str = "sparse"  # "bare", "sparse", "moderate", "dense"
    coarse_phenology_stage: float = 0.0    # 0=dormant -> 4=senescence
    phenology_sigma: float = 0.80          # Very uncertain from RGB alone

    # Boundary contamination
    boundary_contamination_score: float = 0.0

    # Confidence
    overall_confidence: float = 0.5

    # Zone-level outputs (zone-capable from day one)
    zone_results: List[ZoneInferenceResult] = field(default_factory=list)

    # Artifacts
    vegetation_mask: Optional[List[List[float]]] = None
    anomaly_heatmap: Optional[List[List[float]]] = None
    confidence_map: Optional[List[List[float]]] = None

    # LLM Vision overlay (parallel path)
    llm_vision: Optional[Any] = None  # LLMVisionResult when available

    # Feasibility gates
    feasibility_gates: List[FeasibilityGate] = field(default_factory=list)


@dataclass
class ZoneInferenceResult:
    """Per-zone inference output."""
    zone_id: str = ""
    canopy_fraction: float = 0.0
    anomaly_score: float = 0.0
    structural_uniformity: float = 0.0
    confidence: float = 0.5


# ============================================================================
# Inference Engine
# ============================================================================

class SatelliteRGBInference:
    """
    Structural inference from preprocessed satellite RGB imagery.
    
    V1 implements:
      - Excess Green segmentation for vegetation vs bare soil
      - Spatial heterogeneity analysis for anomaly detection
      - Green-ratio-based coarse phenology estimation
      - Zone aggregation
    
    All outputs have sigma estimates — no bare numbers.
    
    Usage:
        inference = SatelliteRGBInference()
        result = inference.run(plot_context, qa_result)
    """

    # Vegetation detection thresholds
    VEG_GREEN_RATIO_THRESHOLD = 0.34  # Above this = likely vegetation
    SOIL_GREEN_RATIO_LOW = 0.28       # Below this = likely bare soil
    ANOMALY_STD_MULTIPLIER = 2.5      # Pixels > mean + N*std = anomaly

    def run(
        self,
        ctx: PlotImageContext,
        resolution_m: float = 10.0,
        n_zones: int = 4,
        image_bytes: Optional[bytes] = None,
    ) -> SatelliteRGBInferenceResult:
        """
        Run full structural inference pipeline.
        
        Args:
            ctx: preprocessed PlotImageContext
            resolution_m: ground resolution in meters
            n_zones: number of zones for zone-level aggregation
        
        Returns:
            SatelliteRGBInferenceResult with all observations.
        """
        result = SatelliteRGBInferenceResult()

        if ctx.inside_pixels == 0:
            result.overall_confidence = 0.0
            return result

        # --- Stage 3A: Vegetation / soil segmentation ---
        veg_mask, soil_mask = self._segment_vegetation(ctx)
        result.vegetation_mask = veg_mask

        veg_fraction, soil_fraction = self._compute_fractions(
            veg_mask, soil_mask, ctx.masks.inside_mask
        )
        result.vegetation_fraction = veg_fraction
        result.bare_soil_fraction = soil_fraction

        # Sigma depends on segmentation clarity
        ambiguous_fraction = max(0, 1.0 - veg_fraction - soil_fraction)
        result.vegetation_sigma = 0.08 + ambiguous_fraction * 0.15
        result.bare_soil_sigma = 0.08 + ambiguous_fraction * 0.15

        # --- Stage 3B: Anomaly detection ---
        anomaly_map = self._detect_anomalies(ctx)
        result.anomaly_heatmap = anomaly_map

        anomaly_fraction = self._compute_anomaly_fraction(
            anomaly_map, ctx.masks.inside_mask
        )
        result.anomaly_fraction = anomaly_fraction
        result.anomaly_sigma = 0.15 + (1.0 - result.overall_confidence) * 0.10

        # --- Stage 3D: Canopy summary ---
        result.canopy_density_class = self._classify_density(veg_fraction)
        result.coarse_phenology_stage = self._estimate_phenology(ctx, veg_fraction)
        result.phenology_sigma = 0.80  # Very uncertain from RGB alone

        # --- Boundary contamination ---
        result.boundary_contamination_score = ctx.masks.boundary_fraction

        # --- Confidence map ---
        result.confidence_map = self._build_confidence_map(
            ctx, veg_mask, anomaly_map
        )

        # --- Overall confidence ---
        result.overall_confidence = self._compute_overall_confidence(
            ctx, veg_fraction, anomaly_fraction, ambiguous_fraction
        )
        result.anomaly_sigma = 0.15 + (1.0 - result.overall_confidence) * 0.10

        # --- Zone aggregation ---
        result.zone_results = self._aggregate_zones(
            ctx, veg_mask, anomaly_map, n_zones
        )

        # --- Feasibility gates ---
        result.feasibility_gates = [
            FeasibilityGate.block("row_direction", "Deferred to V1.5"),
            FeasibilityGate.block("row_spacing", "Deferred to V1.5"),
        ]

        # --- LLM Vision Overlay (Parallel Path) ---
        if image_bytes and analyze_tile is not None:
            try:
                llm_result = analyze_tile(image_bytes)
                if llm_result and llm_result.confidence > 0.5:
                    result.llm_vision = llm_result
                    llm_veg = llm_result.vegetation_pct / 100.0
                    llm_soil = llm_result.bare_soil_pct / 100.0
                    
                    # Weighted merge: 60% traditional CV + 40% LLM vision
                    w_cv = 0.6
                    w_llm = 0.4
                    if llm_result.confidence > 0.7:
                        w_cv = 0.5
                        w_llm = 0.5
                    
                    result.vegetation_fraction = w_cv * veg_fraction + w_llm * llm_veg
                    result.bare_soil_fraction = w_cv * soil_fraction + w_llm * llm_soil
                    
                    # Override density class if LLM is confident
                    result.canopy_density_class = self._classify_density(result.vegetation_fraction)
                    
                    # Override phenology from LLM when confident
                    stage_map = {
                        "bare_soil": 0.0, "early_emergence": 0.5,
                        "vegetative": 1.5, "reproductive": 2.0, "senescence": 3.5,
                    }
                    if llm_result.emergence_stage in stage_map and llm_result.confidence > 0.6:
                        llm_pheno = stage_map[llm_result.emergence_stage]
                        result.coarse_phenology_stage = w_cv * result.coarse_phenology_stage + w_llm * llm_pheno
                    
                    print(f"[LLM_VISION] Merged: veg={result.vegetation_fraction:.2f}, "
                          f"soil={result.bare_soil_fraction:.2f}, "
                          f"density={result.canopy_density_class}")
            except Exception as e:
                print(f"[LLM_VISION] Overlay failed (non-blocking): {e}")

        return result

    # ================================================================
    # Stage 3A: Vegetation / Soil Segmentation
    # ================================================================

    def _segment_vegetation(
        self, ctx: PlotImageContext
    ) -> Tuple[List[List[float]], List[List[float]]]:
        """
        Segment pixels into vegetation (1.0) vs non-vegetation (0.0)
        and bare soil (1.0) vs non-soil (0.0).
        
        Uses Excess Green Index: ExG = 2G - R - B (normalized)
        This is the most reliable first feature from RGB.
        
        ExG > 0  -> green dominant -> vegetation
        ExG < 0  -> red/blue dominant -> soil or non-vegetation
        """
        h, w = ctx.height, ctx.width
        veg_mask = [[0.0] * w for _ in range(h)]
        soil_mask = [[0.0] * w for _ in range(h)]

        for r in range(h):
            for c in range(w):
                if r >= len(ctx.masks.inside_mask) or c >= len(ctx.masks.inside_mask[r]):
                    continue
                if ctx.masks.inside_mask[r][c] < 0.5:
                    continue

                red = ctx.red[r][c] if r < len(ctx.red) and c < len(ctx.red[r]) else 0.0
                green = ctx.green[r][c] if r < len(ctx.green) and c < len(ctx.green[r]) else 0.0
                blue = ctx.blue[r][c] if r < len(ctx.blue) and c < len(ctx.blue[r]) else 0.0

                total = red + green + blue
                if total < 0.01:
                    soil_mask[r][c] = 1.0
                    continue

                green_ratio = green / total
                # Excess Green Index: 2G - R - B, normalized by total
                exg = (2.0 * green - red - blue) / total

                # Brightness floor: very dark pixels cannot be vegetation
                # (dark soil with noise produces random green-dominant ratios)
                if total < 0.30:
                    soil_mask[r][c] = 1.0
                    continue

                # Vegetation: green dominant with sufficient absolute green
                # Requires ExG > 0, high green_ratio, AND meaningful green intensity
                if exg > 0.05 and green_ratio >= 0.36 and green > 0.25:
                    veg_mask[r][c] = 1.0
                # Bare soil: red/brown dominant (ExG < 0 OR very low green_ratio)
                elif exg < -0.02 or green_ratio <= 0.30:
                    soil_mask[r][c] = 1.0
                # Ambiguous band: classify as soil (lean conservative)
                else:
                    soil_mask[r][c] = 1.0

        return veg_mask, soil_mask

    def _compute_fractions(
        self,
        veg_mask: List[List[float]],
        soil_mask: List[List[float]],
        inside_mask: List[List[float]],
    ) -> Tuple[float, float]:
        """Compute fraction of inside pixels that are vegetation / soil."""
        veg_count = 0
        soil_count = 0
        inside_count = 0

        for r in range(len(inside_mask)):
            for c in range(len(inside_mask[r])):
                if inside_mask[r][c] > 0.5:
                    inside_count += 1
                    if r < len(veg_mask) and c < len(veg_mask[r]) and veg_mask[r][c] > 0.5:
                        veg_count += 1
                    if r < len(soil_mask) and c < len(soil_mask[r]) and soil_mask[r][c] > 0.5:
                        soil_count += 1

        if inside_count == 0:
            return 0.0, 0.0

        return veg_count / inside_count, soil_count / inside_count

    # ================================================================
    # Stage 3B: Anomaly Detection
    # ================================================================

    def _detect_anomalies(self, ctx: PlotImageContext) -> List[List[float]]:
        """
        Detect structural anomalies via spatial heterogeneity.
        
        Anomaly = pixel deviates significantly from plot mean.
        Uses green channel variance as the primary signal.
        """
        h, w = ctx.height, ctx.width
        anomaly_map = [[0.0] * w for _ in range(h)]

        mean_g = ctx.mean_green
        std_g = max(ctx.std_green, 0.01)
        threshold = self.ANOMALY_STD_MULTIPLIER * std_g

        for r in range(h):
            for c in range(w):
                if r >= len(ctx.masks.inside_mask) or c >= len(ctx.masks.inside_mask[r]):
                    continue
                if ctx.masks.inside_mask[r][c] < 0.5:
                    continue

                green = ctx.green[r][c] if r < len(ctx.green) and c < len(ctx.green[r]) else 0.0
                deviation = abs(green - mean_g)

                if deviation > threshold:
                    # Normalize anomaly score 0–1
                    anomaly_map[r][c] = min(1.0, deviation / (threshold * 2.0))

        return anomaly_map

    def _compute_anomaly_fraction(
        self,
        anomaly_map: List[List[float]],
        inside_mask: List[List[float]],
    ) -> float:
        """Fraction of inside pixels with anomaly score > 0."""
        anomaly_count = 0
        inside_count = 0

        for r in range(len(inside_mask)):
            for c in range(len(inside_mask[r])):
                if inside_mask[r][c] > 0.5:
                    inside_count += 1
                    if r < len(anomaly_map) and c < len(anomaly_map[r]):
                        if anomaly_map[r][c] > 0.1:
                            anomaly_count += 1

        return anomaly_count / max(inside_count, 1)

    # ================================================================
    # Stage 3D: Canopy Summary
    # ================================================================

    def _classify_density(self, vegetation_fraction: float) -> str:
        """Classify canopy density from vegetation fraction.
        
        Thresholds tuned against benchmark confusion matrix:
          bare < 0.08 < sparse < 0.40 < moderate < 0.75 < dense
        """
        if vegetation_fraction < 0.08:
            return "bare"
        elif vegetation_fraction < 0.40:
            return "sparse"
        elif vegetation_fraction < 0.75:
            return "moderate"
        else:
            return "dense"

    def _estimate_phenology(
        self, ctx: PlotImageContext, veg_fraction: float
    ) -> float:
        """Multi-feature phenology estimation from RGB color + veg coverage.
        
        Uses veg_fraction, green_ratio, red/green ratio, and brightness
        together instead of green_ratio alone. Very uncertain (sigma=0.8).
        
        Stage mapping:
          0.0 = dormant/bare
          0.5 = early emergence
          1.5 = strong vegetative
          2.0 = flowering/mid-season
          2.5 = stressed/late vegetative
          3.0 = ripening (yellowing)
          3.5 = senescence
          4.0 = post-harvest/stubble
        """
        gr = ctx.green_ratio
        brightness = (ctx.mean_red + ctx.mean_green + ctx.mean_blue) / 3.0
        rg_ratio = ctx.mean_red / max(ctx.mean_green, 0.001)
        
        # --- Stage 1: High vegetation, green dominant -> vegetative/flowering ---
        if veg_fraction > 0.75 and gr > 0.40:
            # Dense green canopy
            if rg_ratio < 0.35:
                return 1.5  # Strong vegetative (very green-dominant)
            else:
                return 2.0  # Flowering / mid-season (slightly less green)
        
        # --- Stage 2: Moderate vegetation, green present -> mid-season ---
        if 0.40 <= veg_fraction <= 0.75:
            if gr > 0.40:
                return 1.5  # Vegetative with moderate coverage
            elif gr > 0.33 and rg_ratio > 1.1:
                return 3.0  # Ripening (yellowing — red approaching green)
            elif rg_ratio < 0.50:
                return 0.5  # Early/transitional (green but sparse)
            else:
                return 2.5  # Stressed / late vegetative
        
        # --- Stage 3: Low vegetation (< 0.40) -> early, senescence, or bare ---
        if veg_fraction < 0.08:
            return 0.0  # Almost no vegetation -> dormant/bare
        
        # Low-moderate veg (0.08 - 0.40): could be emergence or senescence
        # Key discriminator: senescence/post-harvest has high r/g ratio (browning),
        # emergence has lower r/g.
        if rg_ratio >= 1.25 and brightness > 0.25:
            if veg_fraction < 0.15:
                # Almost no green left but what remains is browning -> senescence
                return 3.5
            elif veg_fraction < 0.25:
                # Some green on brown base — could be dormant or late senescence.
                # Lower brightness -> more likely dormant (winter field)
                if brightness < 0.30:
                    return 0.0  # Dormant
                else:
                    return 3.5  # Late senescence
            elif gr > 0.33:
                return 4.0  # Post-harvest stubble (significant green remaining)
            else:
                return 3.5  # Late senescence
        
        # Low veg with moderate r/g -> early emergence
        return 0.5  # Early stage (sparse seedlings on soil)


    # ================================================================
    # Confidence and zone aggregation
    # ================================================================

    def _build_confidence_map(
        self,
        ctx: PlotImageContext,
        veg_mask: List[List[float]],
        anomaly_map: List[List[float]],
    ) -> List[List[float]]:
        """
        Per-pixel confidence: higher where segmentation is clear,
        lower at edges and ambiguous pixels.
        """
        h, w = ctx.height, ctx.width
        conf = [[0.0] * w for _ in range(h)]

        for r in range(h):
            for c in range(w):
                if r >= len(ctx.masks.inside_mask) or c >= len(ctx.masks.inside_mask[r]):
                    continue
                if ctx.masks.inside_mask[r][c] < 0.5:
                    continue

                # Base confidence from being inside
                base = 0.7

                # Edge penalty
                if r < len(ctx.masks.edge_mask) and c < len(ctx.masks.edge_mask[r]):
                    if ctx.masks.edge_mask[r][c] > 0.5:
                        base *= 0.6  # Boundary reduces confidence

                # Clear classification boost
                is_veg = r < len(veg_mask) and c < len(veg_mask[r]) and veg_mask[r][c] > 0.5
                if is_veg:
                    base *= 1.1  # Clear vegetation = higher confidence

                conf[r][c] = min(1.0, base)

        return conf

    def _compute_overall_confidence(
        self,
        ctx: PlotImageContext,
        veg_fraction: float,
        anomaly_fraction: float,
        ambiguous_fraction: float,
    ) -> float:
        """
        Overall inference confidence.
        
        Higher when:
          - Clear segmentation (low ambiguous fraction)
          - Good pixel count
          - Low boundary contamination
        """
        conf = 0.7  # Base

        # Penalty for ambiguity
        conf -= ambiguous_fraction * 0.3

        # Penalty for low pixel count
        if ctx.inside_pixels < 100:
            conf *= 0.6
        elif ctx.inside_pixels < 50:
            conf *= 0.3

        # Penalty for high boundary contamination
        conf -= ctx.masks.boundary_fraction * 0.2

        return max(0.1, min(1.0, conf))

    def _aggregate_zones(
        self,
        ctx: PlotImageContext,
        veg_mask: List[List[float]],
        anomaly_map: List[List[float]],
        n_zones: int,
    ) -> List[ZoneInferenceResult]:
        """
        Aggregate inference to zones by splitting the plot into
        horizontal bands (simple V1 zoning).
        
        In production, zones would come from the PlotGrid.
        """
        if ctx.height < n_zones or ctx.inside_pixels < n_zones * 4:
            # Too small to zone — return single plot zone
            return [ZoneInferenceResult(
                zone_id="plot",
                canopy_fraction=self._compute_fractions(
                    veg_mask, [[0.0]], ctx.masks.inside_mask
                )[0],
                anomaly_score=self._compute_anomaly_fraction(
                    anomaly_map, ctx.masks.inside_mask
                ),
                structural_uniformity=1.0 - ctx.std_green / max(ctx.mean_green, 0.01),
                confidence=0.5,
            )]

        zones = []
        zone_height = ctx.height // n_zones

        for z in range(n_zones):
            r_start = z * zone_height
            r_end = (z + 1) * zone_height if z < n_zones - 1 else ctx.height

            zone_veg = 0
            zone_anomaly = 0
            zone_inside = 0
            zone_green_vals = []

            for r in range(r_start, r_end):
                for c in range(ctx.width):
                    if r < len(ctx.masks.inside_mask) and c < len(ctx.masks.inside_mask[r]):
                        if ctx.masks.inside_mask[r][c] > 0.5:
                            zone_inside += 1
                            if r < len(veg_mask) and c < len(veg_mask[r]) and veg_mask[r][c] > 0.5:
                                zone_veg += 1
                            if r < len(anomaly_map) and c < len(anomaly_map[r]) and anomaly_map[r][c] > 0.1:
                                zone_anomaly += 1
                            if r < len(ctx.green) and c < len(ctx.green[r]):
                                zone_green_vals.append(ctx.green[r][c])

            canopy_frac = zone_veg / max(zone_inside, 1)
            anomaly_score = zone_anomaly / max(zone_inside, 1)

            # Structural uniformity: 1 - CV of green channel in zone
            if zone_green_vals and len(zone_green_vals) > 1:
                mean_g = sum(zone_green_vals) / len(zone_green_vals)
                std_g = math.sqrt(sum((x - mean_g) ** 2 for x in zone_green_vals) / len(zone_green_vals))
                uniformity = max(0.0, 1.0 - std_g / max(mean_g, 0.01))
            else:
                uniformity = 0.5

            zones.append(ZoneInferenceResult(
                zone_id=f"zone_{z}",
                canopy_fraction=round(canopy_frac, 3),
                anomaly_score=round(anomaly_score, 3),
                structural_uniformity=round(uniformity, 3),
                confidence=0.5 if zone_inside > 10 else 0.2,
            ))

        return zones
