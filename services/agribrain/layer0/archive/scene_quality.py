"""
Historical scene quality scoring calculations.
"""

def compute_scene_quality_score(
    valid_pixel_fraction: float,
    geometry_overlap: float,
    product_level_score: float,
    band_completeness: float,
    mask_quality: float
) -> float:
    """
    Computes quality_score according to V90.7 specifications:
      quality_score = (
          0.35 * valid_pixel_fraction
          + 0.25 * geometry_overlap
          + 0.20 * product_level_score
          + 0.10 * band_completeness
          + 0.10 * mask_quality
      )
    """
    return (
        0.35 * valid_pixel_fraction
        + 0.25 * geometry_overlap
        + 0.20 * product_level_score
        + 0.10 * band_completeness
        + 0.10 * mask_quality
    )
