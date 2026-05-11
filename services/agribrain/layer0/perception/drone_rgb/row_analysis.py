"""
Row Analysis Module.

Computes per-row continuity profiles, detects row breaks (stand gaps),
estimates stand density, and separates in-row vs inter-row weeds.

V2.0: Added FFT-based row detection (Phase D) for:
  - Dominant row azimuth from spectral energy peaks
  - Row spacing computed from peak spatial frequency + GSD
  - SNR-based confidence scoring
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import math

from layer0.perception.drone_rgb.schemas import RowBreak


# ============================================================================
# FFT-Based Row Detection (Phase D)
# ============================================================================

@dataclass
class FFTRowResult:
    """Result of FFT-based row detection."""
    azimuth_deg: float          # Dominant row direction (0–180°)
    spacing_cm: float           # Row spacing in cm (from GSD + frequency)
    confidence: float           # SNR-based confidence (0–1)
    peak_frequency: float       # Peak spatial frequency in cycles/block
    spectral_snr: float         # Signal-to-noise ratio of the peak


def _dft_1d(signal: List[float]) -> List[complex]:
    """Compute the 1D Discrete Fourier Transform (no numpy dependency).

    Uses the direct DFT formula: X[k] = Σ x[n] * e^{-j2πkn/N}
    O(N²) complexity — acceptable for the downsampled grid sizes (~40×40).
    """
    N = len(signal)
    result = []
    for k in range(N):
        re = 0.0
        im = 0.0
        for n in range(N):
            angle = -2.0 * math.pi * k * n / N
            re += signal[n] * math.cos(angle)
            im += signal[n] * math.sin(angle)
        result.append(complex(re, im))
    return result


def _power_spectrum_2d(grid: List[List[float]]) -> List[List[float]]:
    """Compute the 2D power spectrum via row-then-column 1D DFTs.

    Returns |DFT|² for each (fy, fx) frequency bin.
    """
    h = len(grid)
    w = len(grid[0]) if h > 0 else 0
    if h == 0 or w == 0:
        return []

    # Step 1: DFT along each row
    row_dft: List[List[complex]] = []
    for y in range(h):
        row_dft.append(_dft_1d(grid[y]))

    # Step 2: DFT along each column of the row-DFT result
    full_dft: List[List[complex]] = [[complex(0, 0)] * w for _ in range(h)]
    for x in range(w):
        col = [row_dft[y][x] for y in range(h)]
        col_dft = _dft_1d(col)
        for y in range(h):
            full_dft[y][x] = col_dft[y]

    # Step 3: Power spectrum
    power = [[0.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            c = full_dft[y][x]
            power[y][x] = c.real * c.real + c.imag * c.imag
    return power


def fft_detect_rows(
    canopy_map: List[List[float]],
    gsd_cm: float = 2.0,
    block_size: int = 1,
) -> FFTRowResult:
    """Detect row direction and spacing using 2D FFT spectral analysis.

    1. Compute 2D power spectrum of the canopy grid
    2. Zero the DC component and low-frequency halo
    3. Accumulate energy in polar (angle, radius) bins
    4. Find peak angle → row azimuth (perpendicular to dominant frequency)
    5. At peak angle, find peak radius → row spacing

    Args:
        canopy_map: 2D grid of canopy fraction values
        gsd_cm: Ground sample distance in cm (per original pixel)
        block_size: Number of original pixels per grid cell

    Returns:
        FFTRowResult with azimuth, spacing, confidence, and diagnostics
    """
    h = len(canopy_map)
    w = len(canopy_map[0]) if h > 0 else 0
    if h < 8 or w < 8:
        return FFTRowResult(
            azimuth_deg=0.0, spacing_cm=75.0,
            confidence=0.0, peak_frequency=0.0, spectral_snr=0.0,
        )

    # Subtract the mean to remove DC bias before FFT
    total = sum(canopy_map[y][x] for y in range(h) for x in range(w))
    mean_val = total / (h * w)
    centered = [
        [canopy_map[y][x] - mean_val for x in range(w)]
        for y in range(h)
    ]

    # Compute 2D power spectrum
    power = _power_spectrum_2d(centered)
    if not power:
        return FFTRowResult(
            azimuth_deg=0.0, spacing_cm=75.0,
            confidence=0.0, peak_frequency=0.0, spectral_snr=0.0,
        )

    # Zero the DC component and low-frequency halo (radius < 2)
    cy, cx = h // 2, w // 2
    for y in range(h):
        for x in range(w):
            # Map to centered frequency coordinates
            fy = y if y <= cy else y - h
            fx = x if x <= cx else x - w
            radius = math.sqrt(fy * fy + fx * fx)
            if radius < 2.0:
                power[y][x] = 0.0

    # Accumulate energy in polar bins (angle in 1° steps, radius bins)
    angle_bins = [0.0] * 180  # 0–179 degrees
    # Also track per-angle best radius
    angle_radius_energy: dict = {}  # angle_deg -> {radius_bin: energy}

    max_radius = min(cy, cx)
    for y in range(h):
        for x in range(w):
            fy = y if y <= cy else y - h
            fx = x if x <= cx else x - w
            radius = math.sqrt(fy * fy + fx * fx)
            if radius < 2.0 or radius > max_radius:
                continue

            angle_rad = math.atan2(fy, fx)
            angle_deg = math.degrees(angle_rad) % 180
            angle_bin = int(angle_deg) % 180

            energy = power[y][x]
            angle_bins[angle_bin] += energy

            radius_bin = int(round(radius))
            if angle_bin not in angle_radius_energy:
                angle_radius_energy[angle_bin] = {}
            are = angle_radius_energy[angle_bin]
            are[radius_bin] = are.get(radius_bin, 0.0) + energy

    # Find the peak angle (frequency direction)
    peak_angle = 0
    peak_energy = 0.0
    for i in range(180):
        if angle_bins[i] > peak_energy:
            peak_energy = angle_bins[i]
            peak_angle = i

    # Compute SNR: peak energy vs. median energy
    sorted_energies = sorted(angle_bins)
    median_energy = sorted_energies[len(sorted_energies) // 2]
    spectral_snr = (peak_energy / median_energy) if median_energy > 0 else 0.0

    # In image coordinates (x=East, y=South), the math angle of the frequency 
    # vector directly equals the compass azimuth of the rows. 
    # (The 90-deg perpendicular shift and 90-deg math-to-compass shift cancel out).
    row_azimuth = peak_angle

    # Find peak radius at the peak angle → row spacing
    radius_energies = angle_radius_energy.get(peak_angle, {})
    peak_radius = 4  # default
    peak_r_energy = 0.0
    for r_bin, r_energy in radius_energies.items():
        if r_bin >= 2 and r_energy > peak_r_energy:
            peak_r_energy = r_energy
            peak_radius = r_bin

    # Convert frequency to spatial period
    # frequency = peak_radius cycles / grid_size
    # period_blocks = grid_size / peak_radius
    grid_size = max(h, w)
    if peak_radius > 0:
        period_blocks = grid_size / peak_radius
        spacing_cm = period_blocks * block_size * gsd_cm
    else:
        spacing_cm = 75.0  # fallback

    # Confidence from SNR (sigmoid mapping)
    # SNR < 2 → low confidence, SNR > 5 → high confidence
    confidence = min(1.0, max(0.0, (spectral_snr - 1.5) / 4.0))

    # Boundary canonicalization (same as variance-based)
    if row_azimuth >= 177.0 or row_azimuth <= 3.0:
        row_azimuth = 0.0
    elif 87.0 <= row_azimuth <= 93.0:
        row_azimuth = 90.0

    # Round to 0.5°
    row_azimuth = round(row_azimuth * 2) / 2.0

    return FFTRowResult(
        azimuth_deg=row_azimuth,
        spacing_cm=round(spacing_cm, 1),
        confidence=confidence,
        peak_frequency=peak_radius / grid_size if grid_size > 0 else 0.0,
        spectral_snr=round(spectral_snr, 2),
    )


def _build_row_mask(
    grid_h: int, grid_w: int,
    row_azimuth_deg: float,
    row_spacing_px: float,
    row_width_px: float,
    block_size: int,
) -> List[List[bool]]:
    """Build a boolean mask identifying which grid cells fall within a row strip.
    
    Returns a grid_h x grid_w boolean grid.  True = inside a row strip.
    """
    theta = math.radians(row_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    half_width = row_width_px / (2.0 * block_size)
    spacing = row_spacing_px / block_size

    mask = [[False] * grid_w for _ in range(grid_h)]
    for gy in range(grid_h):
        for gx in range(grid_w):
            # Project block centre onto the row-normal axis
            rho = gx * cos_t + gy * sin_t
            dist = rho % spacing
            if dist > spacing / 2:
                dist = spacing - dist
            mask[gy][gx] = dist < half_width
    return mask


def compute_row_profiles(
    canopy_map: List[List[float]],
    row_azimuth_deg: float,
    row_spacing_px: float,
    block_size: int,
    row_width_px: float = 10,
) -> Tuple[List[float], int]:
    """Compute per-row continuity scores (0-1).
    
    Only blocks within the row strip width are considered, preventing
    inter-row soil from artificially lowering continuity scores.
    
    Returns:
        (continuity_scores, row_count)
    """
    if not canopy_map or not canopy_map[0]:
        return [], 0

    h, w = len(canopy_map), len(canopy_map[0])
    theta = math.radians(row_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    spacing = row_spacing_px / block_size
    if spacing < 1:
        spacing = 1
    half_width = row_width_px / (2.0 * block_size)

    # Assign each block to the nearest row index, but only if it's
    # within the row strip width
    row_bins: dict = {}  # row_index -> list of canopy values along that row
    for gy in range(h):
        for gx in range(w):
            rho = gx * cos_t + gy * sin_t
            row_idx = round(rho / spacing)
            dist = abs(rho - row_idx * spacing)
            if dist > half_width:
                continue  # Skip inter-row blocks
            if row_idx not in row_bins:
                row_bins[row_idx] = []
            row_bins[row_idx].append(canopy_map[gy][gx])

    # Compute continuity per row (fraction of in-strip blocks with canopy > threshold)
    threshold = 0.2
    scores = []
    for idx in sorted(row_bins.keys()):
        vals = row_bins[idx]
        if len(vals) < 3:
            continue
        green_count = sum(1 for v in vals if v > threshold)
        scores.append(green_count / len(vals))

    return scores, len(scores)


def detect_row_breaks(
    canopy_map: List[List[float]],
    row_azimuth_deg: float,
    row_spacing_px: float,
    row_width_px: float,
    block_size: int,
    gap_threshold: float = 0.15,
    min_gap_blocks: int = 2,
) -> List[RowBreak]:
    """Detect contiguous gap segments within each row.
    
    A gap is a run of >= min_gap_blocks consecutive blocks along a row
    where canopy fraction < gap_threshold.
    """
    if not canopy_map or not canopy_map[0]:
        return []

    h, w = len(canopy_map), len(canopy_map[0])
    theta = math.radians(row_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    spacing = row_spacing_px / block_size
    if spacing < 1:
        spacing = 1
    half_width = row_width_px / (2.0 * block_size)

    # Build per-row ordered block lists
    # For each block, compute (row_index, position_along_row, canopy_value)
    row_blocks: dict = {}  # row_index -> list of (along_pos, canopy_val)
    for gy in range(h):
        for gx in range(w):
            rho = gx * cos_t + gy * sin_t
            row_idx = round(rho / spacing)
            dist = rho - row_idx * spacing
            if abs(dist) > half_width:
                continue  # Not inside a row strip
            # Position along the row (perpendicular to the normal)
            along = -gx * sin_t + gy * cos_t
            if row_idx not in row_blocks:
                row_blocks[row_idx] = []
            row_blocks[row_idx].append((along, canopy_map[gy][gx]))

    breaks = []
    for row_idx in sorted(row_blocks.keys()):
        blocks = sorted(row_blocks[row_idx], key=lambda b: b[0])
        if len(blocks) < 3:
            continue
        # Scan for gap runs
        gap_start = None
        gap_count = 0
        for pos_idx, (along, val) in enumerate(blocks):
            if val < gap_threshold:
                if gap_start is None:
                    gap_start = pos_idx
                gap_count += 1
            else:
                if gap_start is not None and gap_count >= min_gap_blocks:
                    breaks.append(RowBreak(
                        row_index=row_idx,
                        start_block=gap_start,
                        end_block=gap_start + gap_count - 1,
                        gap_length_blocks=gap_count,
                    ))
                gap_start = None
                gap_count = 0
        # Handle gap at end of row
        if gap_start is not None and gap_count >= min_gap_blocks:
            breaks.append(RowBreak(
                row_index=row_idx,
                start_block=gap_start,
                end_block=gap_start + gap_count - 1,
                gap_length_blocks=gap_count,
            ))

    return breaks


def compute_stand_density(
    canopy_map: List[List[float]],
    row_azimuth_deg: float,
    row_spacing_px: float,
    row_width_px: float,
    block_size: int,
    presence_threshold: float = 0.3,
) -> List[float]:
    """Compute stand density (number of vegetation segments per row).
    
    A "stand" is a contiguous run of blocks with canopy > threshold within a row.
    Returns one value per detected row.
    """
    if not canopy_map or not canopy_map[0]:
        return []

    h, w = len(canopy_map), len(canopy_map[0])
    theta = math.radians(row_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    spacing = row_spacing_px / block_size
    if spacing < 1:
        spacing = 1
    half_width = row_width_px / (2.0 * block_size)

    row_blocks: dict = {}
    for gy in range(h):
        for gx in range(w):
            rho = gx * cos_t + gy * sin_t
            row_idx = round(rho / spacing)
            dist = rho - row_idx * spacing
            if abs(dist) > half_width:
                continue
            along = -gx * sin_t + gy * cos_t
            if row_idx not in row_blocks:
                row_blocks[row_idx] = []
            row_blocks[row_idx].append((along, canopy_map[gy][gx]))

    densities = []
    for row_idx in sorted(row_blocks.keys()):
        blocks = sorted(row_blocks[row_idx], key=lambda b: b[0])
        if len(blocks) < 2:
            densities.append(0.0)
            continue
        # Count distinct green runs
        segment_count = 0
        in_segment = False
        for _, val in blocks:
            if val > presence_threshold:
                if not in_segment:
                    segment_count += 1
                    in_segment = True
            else:
                in_segment = False
        densities.append(float(segment_count))

    return densities


def classify_weed_location(
    weed_map: List[List[float]],
    row_mask: List[List[bool]],
) -> Tuple[List[List[float]], List[List[float]], float, float]:
    """Split weed map into in-row and inter-row components.
    
    Returns:
        (in_row_weed_map, inter_row_weed_map, in_row_fraction, inter_row_fraction)
    """
    if not weed_map or not weed_map[0]:
        return [], [], 0.0, 0.0

    h, w = len(weed_map), len(weed_map[0])
    in_row = [[0.0] * w for _ in range(h)]
    inter_row = [[0.0] * w for _ in range(h)]

    in_row_total = 0.0
    inter_row_total = 0.0
    in_row_count = 0
    inter_row_count = 0

    for gy in range(h):
        for gx in range(w):
            val = weed_map[gy][gx]
            if row_mask[gy][gx]:
                in_row[gy][gx] = val
                in_row_total += val
                in_row_count += 1
            else:
                inter_row[gy][gx] = val
                inter_row_total += val
                inter_row_count += 1

    in_frac = in_row_total / in_row_count if in_row_count > 0 else 0.0
    inter_frac = inter_row_total / inter_row_count if inter_row_count > 0 else 0.0

    return in_row, inter_row, in_frac, inter_frac
