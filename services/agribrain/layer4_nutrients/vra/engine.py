"""
Layer 4.9: Variable Rate Application (VRA) Engine.

Generates zone-specific nutrient prescriptions from L2 spatial analysis.
Instead of one flat rate for the entire field, VRA adjusts rates per
management zone based on spectral deviation from the field mean.

Science:
  - Prescription mapping: zone NDVI Z-score → rate adjustment factor
  - Low-NDVI zones get higher rates (likely more deficient)
  - High-NDVI zones get lower rates (already sufficient)
  - Adjustment is bounded to prevent over/under-application
  - Minimum zone size constraint (equipment resolution)

Precision agriculture:
  - Typical VRA saves 15-25% fertilizer with equal or better yield
  - Requires: GPS-enabled spreader + prescription map
  - Zone delineation from L2 spatial clustering

References:
  - Mulla (2013): Twenty-five years of remote sensing in precision agriculture
  - Schepers et al. (2004): Comparison of corn leaf N concentration and
    chlorophyll meter readings, Comm. Soil Science & Plant Analysis
  - Lambert et al. (2006): Economic analysis of variable-rate N application
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from layer4_nutrients.schema import Nutrient, Prescription


@dataclass
class VRAZoneRate:
    """Rate prescription for one management zone."""
    zone_id: str = ""
    zone_area_ha: float = 0.0

    # Zone spectral metrics
    ndvi_mean: float = 0.0
    ndvi_z_score: float = 0.0  # Relative to field mean

    # Rate adjustment
    adjustment_factor: float = 1.0  # Multiplier on base rate
    adjusted_rate_kg_ha: float = 0.0  # Base × factor
    base_rate_kg_ha: float = 0.0

    # Confidence
    zone_confidence: float = 0.0
    pixel_count: int = 0

    notes: str = ""


@dataclass
class VRAOutput:
    """Variable Rate Application output for one nutrient."""
    nutrient: Nutrient = Nutrient.N
    base_rate_kg_ha: float = 0.0
    zone_rates: List[VRAZoneRate] = field(default_factory=list)

    # Field-level metrics
    total_product_kg: float = 0.0       # Total product needed
    product_savings_pct: float = 0.0    # Savings vs flat rate
    cv_across_zones: float = 0.0        # Coefficient of variation

    # Equipment constraints
    min_zone_ha: float = 0.5
    rate_resolution_kg_ha: float = 5.0  # Spreader rate step size

    notes: str = ""


class VRAEngine:
    """Generates zone-specific prescriptions from L2 spatial data.

    Architecture:
    1. Receives zone-level NDVI statistics from L2 spatial analysis
    2. Computes per-zone adjustment factor relative to field mean
    3. Applies equipment constraints (min zone size, rate resolution)
    4. Produces prescription map compatible with ISOBUS/SHP export
    """

    # VRA tuning parameters
    MAX_BOOST = 1.40   # Maximum rate increase for low-NDVI zones
    MAX_REDUCE = 0.60  # Maximum rate decrease for high-NDVI zones
    SENSITIVITY = 0.15 # Rate change per NDVI Z-score unit

    def __init__(
        self,
        min_zone_ha: float = 0.5,
        rate_resolution_kg_ha: float = 5.0,
    ):
        self.min_zone_ha = min_zone_ha
        self.rate_resolution = rate_resolution_kg_ha

    def generate_vra_prescription(
        self,
        nutrient: Nutrient,
        base_rate_kg_ha: float,
        zone_data: List[Dict[str, Any]],
        field_area_ha: float = 10.0,
    ) -> VRAOutput:
        """Generate variable-rate prescription.

        Args:
            nutrient: Target nutrient
            base_rate_kg_ha: Field-average recommended rate
            zone_data: List of zone dicts from L2 spatial analysis:
                [{zone_id, ndvi_mean, ndvi_std, area_ha, pixel_count}, ...]
            field_area_ha: Total field area
        """
        if not zone_data or base_rate_kg_ha <= 0:
            return VRAOutput(
                nutrient=nutrient,
                base_rate_kg_ha=base_rate_kg_ha,
                notes="No zone data or zero base rate — flat rate applied.",
            )

        # 1. Compute field-level NDVI mean (area-weighted)
        total_area = sum(z.get("area_ha", 1.0) for z in zone_data)
        if total_area <= 0:
            total_area = 1.0
        field_ndvi_mean = sum(
            z.get("ndvi_mean", 0.5) * z.get("area_ha", 1.0)
            for z in zone_data
        ) / total_area

        # Field NDVI stddev (for Z-score computation)
        field_ndvi_var = sum(
            z.get("area_ha", 1.0) * (z.get("ndvi_mean", 0.5) - field_ndvi_mean) ** 2
            for z in zone_data
        ) / total_area
        field_ndvi_std = max(0.01, field_ndvi_var ** 0.5)

        # 2. Compute zone-level adjustments
        zone_rates = []
        for z in zone_data:
            zone_id = z.get("zone_id", "Z0")
            zone_area = z.get("area_ha", 1.0)
            zone_ndvi = z.get("ndvi_mean", field_ndvi_mean)
            pixel_count = z.get("pixel_count", 0)

            # Skip zones below minimum size
            if zone_area < self.min_zone_ha:
                continue

            # Z-score relative to field mean
            z_score = (zone_ndvi - field_ndvi_mean) / field_ndvi_std

            # Adjustment factor: lower NDVI → higher rate
            # factor = 1.0 - sensitivity × z_score
            # Negative z_score (low NDVI) → factor > 1.0 (boost)
            # Positive z_score (high NDVI) → factor < 1.0 (reduce)
            factor = 1.0 - self.SENSITIVITY * z_score
            factor = max(self.MAX_REDUCE, min(self.MAX_BOOST, factor))

            # Apply rate
            adjusted_rate = base_rate_kg_ha * factor

            # Round to spreader resolution
            adjusted_rate = round(adjusted_rate / self.rate_resolution) * self.rate_resolution
            adjusted_rate = max(0.0, adjusted_rate)

            # Zone confidence (based on pixel count and NDVI consistency)
            zone_std = z.get("ndvi_std", 0.1)
            intra_zone_cv = zone_std / max(0.01, zone_ndvi)
            zone_conf = max(0.3, 1.0 - intra_zone_cv * 2.0)
            if pixel_count < 10:
                zone_conf *= 0.5  # Low pixel count = low confidence

            notes = ""
            if factor > 1.15:
                notes = f"Zone {zone_id}: LOW vigor — boosted rate (+{(factor-1)*100:.0f}%)"
            elif factor < 0.85:
                notes = f"Zone {zone_id}: HIGH vigor — reduced rate (-{(1-factor)*100:.0f}%)"

            zone_rates.append(VRAZoneRate(
                zone_id=zone_id,
                zone_area_ha=round(zone_area, 2),
                ndvi_mean=round(zone_ndvi, 3),
                ndvi_z_score=round(z_score, 2),
                adjustment_factor=round(factor, 3),
                adjusted_rate_kg_ha=round(adjusted_rate, 1),
                base_rate_kg_ha=round(base_rate_kg_ha, 1),
                zone_confidence=round(zone_conf, 2),
                pixel_count=pixel_count,
                notes=notes,
            ))

        # 3. Field-level metrics
        total_product = sum(zr.adjusted_rate_kg_ha * zr.zone_area_ha for zr in zone_rates)
        flat_product = base_rate_kg_ha * sum(zr.zone_area_ha for zr in zone_rates)
        savings = (1.0 - total_product / max(1.0, flat_product)) * 100.0 if flat_product > 0 else 0.0

        # CV across zones
        rates = [zr.adjusted_rate_kg_ha for zr in zone_rates]
        if rates:
            rate_mean = sum(rates) / len(rates)
            rate_var = sum((r - rate_mean) ** 2 for r in rates) / len(rates)
            cv = (rate_var ** 0.5) / max(0.01, rate_mean)
        else:
            cv = 0.0

        return VRAOutput(
            nutrient=nutrient,
            base_rate_kg_ha=round(base_rate_kg_ha, 1),
            zone_rates=zone_rates,
            total_product_kg=round(total_product, 1),
            product_savings_pct=round(max(0, savings), 1),
            cv_across_zones=round(cv, 3),
            min_zone_ha=self.min_zone_ha,
            rate_resolution_kg_ha=self.rate_resolution,
            notes=f"VRA prescription: {len(zone_rates)} zones, "
                  f"savings: {savings:.1f}% vs flat rate.",
        )
