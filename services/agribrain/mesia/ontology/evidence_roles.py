"""MESIA Evidence Roles — derived from R6 §6.

A radio source may occupy more than one role.  For example, GNSS can be
both GEOMETRY_AUTHORITY and SENSING (reflectometry).  Cellular can be
TRANSPORT, CONTEXT, and conditionally SENSING.

The role determines what downstream authority a radio observation may
carry and how it enters (or does not enter) the ASMAE posterior.
"""

from __future__ import annotations

from enum import Enum


class EvidenceRole(str, Enum):
    """Evidence role taxonomy for radio sources."""

    SENSING = "SENSING"
    """Primary environmental measurement candidate.  May contribute to
    ASMAE posterior only after capability qualification."""

    TRANSPORT = "TRANSPORT"
    """Backhaul/connectivity only.  Connectivity metrics logged as
    NetworkEpoch context; never default sensing evidence."""

    CONTEXT = "CONTEXT"
    """Network/device/environment context (e.g., Android telephony
    metrics, CAMARA QoD).  Useful for nuisance attribution and anomaly
    detection; not direct sensing evidence."""

    TEACHER = "TEACHER"
    """Ground-truth or reference instrument (gravimetric, TDR/FDR, GPR,
    thermal/optical/acoustic).  Used only in the declared role; never
    silently converted to production truth."""

    SENTINEL = "SENTINEL"
    """Calibration and health monitoring reference (cable loopback,
    reference load/antenna/tag, noise source).  Provides independent
    instrument-quality evidence."""

    NEGATIVE_CONTROL = "NEGATIVE_CONTROL"
    """Known non-response reference (RF-absorbing/shielded, cable path,
    dummy antenna, dry/wet known volume).  Validates that a claimed
    effect is not an instrument or environmental artefact."""

    GEOMETRY_AUTHORITY = "GEOMETRY_AUTHORITY"
    """Positioning, timing, and trajectory authority (GNSS/RTK).
    Provides pose, covariance and time — not environmental sensing."""

    EVENT_LEDGER = "EVENT_LEDGER"
    """Intervention and action tracking (BLE valve commands, Zigbee pump
    status, irrigation flow).  Provides the event timeline that ASMAE
    uses as forcing, not as observation."""


# Roles that may produce BehaviourLikelihood for ASMAE (after qualification).
ASMAE_ELIGIBLE_ROLES = frozenset({
    EvidenceRole.SENSING,
})

# Roles that contribute to nuisance/confounder attribution.
NUISANCE_ATTRIBUTION_ROLES = frozenset({
    EvidenceRole.CONTEXT,
    EvidenceRole.EVENT_LEDGER,
    EvidenceRole.SENTINEL,
    EvidenceRole.NEGATIVE_CONTROL,
})
