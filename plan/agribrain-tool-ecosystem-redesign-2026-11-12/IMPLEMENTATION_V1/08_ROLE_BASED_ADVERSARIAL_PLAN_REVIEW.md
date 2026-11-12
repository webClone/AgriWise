# Role-Based Adversarial Review of the Implementation Plan
**Status:** Structured single-author, multi-perspective design challenge. **Not independent multi-agent execution and not code/test validation.**
**Date:** 2026-11-12  
**Source documents:** MASTER, P00–P15, agent charter, DESIGN_V1, existing Round2 findings.
## Reviewer 1 — Scientific integrity (A4 perspective)
**Challenge S1:** The Tool Library's presence of 13 latent-state surfaces could imply 13 valid subfield rasters. **Resolution:** P07 requires all 13 entries in catalog, per-state eligibility and scalar-only no-pixel case; real SIRE render authorization retained.
**Challenge S2:** "Related sensor" could be marketed as posterior assimilation proof because it is nearby. **Resolution:** separate `spatially_near` from `admitted_by` and `assimilated_into` proof edges (P05,P07,P13).
**Challenge S3:** Historical rewind may show observations first acquired/ingested after cutoff. **Resolution:** P03,P13 require knowledge cutoff and source `first_available_at`, exact historical snapshot, no silent current fallback.
**Challenge S4:** MESIA RF spectrum or a planned drone route could be interpreted as physical ground truth. **Resolution:** modes + source receipts + no physical claim (P09,P10,P11).
**Open:** Determine state-specific units, nomenclature and exact on-map privilege from *frozen backend schema* before finalizing design copy. Do not assume full correlated covariance is available.
## Reviewer 2 — Security and actuation (A6 perspective)
**Challenge SEC1:** Development plot-owner bypass is independent of UI route refactor; delaying repair until tool host would leave unsafe source scope. **Resolution:** P01 P0 before feature shell.
**Challenge SEC2:** Frontend registry flag can claim hardware allowed while backend lacks permissions. **Resolution:** registry is discovery/presentation only; backend enforces signed owner+device permission, separate from irrigation safety flag.
**Challenge SEC3:** Feature adapter that trusts geometry or `tenantId` from client could disclose foreign devices. **Resolution:** owner-scoped read-only adapters validate actual registry source and object ID; foreign plot tests in P05/P15.
**Challenge SEC4:** SIRE pixel may be displayed under another geometry epoch. **Resolution:** mask cache geometry digest+grid and numeric/publication proofs P01,P06,P07.
**Open:** Review authentication integration with development-session bootstrap and forbid any public production bypass. Distinguish real drone dispatch approval from physical irrigation lock; no implicit permission transfer.
## Reviewer 3 — Map and systems architecture (A3+A2 perspectives)
**Challenge G1:** Python sensor registry has lat/lng, but Next Prisma `sensor` status route currently does not expose them. A naive join by display name may misplace devices. **Resolution:** P05 must define stable cross-system device identity, owner check, registry epoch, canonical coordinate source and reconciliation of duplicates. Unresolved source mismatch = no pin.
**Challenge G2:** Multiple independent map layers can be enabled, but 1000 events + devices + large raster may cause slow rendering. **Resolution:** viewport indexing, clustering, layer LOD, perf fixtures in P06/P14.
**Challenge G3:** Replacing PlotMapShell outright could break certified raster/pixel receipts. **Resolution:** extend typed vector composition around existing scientific materializer and preserve after-render proof.
**Challenge G4:** Shared state may conflate `timeCursor` vs `observedAt` vs `knowledgeCutoff`. **Resolution:** separate controllers and request-generation tokens P03, exact time proof P13.
**Open:** Decide storage/stream implementation for durable event ledger, view-cache identity, and map-layer visibility state after observing source performance baseline.
## Reviewer 4 — Product and accessibility (A1+A8 perspectives)
**Challenge U1:** 94 concepts are too many to show as 94 equally weighted dock buttons. **Resolution:** complete searchable catalog plus 5–8 pinned Dock favorites and contextual compatible tools; all concepts still discoverable, with aliases deduplicated.
**Challenge U2:** Full scientific complexity may overwhelm farmers or Arabic RTL users. **Resolution:** farmer summary vs expert detail around same science, Arabic RTL and interactive accessible object list P02/P14.
**Challenge U3:** Tool's "planned" badge may appear disabled and useless. **Resolution:** enable discoverable explanation, protocol setup and hypothetical preview without claiming computation or physical execution.
**Challenge U4:** A canvas-only UI prevents keyboard, assistive and small-screen selection. **Resolution:** map entity list alternative, focus return, touch bottom sheet and 200% zoom tests P14.
**Open:** visual approval of true Akaloris theme, default on/off overlay groups, right inspector widths, tool workbench transitions and relative emphasis for farmers vs experts.
## Reviewer 5 — QA/program delivery (A7+A0 perspectives)
**Challenge Q1:** A single green unit-test count could miss broken map render and source identity. **Resolution:** browser pixel/legend/receipt + negative tests P07/P15.
**Challenge Q2:** 16 passes could become one unreviewable PR. **Resolution:** bounded pass PR, R0–R5 gate, no >~20 meaningful files per change without splitting; old route feature flag.
**Challenge Q3:** Feature catalog completion could be counted as 52-plan science repair. **Resolution:** dedicated UI ledger, zero automatic F/T credit, proof to qualify original slices individually.
**Challenge Q4:** A team of nine reviewers may not exist; claiming nine independent agents would be misleading. **Resolution:** document assigned *roles*, record actual executed reviewer identities and clearly label role-based review when performed by same actor.
**Open:** Staffing and genuine independent agents, CI browser runner, reliable production-like staging env; no fixed calendar until P00 verifies them.
## Review resolution
The plan is **ready to begin P00 baseline and prototype review**, but **not implementation-verified**, not independently accepted by nine agents and not release-authorized. No P00–P15 acceptance gate has been executed by the act of writing this audit. The above design critiques are recommendations that must be revisited with distinct implementation reviewers and actual code/test evidence.
## Product decisions to approve before P02
1. Default V2 appearance: immersive map-first hybrid, 13 ASMAE states in accessible separate Lab, main Tool Library pinned dock.
2. Default vector categories: sensors/zones/recent geolocated events; drone/MESIA/tasks/cameras on demand, all individually toggleable.
3. One primary authorized SIRE raster + one optional comparison; vector overlays unlimited in capability but decluttered.
4. Full workbench may expand while retaining a linked map context and exact plot/time identity.
5. No real hardware physical dispatch in observation-only pilot; real operations an independently governed future track.
These are proposed defaults only; they should be approved or adjusted, not silently inferred as accepted by the user.
