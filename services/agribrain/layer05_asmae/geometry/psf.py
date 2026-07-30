"""
ASMAE Point Spread Function / Modulation Transfer Function.

Models sensor-specific spatial blur (PSF) for each observation:
  - S2 10m bands: σ ≈ 5.0m (Gaussian FWHM ~ 11.8m)
  - S2 20m bands: σ ≈ 10.0m (Gaussian FWHM ~ 23.5m)
  - S1 SAR:       σ ≈ 7.5m (Gaussian approximation of speckle spread)

The PSF determines how much a micro-zone contributes to a pixel.
Two micro-zones that are spatially adjacent but spectrally distinct
will be blurred together by the PSF — the H_t operator accounts for
this by weighting overlap contributions with PSF kernel values.

Pure-Python implementation. No numpy/scipy dependency for the kernel
itself (scipy.sparse is used only in the final operator assembly).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# ── Sensor PSF Parameters ───────────────────────────────────────────────────
# Gaussian sigma in meters for each band group.
# Based on Sentinel-2 MTF characterization (Gascon et al. 2017).

S2_PSF_SIGMA_M = {
    "B02": 5.0, "B03": 5.0, "B04": 5.0, "B08": 5.0,      # 10m bands
    "B05": 10.0, "B06": 10.0, "B07": 10.0, "B8A": 10.0,    # 20m bands
    "B11": 10.0, "B12": 10.0,                                # 20m SWIR
    "B01": 30.0, "B09": 30.0, "B10": 30.0,                  # 60m bands
}

S1_PSF_SIGMA_M = {
    "VV": 7.5,
    "VH": 7.5,
}

S5P_PSF_SIGMA_M = {
    "sif": 1750.0,  # ~3.5km / 2
}


@dataclass
class PSFModel:
    """Gaussian PSF model for a specific sensor/band combination.

    Attributes:
        sensor: Sensor identifier (S2, S1, S5P).
        band: Band name.
        sigma_m: Gaussian sigma in meters.
        truncation_radius: Number of sigmas before truncation (default 3).
    """
    sensor: str
    band: str
    sigma_m: float
    truncation_radius: float = 3.0

    @property
    def fwhm_m(self) -> float:
        """Full Width at Half Maximum in meters."""
        return self.sigma_m * 2.0 * math.sqrt(2.0 * math.log(2.0))

    @property
    def effective_radius_m(self) -> float:
        """Effective support radius = sigma * truncation_radius."""
        return self.sigma_m * self.truncation_radius

    def evaluate(self, distance_m: float) -> float:
        """Evaluate Gaussian PSF at a given distance from center.

        Returns normalized kernel value in [0, 1].
        """
        if self.sigma_m <= 0:
            # Delta PSF — perfect point source
            return 1.0 if distance_m == 0.0 else 0.0

        if abs(distance_m) > self.effective_radius_m:
            return 0.0

        return math.exp(-0.5 * (distance_m / self.sigma_m) ** 2)

    def evaluate_2d(self, dx_m: float, dy_m: float) -> float:
        """Evaluate 2D isotropic Gaussian PSF at (dx, dy) offset.

        Separable: G(dx, dy) = G(dx) * G(dy).
        """
        dist = math.sqrt(dx_m * dx_m + dy_m * dy_m)
        return self.evaluate(dist)

    def overlap_weight(
        self,
        pixel_center_x: float,
        pixel_center_y: float,
        zone_center_x: float,
        zone_center_y: float,
        zone_size_m: float,
    ) -> float:
        """Compute PSF-weighted overlap between a pixel and a micro-zone.

        Uses the distance between pixel center and zone center,
        weighted by the PSF kernel. The zone's fractional area overlap
        is handled separately by the operator builder.

        Returns:
            PSF weight in [0, 1]. This is multiplied by the geometric
            overlap fraction to get the final H_t entry.
        """
        dx = pixel_center_x - zone_center_x
        dy = pixel_center_y - zone_center_y
        return self.evaluate_2d(dx, dy)


def get_psf_model(
    sensor: str,
    band: str = "",
    custom_sigma_m: Optional[float] = None,
) -> PSFModel:
    """Get the appropriate PSF model for a sensor/band.

    Args:
        sensor: "S2", "S1", "S5P", or "EXTERNAL".
        band: Optional band name for band-specific PSF.
        custom_sigma_m: Override sigma if provided.

    Returns:
        PSFModel instance.
    """
    if custom_sigma_m is not None:
        return PSFModel(sensor=sensor, band=band, sigma_m=custom_sigma_m)

    if sensor == "S2":
        sigma = S2_PSF_SIGMA_M.get(band, 5.0)  # Default to 10m-band PSF
    elif sensor == "S1":
        sigma = S1_PSF_SIGMA_M.get(band, 7.5)
    elif sensor == "S5P":
        sigma = S5P_PSF_SIGMA_M.get(band, 1750.0)
    elif sensor == "EXTERNAL":
        sigma = 0.5  # External imagery assumed sharp
    else:
        sigma = 5.0  # Fallback

    return PSFModel(sensor=sensor, band=band, sigma_m=sigma)


def get_default_psf_sigma(sensor: str) -> float:
    """Get default PSF sigma for a sensor's primary band group."""
    defaults = {
        "S2": 5.0,    # 10m bands
        "S1": 7.5,
        "S5P": 1750.0,
        "EXTERNAL": 0.5,
    }
    return defaults.get(sensor, 5.0)


# ── SAR Speckle Noise Model ─────────────────────────────────────────────────

@dataclass
class SARNoiseModel:
    """SAR-specific noise model for Sentinel-1 GRD.

    Speckle in SAR is multiplicative noise. The effective number of looks
    (ENL) determines the signal-to-noise ratio.

    For GRD products:
      - IW mode, ENL ≈ 4.4 (VV), 4.2 (VH)
      - Thermal noise floor ≈ -22 dB (VV), -25 dB (VH)
    """
    enl_vv: float = 4.4
    enl_vh: float = 4.2
    thermal_noise_vv_db: float = -22.0
    thermal_noise_vh_db: float = -25.0

    def speckle_std(self, polarization: str = "VV") -> float:
        """Standard deviation of speckle noise (multiplicative).

        For a Gamma-distributed speckle with ENL looks:
            std = 1 / sqrt(ENL)
        """
        enl = self.enl_vv if polarization.upper() == "VV" else self.enl_vh
        return 1.0 / math.sqrt(enl)

    def noise_equivalent_sigma0(self, polarization: str = "VV") -> float:
        """Noise equivalent sigma-zero (NESZ) in linear scale."""
        db = (self.thermal_noise_vv_db
              if polarization.upper() == "VV"
              else self.thermal_noise_vh_db)
        return 10.0 ** (db / 10.0)
