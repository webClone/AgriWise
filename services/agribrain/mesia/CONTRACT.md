# MESIA — Scientific Contract

## System Name
**MESIA** — Multi-Environment Spectrum Intelligence Architecture

## Maturity Status
MESIA is an advanced research and engineering programme as of R6 (31 August 2026).
This module provides the P0 contract freeze: typed objects, state machines, and
scientific invariants, and now includes the full PyTorch FDTD solver, neural receiver
pipeline, and Wildfire Vanguard experiments.

---

## Non-Negotiable Rules (Constitutional Principles)

| ID | Principle | Operational Meaning |
|----|-----------|---------------------|
| P-01 | No universal-receiver fiction | Coverage manifests must exist before scans. MESIA never implies continuous coverage it does not have. |
| P-02 | Discover before identify | Detection records an observable wave event; protocol identity is a later, evidence-gated result. |
| P-03 | Identify before sense | Agricultural interpretation requires PROTOCOL_CONFIRMED or CONTROLLED_SOURCE, not merely an occupied band. |
| P-04 | Native evidence survives | IQ, CSI, range profiles, radar cubes, tag responses and device/API metadata remain immutable and replayable. |
| P-05 | No raw-phase stitching across independent RATs | Fusion occurs at calibrated likelihood, event, state constraint or closure level. |
| P-06 | Configuration is part of the measurement | Geometry, instrument, network, coexistence, calibration and policy epochs are mandatory scientific inputs. |
| P-07 | UNKNOWN is a valid result | Unfamiliar, ambiguous, unavailable and unobservable conditions are retained, not forced into known classes. |
| P-08 | ASMAE owns the posterior | MESIA does not maintain a competing biological truth or bypass AgriBrain evidence admission. |
| P-09 | Capabilities qualify separately | A cluster is never globally certified; each target, domain, use and evidence tier has its own authority record. |
| P-10 | Fail closed and revoke | Failed calibration, closure, observability, transfer, security or governance demotes affected evidence/use automatically. |

---

## MESIA ↔ ASMAE ↔ AgriBrain Boundaries

| System | Owned Responsibility |
|--------|---------------------|
| **MESIA** | Discovers/identifies radio observations; models radio behaviour and nuisance state; produces calibrated likelihoods, observability and closure. |
| **ASMAE** | Maintains explicit agricultural state/posterior on the shared adaptive lattice; applies observation operators; resolves cross-source conflict and uncertainty. |
| **AgriBrain** | Maintains canonical evidence/field/worldline context; diagnosis, planning, policy, authority and user projections. |

### Integration Rule
MESIA outputs remain **evidence proposals** until AgriBrain Layer 0 admits them
and ASMAE incorporates them under a valid observation operator.  MESIA-only or
quarantined evidence cannot create an executable action.

---

## What MESIA Does NOT Own

- Agricultural posterior or crop identity
- Prescription, irrigation, or input recommendations
- Satellite or EO observation operators (those remain in ASMAE)
- Ground-truth label authority
- User-facing action execution

---

## Typed Object Dictionary (Appendix A)

See `contracts/` subpackage for all 22 typed objects:

| Object | Module | Purpose |
|--------|--------|---------|
| ReceiverCapabilityManifest | `contracts.receiver` | Per-receiver hardware capability |
| AntennaPathManifest | `contracts.receiver` | Antenna/cable/filter/calibration chain |
| CoverageGraph | `contracts.coverage` | Observable frequency/time/space/polarisation map |
| CoverageTuple | `contracts.coverage` | Per-path coverage descriptor |
| WaveSurveyPlan | `contracts.wave` | Sweep/dwell/trigger priorities |
| WaveCandidate | `contracts.wave` | Calibrated detected event |
| SpectrumCalibrationEpoch | `contracts.calibration` | Noise/gain/spur calibration window |
| SignalIdentityHypothesis | `contracts.identity` | Ranked waveform/RAT/protocol candidates |
| ProtocolConfirmationReceipt | `contracts.identity` | Direct protocol evidence |
| RadioBehaviourContract | `contracts.behaviour` | Source-specific measurement primitive |
| BehaviourLikelihood | `contracts.behaviour` | Calibrated likelihood for ASMAE |
| RadioObservationPacket | `contracts.observation` | Core exchange format (Appendix E) |
| GeometryEpoch | `contracts.epochs` | Position/orientation/mount change |
| InstrumentEpoch | `contracts.epochs` | Device/firmware/gain/clock change |
| NetworkEpoch | `contracts.epochs` | Operator/cell/beam/scheduler change |
| CoexistenceEpoch | `contracts.epochs` | Interference/neighbours/motion change |
| CalibrationState | `contracts.epochs` | Calibration validity/uncertainty/drift |
| SoftwareModelEpoch | `contracts.epochs` | Detector/model/feature version change |
| ObservabilityCertificate | `contracts.scientific` | Supported zones/strata/rank/conditioning |
| ClosureCertificate | `contracts.scientific` | Held-out prediction performance |
| CapabilityAuthorityRecord | `contracts.authority` | Passed gates, allowed uses, expiry |
| RevocationEvent | `contracts.authority` | Why/when authority was withdrawn |
| SensingTaskReceipt | `contracts.task` | Requested vs executed action |

---

## Schema Design

Following the ASMAE pattern:
- **Frozen dataclasses** (`@dataclass(frozen=True)`) for all contracts
- **Deterministic `content_hash()`** on every typed object
- **`to_dict()` serialization** — no numpy in persisted objects
- **Runtime vs Manifest split** will be introduced in P1+ when native data exists
