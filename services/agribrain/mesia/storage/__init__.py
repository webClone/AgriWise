"""MESIA Native Storage Adapters — R6 §8.2.

Provides serialization adapters for native RF data formats specified in
the R6 blueprint:
  - SigMF (Signal Metadata Format) for generic IQ recordings
  - RINEX for GNSS observables and derived reflectometry products

These adapters produce standards-compliant metadata alongside the native
binary artefacts, ensuring immutable replay and interoperability.
"""

from .sigmf_adapter import (
    SigMFMetadata,
    SigMFCapture,
    SigMFAnnotation,
    SigMFAdapter,
)
from .rinex_adapter import (
    RinexObservationHeader,
    RinexSatelliteObservation,
    RinexAdapter,
)

__all__ = [
    # SigMF
    "SigMFMetadata",
    "SigMFCapture",
    "SigMFAnnotation",
    "SigMFAdapter",
    # RINEX
    "RinexObservationHeader",
    "RinexSatelliteObservation",
    "RinexAdapter",
]
