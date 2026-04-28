"""
Legacy compatibility module.

Do not add new contracts here.
Use schemas.py for Layer 1 Fusion Context Engine V1.

This file re-exports all legacy types so existing imports like:
    from layer1_fusion.schema import FieldTensor, EvidenceItem, ...
continue to work during the transition period.
"""

from .schema_legacy import (  # noqa: F401
    EvidenceSourceType,
    ValidationStatus,
    EvidenceItem,
    FieldTensorChannels,
    FieldTensor,
    FusionOutput,
)
