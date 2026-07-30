# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image, ImageDraw
from typing import Any, Dict, Optional, Tuple

def get_var(bus: Any, key: str, default_val: float = 0.0) -> np.ndarray:
    """
    Retrieves a scientific grid variable by key from the ASMAEFeatureBus
    or its underlying feature pack fallback, ensuring fallback safety.
    """
    if hasattr(bus, key):
        val = getattr(bus, key)
        if val is not None:
            return np.asarray(val, dtype=np.float32)

    alias_map = {
        "salinity": "salinity_stress",
        "thermal": "thermal_stress",
        "biotic_risk": "biotic_confounder_risk",
        "bare_soil": "bare_soil_fraction",
        "retro_score": "retrovalidation_score",
    }
    alt_key = alias_map.get(key)
    if alt_key and hasattr(bus, alt_key):
        val = getattr(bus, alt_key)
        if val is not None:
            return np.asarray(val, dtype=np.float32)

    # Check underlying feature pack if available
    fpack = getattr(bus, "asmae_feature_pack", None)
    if fpack:
        for cat in ("state", "diagnostics", "resolution"):
            grid = fpack.get(cat, {}).get(key) or fpack.get(cat, {}).get(alt_key or "")
            if grid is not None:
                return np.asarray(grid, dtype=np.float32)

    # Retrieve shape from vigor or default to 10x10
    shape = (10, 10)
    if hasattr(bus, "vigor") and bus.vigor is not None:
        shape = bus.vigor.shape
    return np.full(shape, default_val, dtype=np.float32)

def render_asmae_diagnostic_map(
    bus: Any,
    draw_hud: bool = False,
    cert_level: str = "none"
) -> Dict[str, Any]:
    """
    Renders a complete multi-spectral scientific representation from the ASMAEFeatureBus:
      - Red Channel: Vigor modulated by Salinity + Thermal stress + Bare Soil.
      - Green Channel: LAI + Chlorophyll + Phenology.
      - Blue Channel: Canopy Water + Root Zone Water + Surface Wetness.
      - Alpha / Intensity: Governed by uncertainty and BMA disagreement (high disagreement = dotted).
      - HUD overlay rendering.
    """
    vigor = get_var(bus, "vigor", 0.5)
    salinity = get_var(bus, "salinity", 0.0)
    thermal = get_var(bus, "thermal", 0.0)
    bare_soil = get_var(bus, "bare_soil", 0.0)

    lai = get_var(bus, "lai", 1.0)
    chlorophyll = get_var(bus, "chlorophyll", 20.0)
    phenology = get_var(bus, "phenology_progress", 0.5)

    canopy_water = get_var(bus, "canopy_water", 0.1)
    root_zone_water = get_var(bus, "root_zone_water", 0.2)
    surface_wetness = get_var(bus, "surface_wetness_event", 0.0)

    uncertainty = get_var(bus, "uncertainty", 0.15)
    bma_disagreement = get_var(bus, "bma_disagreement", 0.1)

    # Normalize inputs
    lai_norm = np.clip(lai / 8.0, 0.0, 1.0)
    chlor_norm = np.clip(chlorophyll / 80.0 if np.nanmax(chlorophyll) > 1.0 else chlorophyll, 0.0, 1.0)

    # Color bands calculation
    red = np.clip(vigor * (1.0 - 0.25 * salinity - 0.25 * thermal) + 0.3 * bare_soil, 0.0, 1.0)
    green = np.clip(lai_norm * 0.4 + chlor_norm * 0.4 + phenology * 0.2, 0.0, 1.0)
    blue = np.clip(canopy_water * 0.4 + root_zone_water * 0.4 + surface_wetness * 0.2, 0.0, 1.0)
    alpha = np.clip(1.0 - 0.5 * uncertainty - 0.5 * bma_disagreement, 0.1, 1.0)

    # Apply dotted hatching pattern for high disagreement
    H, W = red.shape
    alpha_grid = np.copy(alpha)
    for r in range(H):
        for c in range(W):
            if bma_disagreement[r][c] > 0.20:
                if (r + c) % 2 == 0:
                    alpha_grid[r][c] *= 0.3

    # Generate RGBA image
    img_data = np.zeros((H, W, 4), dtype=np.uint8)
    img_data[..., 0] = (red * 255).astype(np.uint8)
    img_data[..., 1] = (green * 255).astype(np.uint8)
    img_data[..., 2] = (blue * 255).astype(np.uint8)
    img_data[..., 3] = (alpha_grid * 255).astype(np.uint8)

    img = Image.fromarray(img_data, "RGBA")

    if draw_hud:
        # Upscale temporarily to 512x512 using nearest neighbor to ensure legible text
        img = img.resize((512, 512), Image.NEAREST)
        draw = ImageDraw.Draw(img)

        # Draw dark translucent HUD panel
        draw.rectangle([0, 430, 512, 512], fill=(0, 0, 0, 180))

        # Render HUD labels
        eff_res_desc = "Unknown"
        if hasattr(bus, "effective_resolution") and bus.effective_resolution is not None:
            eff_res_desc = f"{np.nanmean(bus.effective_resolution):.1f}m"

        text_lines = [
            f"ASMAE CERTIFICATION LEVEL: {cert_level.upper()}",
            f"EFFECTIVE RESOLUTION: {eff_res_desc}",
            f"STATE: {getattr(bus, 'state', 'composite_assimilated_asmae').upper()}"
        ]

        y_offset = 438
        for line in text_lines:
            draw.text((15, y_offset), line, fill=(255, 255, 255, 255))
            y_offset += 20

    # Convert back to nested float lists for standard schema compatibility
    r_list = red.tolist()
    g_list = green.tolist()
    b_list = blue.tolist()
    a_list = alpha_grid.tolist()

    return {
        "red": r_list,
        "green": g_list,
        "blue": b_list,
        "alpha": a_list,
        "image": img,
        "metadata": {
            "certification_level": cert_level,
            "mean_uncertainty": float(np.nanmean(uncertainty)),
            "mean_bma_disagreement": float(np.nanmean(bma_disagreement)),
        }
    }
