# Akaloris / AgriBrain — Layer 0 Exit-Gate Deep Audit

**Date:** 2026-11-06  
**Analysis base:** `webClone/AgriWise` `main@6edd3721c0defa7eed94b44cf96601ba59a49696`  
**Most advanced Layer 0 code reviewed:** `fix/layer0-b2b08-postfreeze-input-boundary-20261105@6b6767c655a3093d1bea9e40b8df792dd5a65267`  
**Frozen B2B-08:** implementation `4197e09a1bf6c3af6b18d3db009baabf64d5669c`, documentation `a26bf80e54394a755aa599dc952c3402c707da8a`  
**Scientific Pilot:** PR #9 head `71ee1f788ec981bd0824089e46dc68164260444d`; Phase 1F work is on its separate branch `f1b20258ba4119806fdebc2c7875f2c9dbf44513`  
**Scope:** source-based closure assessment and proposed exact-head acceptance gates; this is **not** a new exhaustive audit of 260 current files, a live test execution, a field evaluation, or a merge authorization.

## Executive decision

**Layer 0 is not completely remediated.** All eight B2B cohort milestones are formally frozen, with substantial local and connected qualification receipts. Yet important science/recovery gates remain open. The October/November historical 469 findings are classified, **not individually adjudicated against the current head**. The current Layer 0 branch is **308 commits ahead of `main`** and its code has not been integrated into `main`. Proceed with the **observation-only Scientific Pilot** while keeping `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` in every pilot service. Move to Layer 1 source audit now if desired; reserve Layer 1 trusted integrated-state qualification for the exit gate below.

## Evidence inventory and counts

- Original source-only audit `AGB-CODE-2026-11-02`, version 0.22.0: **260/260** source files inspected (1,812,150 bytes), **469** original findings, **303 P1, 165 P2, 1 P3** original classifications. None of those numbers is a count of currently reachable, independently reproduced defects.
- Current first-order reconciliation document `plan/Layer0_Findings_469_Cohort_Closure_Reconciliation_2026-11-04.md`: maps **469** findings into six structural clusters (82 / 94 / 78 / 96 / 68 / 51) and cohort contracts. Its **RECONCILED** means mapped to workstreams, **not each finding proved fixed**.
- GitHub compare `main@6edd372...6b6767c`: **138** changed files across repo, **99** under `layer0/`, including **47** `layer0/tests/` files. Entire `layer0/perception`, `perception_models`, `sensors`, `calibration`, `geo_context`, `archive`, `learning`, and `sentinel5p` subdirectories have **no changes** on this comparison. That is not proof that every problem in them is live, but is evidence that no direct remediation was made to those module bodies.
- B2B cohort completion: **8/8 formally frozen**, not 469/469 verified resolved.
- The most recent `6b6767c` qualification report records **800 Layer 0 + 21 Layer 1 + 84 ASMAE = 905** Python passes and **12** connected MongoDB passes. These are locally executed receipts reported by the operator; this review did not re-run them or inspect a GitHub-hosted CI success.
- October 18 full AgriBrain 52-package assessment: **137 verified slices / 287 slices (47.7%)**; 52 packages, 153 requirements. This is a historical master-plan evidence metric, not a current Layer 0 completion percentage.

## Source-confirmed risk register

| ID | Priority | Evidence at `6b6767c` | Mandatory closure condition |
|---|---|---|---|
| L0-X01 physical checkpoint equivalence | **P1** | `irrigation_checkpoint_inputs.checkpoint_input_digest()` invokes `resolve_physical_event_plan()` with `day`, `zone_id`, `seen_event_ids`, **not the admission cutoff, trusted tenant/plot/geometry context or the full envelope-level receipt interpretation**. In `kalman_engine.ZoneKalmanFilter.step()`, a matching digest triggers an early committed-state return before admission. The user independently reproduced equal digests with differing cutoffs or envelope receipts. | Build one qualified state-impacting input-plan receipt with the exact trust scope, cutoff and signed physical grant set. Both fresh execution and cold replay compare the same committed plan hash, not a separately filtered approximation. Fail closed on changed eligibility or unknown legacy identity; no new L3 reservations during conflict. |
| L0-X02 operator journal submitted vs consumed | **P2** | `app/scoped_packet_run.py` constructs `submitted_receipt_ids` before L3 signature/physical state admission. `operational_reconciliation.reconcile_staged_assessment` requires a durable receipt row for **every** submitted ID and an exact state snapshot receipt-set match. An invalid second candidate after one committed receipt can prevent recovery. | Separate submitted, rejected, admitted, staged, committed, rolled back and recovered entries with reason, scope and signed receipt digest. Persist an atomic assessed-versus-consumed ledger and attest actual committed receipts; incomplete evidence must remain held without fraudulent completion. |
| L0-X03 multi-day journal assumption | **P2, newly source-traced** | HTTP assessments accept a start/end window; the `COMPLETE_RECONCILED` path requires **one** `state_snapshot_id` across all committed receipts. Distinct days normally generate distinct committed state snapshots. A valid interrupted multi-day assessment could be unrecoverable. | Support an ordered set of day/zone/snapshot commitments, or expressly reject multi-day L3 assessments at intake. Connected test two days, two snapshots, intervening crash, exact recovery without duplicate consumption. |
| L0-X04 committed receipt hidden by abort | **P1/P2, conditional** | `ABORT_AND_ROLLBACK` updates only STAGED receipts and can mark an assessment ABORTED without first rejecting unrelated already-COMMITTED receipts. Atomicity of its own mutations does not make the resulting assessment-science relation correct. | Committed physical delivery must never be silently represented as fully aborted. Require explicit committed-state resolution, recovery/partial-hold outcome, and operator audit. Test mixed STAGED/COMMITTED state with injected failures and concurrent operator CAS. |
| L0-X05 scientific audit not fail-closed | **P1 for Layer 1 promotion** | `state_engine.Layer0StateEngine.__init__` assigns `self._enforce_all_invariants`; no call to it appears in `state_engine.py`. The primary `run()` catches validation and self-audit exceptions, records a conflict/prints warning, then still returns a `Layer0StatePackage`. | Separate `diagnostic_only` and `scientifically_admissible`; invariant, validation or audit failure must be terminal to any Layer 1 **trusted-state** ingestion/publication. Always preserve an auditable failure receipt. Test injected exceptions, nonfinite covariance, spatial/source conflicts and no scientific promotion. |
| L0-X06 large plot grid partial coverage | **P1 conditional on caller** | `plot_grid.PlotGrid.from_polygon` clamps `width`/`height` to `MAX_DIM=500` without a coverage reduction flag or error. B2B fractional support/geometry authority elsewhere does not prove this older grid is harmless if invoked. | Replace silent clipping with explicit bounded tiling, rejection or authoritative partial-coverage descriptor. Test >5 km width/height, area conservation, alpha mask/support, CRS and outside-plot pixels, and prove production caller behavior. |
| L0-X07 scientific identity vs attempt time | **P2** | `state_engine.run` builds an ID from `...:{now.isoformat()}` and comments call it content-addressed; `source_package.Layer0SourcePackage` computes `package_hash` at construction, with no visibly universal post-mutation identity fence at the state handoff. This does not show every downstream hash is bad; it identifies a contract needing proof. | Separate immutable scientific-input root (full exact consumed source/forcing/model/config/geometry/knowledge cutoff) from execution attempt ID. Mutating a packet or forcing after construction must either invalidate/fail or yield a different science root. |
| L0-X08 unsupported crop/physics assumptions | **P2 / scientific limitation** | Original L0-019/L0-041 identified generic wheat-like parameters and missing crop-parameter propagation in the reviewed canonical runner. The current state-entry `DailyAssimilationEngine()` and `add_zone(... soil_props=...)` do not visibly prove that authenticated crop-specific parameters were bound. | Bind crop/cultivar/soil parameter identity to the state input root; assert scope-specific calibration provenance, or label unsupported values as uncalibrated/degraded. Do not claim calibrated state accuracy from PSD/numerical tests. |
| L0-X09 native sensor source truth | **P1 if enabled for state** | The entire `layer0/sensors/` source directory remains unchanged from the November 1 audited baseline. Original L0-241–268 include device/plot binding, calibration window, QA and time semantics, raw flow-to-mm physical support, and packet authority. Central signed packet admission reduces risk but does not prove a native source's physical truth. | Source-by-source acceptance with real device ID/registration, calibration certificate/time, bounded units, sensor/zone spatial support, measured versus estimated classifications, and negative missing QA/unknown device/late/replayed readings. Quarantine unqualified sensor-derived physical state and water events. |
| L0-X10 geo-context validity and spatial support | **P1 if used as measured evidence** | `geo_context/` unchanged; `GeoContextEngine` catches DEM/landcover/WaPOR processing exceptions and proceeds with partial context. Original L0-127–149 include masks, DEM quality, trust modifiers and acquisition-time substitutions. | Treat slope, land cover, WaPOR and placement estimates as context/proxy unless independently supported. Validate masks, finite pixels, DEM QA, published timestamps and outside-plot contamination. Enforce no state/prescription authority from missing QA. |
| L0-X11 optional ML/image pathways | **P2, defer only with isolation** | `perception/farmer_photo/crop_classifier.py` and `organ_classifier.py` initialize `self.model=None`; model-present branches are still `pass`, then use heuristics. Original L0-379–406 include model-readiness and QA/provenance gaps. Other perception/drone/IP-camera paths also unchanged. | Make heuristic outputs strictly diagnostic and non-assimilable, with explicit model origin/uncertainty. Full trained recognizer requires model registry, expert labels, held-out evaluation, scope/QA and crop-disease taxonomy, but **need not block Layer 1 audit** if the producer is disabled from trusted state. |
| L0-X12 SIF optional integration | **P2, defer only with isolation** | `sentinel5p/engine.py` constructs Kalman observations but only uses them for diagnostics and returns a package without passing them to the central Layer0Runner, which does not list Sentinel-5P as a core source. Original L0-095–106. | Explicitly mark SIF unsupported/diagnostic or implement a native signed packet/footprint/QA/time route and end-to-end test. No silent claim that SIF reaches assimilation. |
| L0-X13 legacy persistence and archived evidence | **P2 / conditional** | `state_persistence.py` writes JSON directly to `layer0_state_{plot_id}.json`, without an atomic file/tenant namespace barrier. `archive/` remains unchanged. Durable Mongo L3 commitments do not automatically repair these separate old paths. | Establish unused/isolated status for legacy warm-state load, or add atomic scoped persistence, schema/parameter/geometry/version CAS and restart tests. Archive raw source receipts must survive cache TTL/compaction until lineage is safely retained. |
| L0-X14 package/entrypoint and Layer 1 adapter gates | **Integration blocker** | `main` is 308 commits behind the corrective branch; the October 52-package register identifies F37 (Python namespace), F40 (annotation consumers), F01/F02 (admission/time) and T11 (resilience) as partially qualified. | One exact-head supported interpreter/dependency image; cold import and type-hint resolution of supported entrypoints, Layer0Runner-to-Layer1 data handoff, and provider/cold-cache outage drills. Do not assume 21 passing Layer 1 tests prove the full handoff. |

**Source-strength distinction:** X01, X02 and identified source faults are code-based. X03 and X04 are additional source-traced edge cases, **not** independently reproduced replica-set tests. X06, X08–X13 are conditional: their runtime severity depends on whether each producer can reach a trusted consumer on the target deployment. Do not inflate those into observed production incidents.

## Original Layer 0 audit inventory: domains to disposition

The original 469 findings span:

| Domain/pass group | Finding IDs | Count | Handoff recommendation |
|---|---|---:|---|
| Root interfaces, Kalman, observation and invariants | L0-001–041 | 41 | Explicit remaining state/identity/invariant closure |
| Data gateway | L0-042–063 | 22 | Confirm CAS/TTL/compaction and provider failure behavior at one current API |
| Sentinel-2 | L0-064–078 | 15 | Use qualified B2B native issuer; deny legacy/stat-only promotion |
| Sentinel-1 | L0-079–094 | 16 | Full polarization/orbit/grid QA and signed content at integration boundary |
| Sentinel-5P | L0-095–106 | 12 | Keep unavailable or qualify native SIF route |
| ASMAE scene products | L0-107–126 | 20 | Full captured byte/scene/geometry/runtime product proof |
| Geo-context | L0-127–149 | 23 | Enforce context-only, support-aware status unless independently measured |
| Archive | L0-150–180 | 31 | Cold recovery, immutable raw reference, retention/quarantine |
| Calibration | L0-181–208 | 28 | Flag heuristic parameters; require independent physical calibration before claims |
| Learning | L0-209–240 | 32 | Separate exploratory memory/models from admitted observation state |
| Sensors | L0-241–268 | 28 | Device identity, calibrated units, timestamps, spatial support and QA |
| Environment/weather | L0-269–337 | 69 | B2B weather source-role split plus cold provider/archive and missing-zero gates |
| Perception, photo, drone, camera | L0-338–462 | 125 | Diagnostic-only until model/source/space/time proofs are held |
| Legacy inference/model modules | L0-463–469 | 7 | Clearly disable/retire for trusted state; compatibility-only diagnostics |
| **Total** | **L0-001–469** | **469** | **No current per-finding verified closure count** |

## Bounded remediation sequence (proposed)

### Phase L0-C0 — Pin and classify production reachability

- Freeze three immutable references in the closure report: `main`, B2B-08 freeze, and latest post-freeze candidate. Do not change the master monograph or historical audit.
- For each original finding, record **current blob**, route owner, reachable in (a) trusted current state (b) optional diagnostic path (c) legacy (d) disabled (e) pending proof. Use dispositions `FIXED_VERIFIED`, `MITIGATED_BY_BOUNDARY_VERIFIED`, `ISOLATED_NON_AUTHORITATIVE`, `OPEN_REACHABLE`, `CONDITIONAL_UNPROVEN`. Require link to executable proof, not just cohort name.
- Publish **actual** accepted numerator for 469, not 469/469 classified. P1 reachable in trusted state must be 0 at exit; uncertain must be explicitly blocked from trusted state.

### Phase L0-C1 — Canonical scientific state safety (mandatory before L1 trusted input)

1. Require successful invariant/validation/audit verdict for science-grade packages; preserve failure provenance as diagnostic-only without crashing the whole readout.
2. Enforce stable input root independent of `run_timestamp`; include exact source identities, consumed weather, model/parameter version, geometry, crop/zone, observation ordering and origin/availability cutoff. Reject post-hash mutation or record a changed root.
3. Repair PlotGrid truncation or prohibit partial grid science without explicit spatial coverage and area accounting. Validate CRS, masks, alpha/finiteness and zone support.
4. Bind authenticated parameter configuration and its calibration provenance; enforce physically bounded state/Q/R/covariance including missing-weather and irregular-gap paths.
5. Test fail-injected invariant exception, bad QA, no observations, numeric zero, stale geometry, foreign plot/zone, oversized polygons and two source reorders.

### Phase L0-C2 — Signed-delivery residuals (separate, OFF in pilot)

1. Derive **one** qualified, immutable event execution plan from server-derived tenant/plot/zone/geometry/cutoff, canonical receipt at envelope or payload level, trusted verifier and full signed grant. Filter and checkpoint must use **the same plan**; input digest must express exact admitted physical effects, not merely submitted candidates.
2. Split journal records into submitted/eligible/rejected/staged/committed/rolled_back and reason; correlate each actual admitted/committed receipt to assessment and state snapshot under transaction, including crash timing.
3. Define multi-day model: either reject multi-day physical assessments or support ordered multiple per-day committed snapshots (and partial completion/repair). Never mark an assessment simply ABORTED while keeping unaccounted physically COMMITTED rows.
4. Connected isolated-rs0 positive: exact cold replay with renamed transport IDs; one and two genuinely distinct delivered evidence records; multi-day restart. Negative: noon vs afternoon cutoff, envelope versus payload receipt, changed precipitation/observations, duplicate IDs, tampered signature, parallel receipt revocation, invalid second delivery following committed first, CAS failure and crash at each transaction boundary. Assert no phantom restage, duplicate water, silent reuse, or false 'all aborted'.
5. Signed irrigation remains OFF in Pilot even when all these tests pass. Field sensor calibration/actuator and independent HSM are separate future operational gates.

### Phase L0-C3 — Source producer qualification and quarantine

- Start with sources required for the observation-only pilot: **S2, S1, true observed historical weather**, then independently qualified IoT only if available. Use actual immutable provider bytes or signed receipts, full CRS/grid/time/unit/QA and source/cutoff authority.
- Test real-world captured source cold cache, provider outage, stale/forecast mix, missing/true-zero precipitation, invalid bands/cloud/orbit/pixel data and foreign plot geometry, supporting decisions through Layer0SourcePackage and Layer0StatePackage.
- Explicitly quarantine unsupported SIF, heuristic photo, drone, IP camera, uncalibrated sensor and geo-context proxies from trusted state until separate models/certificates are qualified; diagnostic displays may remain.
- Verify that archive/learning/calibration fallback values cannot masquerade as physical observations via wrappers and legacy aliases.

### Phase L0-C4 — Durability, packaging and cross-worker safety

- Run supported Python runtime import/schema/type-hint checks (including F37/F40), actual production main-app lifespan and issuer trust root initialization.
- Fail-inject provider timeout/cache corruption, clock skew, key/receipt revocation, Mongo transaction abort/primary stepdown/restart, duplicate API requests, geometry epoch changes and partial journal writes. Verify exact source/commit lineage and resulting error/status observability.
- Keep obsolete `state_persistence.py` and archive routines explicitly excluded from canonical production, or repair their atomic/tenant/version integrity if invoked.

### Phase L0-C5 — Layer 0 → Layer 1 scientific handoff acceptance

- On one candidate integration SHA, run actual source acquisition/captured source → native qualified Layer 0 packet → source package/state estimate → `Layer0RunnerOutput.to_layer1_bundle_kwargs()` → `Layer1FusionEngine.fuse`/canonical Layer 1 entrypoint. No fabricated source calibration, time, geometry, or L8 proof.
- Require Layer 1’s evidence ledger to contain the **exact admitted source IDs/hashes** and corresponding rejection ledger; preserve uncertainty, scope, observation-versus-estimation roles, weather time and crop/geometry epochs. Predictions stay estimates; unqualified inputs do not gain state authority.
- Test owner-authenticated observation-only publication separately on the isolated Scientific Pilot lineage; do not merge PR #9, post-freeze L3 or `main` merely to run this acceptance.

## Exit criteria and decision classes

**`L0_READY_FOR_LAYER1_TRUSTED_INPUT`** only if all hold:
1. No unresolved, reachable P1 permits unsupported evidence to influence trusted state or silently misidentify the input root.
2. Any remaining original finding has explicit current evidence-backed disposition; legacy/optional work is hard-isolated from trusted routes, rather than assumed fixed.
3. One exact, reproducible source → Layer 0 → Layer 1 handoff passes under qualified inputs and explicit denial cases, with correct provenance, numeric, spatial and temporal contracts.
4. State integrity/audit errors are diagnostic, not publishable scientific success; no silent truncation of required plot support.
5. Exact candidate SHA passes Layer 0 + Layer 1 regression, affected ASMAE fast contract and selectively relevant connected Mongo/provider gates; include preserved real-scene receipts without claiming they were freshly rerun.
6. Signed irrigation remains disabled for the observation-only pilot, with a separate acceptance HOLD for physical L3 until C2 passes; no automated physical commands or positive prescription authority.
7. Immutable protected branches and original monograph/audit stay unchanged; no merge without owner approval.

**`L0_FULL_PRODUCTION_PHYSICAL_READINESS`** is a later, stricter milestone: externally operated HSM, independent sensor and hydraulic calibration, native field provenance, actuator safety, physical water-conservation/measurement validation, and cross-site incident/recovery drills. It is NOT required merely to begin Layer 1 code review or observation-only pilot.

**Decision:** Do the source/exit-gate work in parallel with the observation-only pilot; fix C1 before using Layer 0 as a trusted Layer 1 producer. C2 can run separately and must not contaminate pilot. Avoid reopening all 469 as independent programming tickets; classify by current reachable authority paths, then close each root cause once with auditable evidence.