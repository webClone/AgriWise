"""
AgriWise Unified Crop Database — Single Source of Truth.

200+ crop species covering Mediterranean, MENA, Sub-Saharan, and Tropical zones.
All agribrain layers (L2, L3, L4, L6, orchestrator) import from here.

Usage:
    from crop_database import get_crop, list_crops, resolve_crop_code

Architecture classes:
    cereal, maize, rice, legume, vegetable, perennial, cotton, tropical_tree
"""

from .registry import (
    CropSpec,
    get_crop,
    list_crops,
    list_crop_codes,
    resolve_crop_code,
    get_architecture_class,
    CROP_REGISTRY,
)

__all__ = [
    "CropSpec",
    "get_crop",
    "list_crops",
    "list_crop_codes",
    "resolve_crop_code",
    "get_architecture_class",
    "CROP_REGISTRY",
]
