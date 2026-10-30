# ASMAE Batch A+B integrated verification — e85cfd2

Completed 25 October 2026. Candidate `e85cfd224f8a731e2959648ce28450e27782188f`; exact parent `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`; branch `feat/f36-t09-asmae-13-state-publication` independently confirmed at the candidate.

## Decision

**Hold the merge. The cohort is materially implemented but only partially verified as complete.** An introduced P1 runtime binding regression affects ordinary ASMAE map conversion/output assembly. The broader per-state, permission, availability and artifact contracts also retain connected gaps. Keep the verified changes and finish the existing A/B cohort in one integrated correction revision; do not split this report into another series of residual-only projects.

The review verifies real progress: H_t indirect labeling, zero-overlap exclusion, H_t memory protection, covariance-only positive updates, forecast memory evolution, lossless counters, schema False defaults, several denial carriers, all thirteen range registrations, LAI legend coverage, empty-raster handling, identity-nodata cleaning, normal generation-addressed ASMAE cache commits and explicit two-dimensional mask preservation.

Those local corrections do not yet establish the full connected publication contract. The user-reported 57 passing repository tests are retained as author-reported receipts. They were not rerun or used as the correctness oracle. Fresh authored native/exact-fragment probes reproduce both repairs and remaining failures against the exact parent.

## 1. Source identity and scope

The candidate has one parent, d59c9bd. Fourteen production Python modules changed; the commit also includes two plan documents and a new test file. All fourteen production modules compile. Compilation does not detect the reproduced runtime NameError/UnboundLocalError.

Both selected source corpora contain 1,087 files, matched against their pinned Git blobs and SHA-256 hashes and unchanged after review. This is identity coverage, not a claim that every selected file was exhaustively audited. The review concentrates on the integrated A/B boundaries and their connected active entrypoints. Repository tests and audit documents are not scientific evidence inputs.

Six specialist lanes executed native component code and explicitly identified isolated AST/pure TypeScript fragments. No full engine/provider/runner/API/browser/GIS-file/hardware execution occurred. The exact ordinary converter method does run natively; the assembly lexical-prefix test is described separately below.

## 2. Verified repairs and remaining status

| Original workstream | Independently verified progress | Integrated disposition |
|---|---|---|
| WB01 scientific support | H_t indirect labels, zero H_t support rejection, all-target negligible influence rejection, H_t NOT_ASSIMILATED guard, forecast evolution and all three counters | Partial: per-state result is ignored by ledger admission; active proxy path bypasses the new policy |
| WB02 permissions | Schema False defaults, missing/string-false denial, permission-alias False intersection, native restriction ingress and explicit positive non-ASMAE grant controls | Partial: support/ceilings are incompletely bound; malformed permissions and competing carriers remain permissive |
| WB03 catalog/availability | All thirteen range entries, LAI legend through 8, empty raster without scalar becomes missing/disabled | Partial: malformed scalar/pixel qualification, temporal-status consistency and canonical catalog convergence remain |
| WB04 spatial validity | Native identity nodata cleaning and grounding consequence repaired; intended None/concentration logic works under explicitly supplied scratch binding | Hold: new native NumPy binding failures; scalar maps/resampling/preflight still incomplete |
| WB05 artifacts/export | Normal generation publication, failure-before-commit retention, legacy fixed reads, explicit 2D masks and richer explicit-attribute export | Partial: scientific-policy migration, mask edge contracts, canonical export parity and L10 durability remain |
| WB06 expert/GIS consumer | Outside current A/B patch | Deferred Batch C, not a new e85 regression |

## 3. Required completion groups

### AB-R01 — P1: repair native bindings and finish spatial continuity

The candidate adds `np.isfinite` inside `_microzone_to_grid` without binding NumPy in that method or at module scope. Native production-module import plus the ordinary call below raises NameError:

```python
engine = ASMAEEngine.__new__(ASMAEEngine)
engine._microzone_to_grid({'mz_000_000': [0.0] * 13}, None)
```

The exact parent returns thirteen 1×1 zero grids. The normal EnKF means/sigma producer emits this microzone-keyed vector shape; the counterexample does not rely on sparse or malformed IDs. See [services/agribrain/layer05_asmae/engine.py:L3271-L3315](https://github.com/webClone/AgriWise/blob/e85cfd224f8a731e2959648ce28450e27782188f/services/agribrain/layer05_asmae/engine.py#L3271-L3315).

A separate failure remains even if a module import is added: `_assemble_output` now calls `np.isfinite` before its existing local `import numpy as np`. Python marks np local for the whole function. An exact production assembly prefix preserving that later local binding raises UnboundLocalError on ordinary finite state-keyed uncertainty grids; parent prefix returns. This scoped prefix does not execute the full assembly method or its late runtime dependencies. Relevant reads are at 1969/1985 and the local import at 2174.

**Adding only a module-level NumPy import is insufficient.** Centralize or move the binding before every use and remove the shadowing pattern. Then run the native converter and a scoped native assembly fixture without injected globals.

Preserve the intended None fix while completing the same validity contract: scalar support maps still zero-fill missing cells; shape/zone IDs remain unqualified; bilinear resampling with None can erase a supported zero endpoint through NaN×0; frontend preflight remains the earlier weaker contract. Sparse/malformed cases are authored boundaries, and normal incidence is not established. The None/aggregate success controls deliberately supply NumPy in scratch and must not be described as native candidate acceptance.

### AB-R02 — P1 scientific contract: make per-state receipts authoritative across both update paths

H_t now records `per_state_influence`, but accepts the whole report when any target changes. The successful report retains every target; the ledger increments each target from report-level success. In the native constant-LAI/varying-vigor fixture, LAI delta is exactly 0 and its own `state_influenced=False`, yet accepted count is 1 and SIRE calls it indirectly constrained. The varying-LAI positive control updates normally. Mean-zero covariance contraction is separately verified as informative and accepted.

The active `update_step_proxy` path still updates NOT_ASSIMILATED memory and emits unconditional accepted proxy reports. Candidate and parent both change memory by **0.5467425258** in the controlled proxy fixture. `run_enkf` selects this path without H_t; the full run was not invoked. Filtering only the outer report is insufficient because the numeric helper iterates the original mapping's targets.

Primary evidence: [services/agribrain/layer05_asmae/assimilation/filter.py:L1751-L1823](https://github.com/webClone/AgriWise/blob/e85cfd224f8a731e2959648ce28450e27782188f/services/agribrain/layer05_asmae/assimilation/filter.py#L1751-L1823), [services/agribrain/layer05_asmae/feature_export.py:L118-L154](https://github.com/webClone/AgriWise/blob/e85cfd224f8a731e2959648ce28450e27782188f/services/agribrain/layer05_asmae/feature_export.py#L118-L154). Complete one shared target-policy selector for numerical helpers and report builders; admit/exclude each target independently; make ledger, feature export and downstream accepted-target consumers use that result. Keep forecast/decay evolution and legitimate uncertainty-only updates intact. This is scientific support qualification, not a demonstrated prescription or hardware effect.

### AB-R03 — P2: finish one typed capability/restriction projection

Native raw surfaces with Unsupported or DIAGNOSTIC support can still copy metadata True into state-update permission. The normalized ledger ceiling is not consistently bound into native provenance/permission calculation. Aliases and the independent display gate remain more restrictive, creating inconsistent views.

The new strict parser still maps arbitrary numeric values by truthiness: NaN, Infinity, -1 and 2 can become True. Ceiling handling uppercases `str(enum)` without normalizing `.value`; actual enum objects bypass recognized names, while TRAINING_EXPORT and declared unknown ceilings remain permissive. Valid explicit PRESCRIPTION_DRIVER, STATE_UPDATE and DIAGNOSTIC string controls demonstrate intended grants and denials.

The serializer uses first-carrier selection for enforcement but later writes a full restriction union. An empty attribute list can mask a revoked provenance list while the final document records the revocation alongside True permissions. Permissive attribute/snake ceilings can likewise mask stricter provenance/camel ceilings. See [services/agribrain/layer10_sire/surface_contract.py:L70-L83](https://github.com/webClone/AgriWise/blob/e85cfd224f8a731e2959648ce28450e27782188f/services/agribrain/layer10_sire/surface_contract.py#L70-L83) and [services/agribrain/layer10_sire/surface_contract.py:L217-L270](https://github.com/webClone/AgriWise/blob/e85cfd224f8a731e2959648ce28450e27782188f/services/agribrain/layer10_sire/surface_contract.py#L217-L270).

Normalize supported finite/binary booleans and enum/value/name forms once. Union restrictions before making decisions, intersect all current capability ceilings, and bind per-state support to raw constructor permissions. Use the same normalized result in aliases, canonical JSON and export. Keep valid positive controls and compatibility policy explicit. No downstream action or exploitation is claimed.

### AB-R04 — P2: qualify complete availability/domain receipts

The original eight missing range entries, LAI legend and metadata-only empty-surface cases are repaired. Remaining malformed inputs reveal incomplete qualification: flag-only scalar claims, string `false` scalar flags, boolean/NaN/Infinity/garbage scalar values can still create plot availability. Boolean/string raster values can count as valid pixels; invariants accept NaN/booleans and can raise TypeError on strings. These are controlled boundary cases, not evidence of normal field-generated corrupt values or an overlay bypass.

Scientific domain checks, scalar artifacts, pixel masks, inspection and pixel authorization still need one typed contract. Catalog tables remain manually duplicated. The genuine empty-ledger temporal fixture still treats prior phenology and memory differently; explicit model/temporal status controls pass both. That is a native-producer/exact-gate fixture, not a complete temporal forecast execution.

Complete finite nonboolean qualification before ranges, use real scalar/artifact support instead of flag truthiness, preserve genuine scalar zero and diagnostic inspection, and derive all consumers from canonical product/domain metadata. Keep invalid state failures local so qualified siblings survive.

### AB-R05 — P1 scientific migration plus P2 artifact parity/durability

**Storage-format compatibility currently bypasses scientific-policy correction.** The actual parent ledger builder writes an authored accepted real NDVI→vigor receipt under the old directness policy. Parent native cache save succeeds. Candidate computes the identical input cache key and accepts that legitimate old cache. Native candidate feature export retains real/direct source, confidence/weight **0.90**, and field-approval eligibility True; SIRE still labels it Observed/direct, with management eligibility False.

Every old artifact checksum is legitimate. This is a missing scientific-policy migration boundary, not a checksum bypass. Separate storage format from operator/descriptor/support-policy compatibility. Include policy identity in cache execution identity or explicitly requalify old scientific receipts; retaining legacy parsing for archive/research must not silently restore current Observed/approval claims.

Other connected artifact issues remain:

- A valid `np.ma.array(data)` with scalar nomask=False now fails publication; parent saves successfully. Normalize masks to data shape or deliberately omit all-false masks.
- Manifest-consistent undersized masks are clipped with min(shape) instead of rejected. Require exact typed pairing/shape/role checks. This authored mismatch is not shown as normal writer output or an external exploit.
- Compatibility export manually rebuilds metadata. Native thirteen-state generation puts confidence 0.8 in provenance; canonical JSON resolves it, but all thirteen compatibility entries have confidence None. Provenance masks/grid sigma and canonical permission denials can also diverge.
- The equivalent unchanged L10 cache writer still overwrites fixed paths and deletes the prior JSON/NPZ after an injected JSON rename failure. The exact isolated writer/sanitizer uses an admitted-fixture validator stub; no full publication validator/runner is executed.

Primary evidence: [services/agribrain/layer05_asmae/cache.py:L510-L579](https://github.com/webClone/AgriWise/blob/e85cfd224f8a731e2959648ce28450e27782188f/services/agribrain/layer05_asmae/cache.py#L510-L579), [services/agribrain/layer10_sire/products/export.py:L75-L154](https://github.com/webClone/AgriWise/blob/e85cfd224f8a731e2959648ce28450e27782188f/services/agribrain/layer10_sire/products/export.py#L75-L154), [services/agribrain/layer10_sire/runner.py:L1457-L1544](https://github.com/webClone/AgriWise/blob/e85cfd224f8a731e2959648ce28450e27782188f/services/agribrain/layer10_sire/runner.py#L1457-L1544). Derive export metadata from the actual canonical receipt and apply immutable generation/atomic manifest discipline to both ASMAE and L10 caches. Keep current successful generation/failure-retention fixes.

Strict non-raster JSON normalization and post-commit cleanup/fsync ambiguity are documented hardening qualifications. A fault injected after manifest switch can expose cleanup ambiguity, but ordinary incidence after the current helper's replace is unestablished. UUID uniqueness alone does not establish content-stable retries or safe garbage collection.

## 4. One completion revision and one release gate

Use the existing integration branch. Keep one owner for shared hotspots (`engine.py`, `filter.py`, ledger/feature export, `surfaces/asmae.py`, surface contract and cache interfaces); parallel owners work in isolated worktrees. These five groups are workstreams inside the same A/B completion revision, not five new repair programs.

1. Fix native import/binding failures first so real assembly fixtures can execute.
2. In parallel, finish shared per-state policy/receipt consumption, typed capability intersections and finite availability/domain qualification.
3. Finish immutable artifact masks/readers, scientific-policy migration, canonical compatibility export and the equivalent L10 transaction.
4. Run one complete integrated matrix after combining the work: ordinary native converter/assembly; H_t and proxy; constant versus varying target; covariance-only update; memory forecast versus forbidden analysis; all thirteen domain/availability cases; all capability encodings/carriers and explicit grants; sparse holes and zero; mask shape/nomask; legacy-policy bridge; cache interrupted commit and real concurrent readers/writers; native generator→canonical→compatibility receipt parity.
5. Run relevant regression suites once after that matrix. User-reported repository greens supplement, rather than replace, native boundary/connected-path evidence. Keep earlier checked-square/covariance fixes frozen unless those implementations change.

Batch C UI/GIS scaffolding may continue against the shared contract. Its deferred features are not blockers invented by this review; they also cannot be used to declare A/B complete while ordinary map assembly fails.

## 5. Verification receipts and qualifications

| Lane | Fresh observation coverage |
|---|---|
| Semantics | 15 differential observations; eight assimilation, three counter and one forecast fixture per snapshot |
| Authority | 23 candidate / 13 parent observations; actual ceiling encodings and explicit grant controls |
| Catalog | 30 main plus two temporal observations per snapshot |
| Spatial | 15 differential Python plus six pure TypeScript preflight observations |
| Cache | 16 observations; two writer processes perform 16 writes while a reader performs 90 loads |
| Export | 18 candidate / nine parent observations; native builder/canonical comparison and isolated L10 transaction |

Counts overlap; no aggregate independent-test count is claimed. Twelve top-level replay commands complete successfully. Success means fixes, residual defects and controls reproduce; cohort acceptance is **HOLD_PARTIAL**. Fourteen changed production modules compile, while the introduced native runtime failures remain reproduced.

The review runtime is supported Python 3.12 and Node with TypeScript support; the user reported tests on Python 3.13. Lexical NumPy binding failures are ordinary Python semantics. No claim is made that the user's test commands were rerun or failed.

The coordinated replay initially encountered a review-harness enumeration of generated bytecode. The harness now excludes `__pycache__` from Git-source receipts; the corrected complete replay passes. That correction changes review tooling only, and its original diagnostic is retained. Production source bytes remain unchanged.

The evidence archive contains strict JSON results, exact source receipts, scripts, six specialist reports, original-parent identity, replay logs, normative plan/R3 references and source reconstruction instructions. It excludes complete production source files, repository test files and private runtime stores. The exact staged sources and scripts were executed; a full new Git-object materializer reconstruction was not.

## 6. Governance

The governing master plan, sequencing addendum and task register remain pinned to matching candidate Git blobs. R3 scientific reference identity remains verified. Relevant requirements include AB-ASM-003/011/016, AB-ARC-005/006/007 and AB-L10-001, through F36/F38/T09/T11. All **52 FA milestones remain open, zero checked**.

No production source edits, merge, push, remote comments, full provider/pipeline/browser execution or hardware operation occurred. The next action is a consolidated A/B completion implementation, followed by one integrated verification gate.


---

# Specialist appendix: Scientific support

# Batch A scientific support: e85cfd2 against d59c9bd

## Disposition

**WB01 is partially repaired.** H_t directness, zero-spatial-support exclusion, all-target negligible-influence exclusion, H_t NOT_ASSIMILATED protection and direct/proxy/indirect counter preservation are verified repaired. One coherent per-state support contract remains incomplete across target qualification, ledger consumption and the active proxy entrypoint. Correct this within the existing A/B cohort; do not split it into serial micro-reviews.

Fresh native offline replay: **eight assimilation cases per snapshot, three ledger-counter controls per snapshot, one native forecast control per snapshot, and fifteen grouped observations**, all reproduced. Successful observations include current residual behavior, not passing scientific contracts. No repository test or prior audit claim is a correctness oracle.

## Verified corrections

- Native positive H_t NDVI updates vigor/LAI as indirect support; SIRE no longer labels them directly observed. Exact parent labels both direct/Observed.
- Zero H_t support produces no numerical change and no accepted state count; parent previously grants accepted counts.
- Constant whole-state ensembles produce excluded negligible-influence receipts rather than accepted updates.
- H_t observation analysis excludes stress_memory as NOT_ASSIMILATED. Candidate memory delta is zero with no accepted count; exact parent changes memory by **0.5467425258**.
- Legitimate varying target updates remain possible. A zero-mean-innovation positive control retains covariance contraction and is accepted, preserving uncertainty-only information.
- Native process forecast still advances the NOT_ASSIMILATED accumulator. The controlled hot-weather fixture changes stress memory by **0.024**; observation prohibition has not frozen its forecast evolution.
- Direct, proxy and indirect counters all survive native ledger generation → canonical normalization at exactly one. This closes the prior direct/proxy counter loss.

## Remaining coherent group — per-state receipts are recorded but not authoritative everywhere

### 1. A non-influenced target still gains support when its sibling changes

`assimilation/filter.py:1751–1784` calculates a per-state Boolean `state_influenced`, but determines report-level acceptance using `has_actual_influence`, true if **any** mapped state changes. The successful report at `1798–1823` retains the full target list, including targets whose own influence is false.

`feature_export.py:118–154` then increments accepted counts for every target whenever report-level `update_applied` is True. It never consumes `per_state_influence` to reject the unconditioned target or record a per-state exclusion.

Native controlled fixture: positive H_t and varying vigor ensemble with a constant LAI coordinate. Candidate outputs:

- LAI maximum analysis delta: **0.0**.
- `per_state_influence['lai']['state_influenced']`: **False**.
- LAI `accepted_update_count`: **1**.
- SIRE LAI support class: **indirectly_constrained**.

The varying-LAI positive control changes LAI and receives accepted support; the probe has not disabled the filter. Current field-approval restrictions prevent the old direct-approval overstatement, but incorrect state-specific support still propagates to publication. No prescription or field actuation is claimed.

### 2. The active proxy path bypasses the new observation policy and influence qualification

`update_step_proxy` at `filter.py:1833–1937` retains its prior target filtering and unconditional accepted proxy reports. Its target list at `1861–1867` does not consult `AssimilationPolicy.NOT_ASSIMILATED`, and the actual update helper at `2028–2051` iterates the original mapping's targets. Merely filtering the outer report list would therefore be insufficient.

The native proxy-memory fixture changes NOT_ASSIMILATED stress memory by **0.5467425258**, and its ledger receives `accepted_update_count=1`. Candidate and exact parent reproduce the same delta. A proxy NDVI fixture with constant LAI also leaves LAI unchanged while granting an accepted proxy count.

This entrypoint is active code: `run_enkf` at `filter.py:340–343` selects `update_step_proxy` when real H_t is unavailable. The full run was not invoked. Proxy labeling still limits scientific identity, and mean-only publication has other restrictions; this finding does not claim a direct-observation badge or eligible pixel map from the proxy branch. It establishes inconsistent numerical policy and per-state qualification between two active assimilation entrypoints.

## One correction sequence in the current A/B cohort

1. Introduce one target-policy selector used by H_t and proxy report producers **and their numerical update helpers**. Forbid observation analysis of NOT_ASSIMILATED states before mutation while preserving forecast/decay behavior.
2. Make per-state admission authoritative. Record applied/excluded status, actual support and qualified numerical/covariance influence per target. A report may remain globally successful while an unaffected target receives its own exclusion receipt.
3. Make ledger construction, feature export and the accepted-target selector for downstream graph regularization consume that per-target result. Do not infer per-state support from report-level success.
4. Apply the same state-scaled tolerance/covariance policy to proxy updates. Retain legitimate covariance reduction when mean change is zero; do not require mean displacement alone.
5. Preserve direct/proxy/indirect counters, source IDs and current authority ceilings. Reject contradictory legacy receipts or demote them with an explicit reason instead of silently inventing support.
6. Run one integrated extraction/update → ledger → normalization → feature/SIRE matrix across both entrypoints, with the positive controls above. No further prior-square/covariance review is required unless those implementations change.

## Reproduction and evidence scope

Run `python review-ab-e85cfd2/semantics/probes.py` from the reconstructed workspace. Candidate and parent execute in separate processes to avoid import identity contamination. Network connections are blocked; scenes and source flags are authored declarations, not acquired field data. Native update, process forecast, ledger builder, canonical adapter and SIRE classifier execute. Full engine/runner/provider/API/browser/prescription/hardware paths do not.

`candidate-results.json` and `parent-results.json` retain full controlled receipts, deltas and classification. `results.json` records the fifteen assertions. Source file digests are checked before/after; production Git blob and SHA-256 receipts are included for the invoked boundary modules. No production file was modified.

Governing intent: F36 per-variable support, AB-ASM-003 state-specific influence, AB-ASM-011 permission/label propagation, AB-ASM-016 local validity and AB-ARC-005 factored authority. This bounded verification closes no full package FA milestone.


---

# Specialist appendix: Capabilities and restrictions

# A/B capability and restriction verification — e85cfd2

Candidate `e85cfd224f8a731e2959648ce28450e27782188f`, exact parent `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. Fresh offline native schema/raw surface/alias/serializer probes and exact isolated runner authorization statements. No full runner, API, browser, provider, downstream state update, prescription or hardware execution. Repository tests and audit narratives are not correctness oracles.

## Verdict: WB02 is partially repaired

Keep the remaining work in **one typed capability/restriction completion within Batch A**, spanning producer support, native fields and canonical serialization. The candidate fixes several important cases, but does not yet establish the claimed intersection across all carriers and ceilings.

### Independently verified repairs and positive controls

- Native schema defaults are False for both action permissions. Parent defaults are True.
- String `false` denies native and serialized state-update permission; missing serializer permissions default False. Parent retains the corresponding permissive behavior.
- Conflicting snake-case True and camel-case False permission flags now resolve False in the serializer.
- Native ASMAE ingress carries all eight tested restriction spellings into raw and alias display gates. Canonical snake-case controls and earlier default qualified display remain functional.
- A native non-ASMAE `SurfaceArtifact` (`NDVI_CLEAN`) with explicit True attributes and declared `PRESCRIPTION_DRIVER` retains both permissions in canonical serialization. An explicit `STATE_UPDATE` control retains state-update permission and denies prescription; an explicit `DIAGNOSTIC` control denies both. These are schema/serialization controls, not proof that this authored NDVI fixture is eligible for a real prescription.
- Unsupported display remains denied in the isolated runner gate; ordinary aliases retain False action permissions.

## Residual mechanisms in the same contract

### 1. Native state support is still not bound into action permission

With a genuine indirect ledger whose runtime ceiling is DIAGNOSTIC and metadata `state_update_allowed=True`, native generation produces a raw vigor surface with `diagnostic_only=True`, `management_zone_eligible=False`, yet `state_update_allowed=True`. Canonical serialization retains True. Missing-ledger Unsupported input produces the same True permission, although the display gate correctly denies it with `missing_state_support:vigor`.

The native provenance copies support labels at `surfaces/asmae.py:1620–1625` but does not bind the ledger's authority ceiling into the permission calculation. The new local check at `1810–1832` reads `provenance['authority_ceiling']`, often absent, and does not intersect current support class or the established scientific authority gate. Consequently the new check is not the claimed per-state support/permission intersection. Native bad numeric metadata such as NaN also becomes True through `bool(val)`.

This is an inconsistent published artifact contract, not demonstrated downstream state mutation. The separate native authority gate is False in the controlled fixtures, and Unsupported rendering remains denied.

### 2. The new strict parser and ceiling handling are incomplete

`surface_contract.py:70–83` accepts every numeric scalar via truthiness. Explicit permission values NaN, Infinity, -1 and 2 all serialize as True. Valid 0/1 and False/True controls establish that the native serializer is executing; no undefined JSON file or provider input is required.

`surface_contract.py:259–266` uses `str(ceiling).upper()` and checks only selected names. Actual `AuthorityCeiling.VISUALIZATION`, MONITORING_ONLY, DIAGNOSTIC and STATE_UPDATE enum objects do not normalize through `.value`; the string becomes `AUTHORITYCEILING.*` and bypasses restrictions. Their ordinary lowercase values/uppercase names correctly restrict the intended capabilities. TRAINING_EXPORT in enum, value and name encodings still permits prescription driving, and a declared `UNKNOWN_CAPABILITY` retains both explicit True permissions.

The matrix includes all seven actual enum members, their value/name encodings and three unknown/absent variants (24 cases). Unknown declared ceilings require a fail-closed policy. Absent ceilings for compatibility producers should have an explicit migration/grant rule; this report does not treat every legacy missing field as evidence of an exploitable authorization path.

### 3. First-carrier selection still defeats monotone restriction/ceiling intersection

The serializer gathers restriction eligibility using `_surface_value` (`217–233`), which selects the first available carrier, rather than the complete union. A surface attribute `block_reasons=[]` masks provenance `['local_support_revoked']`. Likewise provenance `block_reasons=[]` masks `blockReasons=['local_support_revoked']`. Both controlled documents serialize True action permissions, while the later complete union (`317–323`) correctly writes `block_reasons=['local_support_revoked']` into the same document. The output is therefore internally contradictory.

Ceilings have the same issue: an attribute `PRESCRIPTION_DRIVER` masks provenance DIAGNOSTIC, and a snake-case permissive ceiling masks a camel-case DIAGNOSTIC ceiling. Native single-carrier denial controls work. This is a remaining inherited contract weakness exposed across the broader matrix, not a reason to reopen every already-closed original dual-carrier display case.

## Coherent completion, not separate micro-fixes

1. Normalize booleans, actual enum `.value`, known names and declared unknown values once at admission. Accept only the documented finite/binary compatibility representations; malformed numeric permission is a denial plus diagnostic.
2. Compute the union of every supported restriction carrier **before** calculating permissions; use that exact canonical union for both enforcement and serialization. Keep advisory warnings distinct from active restriction semantics where the contract requires it.
3. Normalize all current static/runtime/metadata ceiling carriers and intersect their capability sets, rather than selecting one. Explicit current denial must not be masked by attributes, alias spelling or historical support.
4. Bind the normalized per-state scientific support result to native raw permission fields before constructor creation. Derive aliases, canonical JSON and export receipts from the same result. Keep inspection, scouting, training, state update and prescription capabilities distinct.
5. Preserve actual positive grants and existing qualified display controls. No serializer or native constructor should recreate permissions that a producer denied.

Acceptance must cover raw/alias/serializer parity, Unsupported and diagnostic support with a requested True grant, all actual enums/value/name encodings, TRAINING_EXPORT, declared unknown ceilings, non-finite/nonbinary permissions, competing restriction/ceiling carriers and explicit non-ASMAE positive grants. Run the integrated A/B cohort gate after these connected changes; do not split the residuals into one review cycle per spelling.

## Receipts and replay

Commands from workspace:

```bash
python review-ab-e85cfd2/authority/probes.py
python review-ab-e85cfd2/authority/probes.py --parent
```

Fresh candidate: **23 observation assertions**, parent: **13**, all reproduced. Each snapshot exercises 14 native raw/alias carrier cases, 11 serializer cases, 24 ceiling encodings, eight permission scalars and three explicit native non-ASMAE controls. Observation success includes present defects and parent counterexamples; it is not acceptance of those contracts. Both 1,087-file corpora are checked against their exact Git tree and remain unchanged. The four core cited production module receipts and exact runner AST ranges/hashes are in each result file.

Plan trace: AB-ARC-005 factored authority, AB-ARC-006 bounded degradation and AB-L10-001 canonical projection parity. This bounded verification closes no package FA milestone.


---

# Specialist appendix: Catalog and availability

# Integrated A/B catalog, validity and availability verification

Candidate `e85cfd224f8a731e2959648ce28450e27782188f`, exact parent `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. Fresh native offline probes plus the exact isolated inventory/authorization AST; no full runner, provider, API/browser, field hardware or forecast loop. Repository tests and audit claims are not used as the correctness oracle.

## Disposition

**Original examples are repaired; the catalog/availability contract remains partially complete.** Keep the remaining work inside the same A/B cohort. There is no need for separate per-scalar repair/review cycles.

### Verified repairs and positive controls

- All thirteen dedicated types and state/product identities remain registered.
- All thirteen out-of-upper-bound native raster controls now trigger INV-2. The parent's eight missing fractional-state checks are repaired. The native generator plus actual invariant function execute, so this is not merely table inspection.
- LAI legend coverage now reaches 8.0; valid LAI 7.0–7.8 survives the scientific invariant.
- Metadata-only native generation with no raster and no scalar still returns structural all-None objects, but the exact inventory block now reports **missing**, and manifest state modes are **disabled**. The parent called these plot-level and enabled them.
- Qualified valid rasters still enable their modes. A real finite scalar carrier with values 0.0 or 0.5 still permits plot-level inspection, preserving legitimate zero.
- Terminal no-data output retains thirteen explicit missing entries.

These closures should remain closed in the claim register. They are distinct from the residual general qualification below.

## One residual catalog/availability correction group

### 1. New availability gate is not a finite-real or genuine-scalar validator

`products/manifest.py:271–283` and `runner.py:3907–3916` count any non-None pixel except a float NaN/Inf as valid. Booleans and arbitrary strings therefore count as finite pixels. Fresh `False`, `True`, and string-value SurfaceArtifact fixtures enable the vigor mode; ordinary physical numeric zero is the positive control. This is a native surface-carrier validation counterexample, not evidence that the clipped ASMAE engine normally emits those malformed values.

The scalar branch uses:

```python
has_scalar = bool(prov.get("has_scalar_estimate") or prov.get("scalar_value") is not None)
```

With an all-None raster, each of the following still enables its mode and receives `plot_level_only`:

- `has_scalar_estimate=True` without an actual scalar value/reference;
- `has_scalar_estimate="false"`;
- `scalar_value=False`;
- NaN, positive Infinity, or `"not-an-estimate"` as scalar value.

An absent scalar or explicit None correctly stays missing/disabled in the candidate. Numeric 0.0 and 0.5 correctly remain available. The intended distinction is therefore not raster-only blocking: require a qualified scalar estimate/artifact and preserve legitimate scalar-only inspection. A declaration flag is not equivalent to a finite numerical estimate or an immutable artifact containing one. Normal producer incidence of malformed/flag-only carriers was not established.

Availability metadata is not the final render authorization. No overlay bypass, state update, prescription or browser incident is inferred from an enabled mode.

### 2. All thirteen range entries are present, but the invariant still does not qualify numerical types

`invariants.py:123–143` compares values only with `<` and `>`. It does not reject non-finite or boolean values:

- NaN produces no INV-2 violation;
- False and True produce no INV-2 violation;
- an arbitrary string raises TypeError rather than returning a local invalid-state qualification.

This behavior exists in both snapshots; the A/B expansion fixes the missing eight domains but does not complete the promised finite/nonboolean boundary matrix. A normal finite out-of-domain value is now detected in every state, and valid LAI 7–7.8 remains valid. Treat scientific admissible domain, numerical qualification and display range as separate parts of the same state specification. Never clamp an invalid scientific value merely to satisfy visualization limits.

### 3. Catalog and temporal availability remain separate producer/consumer conventions

A lexical source-inventory check finds `CANONICAL_13_STATE_CATALOG`, `CANONICAL_STATE_TO_SURFACE`, and `get_state_catalog_entry` only in the defining module and package exports. Runtime validation and manifests still use independent manually expanded tables. The immediate eight-state/LAI examples are fixed, but the canonical catalog is still not their source of truth. This is an architectural completion item for the existing cohort, not a newly discovered numerical failure.

A separate controlled temporal check uses the actual `build_state_support_ledger([])` producer, native temporal surface generation and the exact authorization block. Its default prior status leaves phenology denied with `missing_state_support:phenology_progress`, while memory's prior state is permitted. Explicit `model_propagated` or `temporally_conditioned` controls permit both. This reproduces the existing model-receipt/status seam in candidate and parent. It is not a full weather-forcing/forecast execution and does not establish failure of a particular real plot. Genuine model propagation should emit its own receipt/status; do not invent observations to force a display pass.

## Cohort completion steps

1. Define one finite nonboolean numeric qualifier and an explicit scalar-artifact/estimate contract. Normalize and validate scalar support once, then share it between manifest, successful inventory and terminal publication. Preserve physical zero and finite scalar-only inspection.
2. Keep registered/materialized/inspectable/plot-state/pixel-authorized statuses separate. Missing values cannot acquire availability through an unqualified flag, string or boolean. Unsupported/revoked scientific support remains separate from object presence.
3. Make the state specification provide admissible domain and visualization metadata. Generate or mechanically validate all thirteen invariant/legend/mode tables from it. Apply finite/type/domain validation locally, preserving valid siblings and diagnostic reasons.
4. Carry genuine temporal/model receipts from producer to normalized ledger and state-specific gate. Preserve model identity and authority ceilings rather than synthesizing accepted sensor counts.
5. Complete one acceptance matrix for all thirteen states and every relevant status/number form. This is one connected A/B contract repair, with no new micro-PR requirement.

## Fresh evidence

`probes.py` executes **30 observation assertions per snapshot**; all reproduce. `temporal-probes.py` executes **two observation assertions per snapshot**; all reproduce. Successful assertions include documenting the residual defects and exact-parent counterexamples, not declaring all scientific contracts acceptable.

Replay from the review directory:

```bash
python catalog/probes.py
python catalog/probes.py --parent
python catalog/temporal-probes.py
python catalog/temporal-probes.py --parent
```

The main script calls native generator, manifest, invariant, canonical serializer and terminal functions, with the exact isolated inventory statements (`runner.py:3855–4042` in candidate). The temporal script executes exact top-level helper/authorization statements only. Both source corpora's 1,087 selected files match Git blob/SHA-256 receipts and are unchanged. Source manifests are retained; `source-receipts.json` lists the directly relevant modules. All JSON is strict, with authored non-finite inputs represented explicitly as nonfinite tokens.

Governing intent: AB-L10-001 qualified canonical projection, AB-ARC-006 bounded degradation, AB-ARC-005 factored authority, and AB-ASM-016 local validity. Primary ownership remains T09/F36/F38/T11. All 52 FA milestones stay open. No production edits or Git mutation occurred.


---

# Specialist appendix: Native spatial runtime and validity

# Integrated A/B spatial verification — e85cfd2 versus d59c9bd

## Verdict

**Hold the integrated spatial acceptance: an introduced P1 binding failure prevents ordinary native microzone conversion, and a second lexical binding failure affects uncertainty-bearing output assembly.** Keep both in the same Batch B correction, alongside the remaining mask/shape continuity work. The native SIRE identity-nodata normalization is repaired and should be retained.

Fresh replay: **15 Python observations plus six pure TypeScript preflight observations**, all reproduced. Observation success includes exact-parent counterexamples and current failures; it is not a pass verdict on the scientific contract. Both source corpora remain unchanged. No repository test/audit is a correctness oracle, and no full engine/runner/provider/API/browser/hardware execution occurs.

## SP-E85-01 — P1 introduced NumPy binding failures in native conversion and assembly

### Ordinary conversion now raises NameError

The candidate adds `np.isfinite(val)` to `_microzone_to_grid` at `layer05_asmae/engine.py:3309–3310`. The module has no `import numpy as np` at module scope. Its existing NumPy imports are local to other methods (`1073`, `1768`, and `2174`); they do not bind `np` for this converter.

The probe imports the production engine module normally, creates an instance with `ASMAEEngine.__new__` to avoid initialization, and invokes the unchanged native method with ordinary authored input:

```python
engine._microzone_to_grid({'mz_000_000': [0.0] * 13}, None)
```

Candidate result: **NameError: name 'np' is not defined**. Exact-parent result: returns thirteen 1×1 zero maps. The candidate module's global dictionary has no `np`. This uses finite numeric values and a normal microzone ID, without sparse or malformed evidence. Native EnKF final statistics use microzone-keyed means/sigmas (`assimilation/filter.py:427–428`), matching this converter entry shape; a pre-keyed state-grid control bypasses the converter loop and returns normally.

### A module-level NumPy import alone will not fix assembly

`_assemble_output` now refers to `np.isfinite` at lines `1969` and `1985`, before its existing local `import numpy as np` at `2174`. Python determines local bindings lexically, so that later import makes `np` local throughout the function. Uncertainty-bearing assembly therefore raises **UnboundLocalError: cannot access local variable 'np' where it is not associated with a value** before reaching the import.

To establish this without running the full assembly method, the probe compiles the exact production prefix through posterior concentration and retains the original later NumPy import after an inserted return. The import is unreachable but preserves the original function's lexical-local binding. With ordinary finite state-keyed grids (bypassing the converter failure), candidate prefix raises UnboundLocalError; exact-parent prefix returns. `candidate-results.json.assembly_prefix_receipt` records the prefix and retained-import lines. No provider, persistence or late assembly branch executes.

**Correction:** bind NumPy consistently before first use in each native method, or use existing `math.isfinite` where appropriate; remove/relocate the late local shadowing import. Do not treat adding one module import as sufficient. Add native-method entry checks that do not inject `np` into the production module or compile the aggregate as a module-level fragment.

## Changes that work, with explicit diagnostic limits

### SIRE identity-nodata cleaning: verified repaired

Native `_align_asmae_grid_to_target` now cleans explicit `-9999` to None before the same-grid return (`surfaces/asmae.py:549–591`). Candidate identity and nearest-neighbor resampling preserve valid physical zero and mask the sentinel; parent identity retains -9999 while its resampling already removes it.

Native surface construction no longer obtains apparent nonuniform grounding from that sentinel: candidate fixture is UNIFORM, exact parent RASTER_GROUNDED. A genuinely all-zero control remains UNIFORM. This establishes native alignment/grounding behavior, not a full-runner/browser authorization receipt.

### Mean/sigma holes and concentration: intended logic verified only after supplying the missing binding in scratch

The candidate changes every unassigned mean/sigma cell to None and avoids generating aggregate concentration at cells without valid uncertainty (`engine.py:1960–1990,3301`). Because the native converter currently fails, the probe executes the exact converter in a deliberately explicit scratch namespace containing NumPy, and executes the exact aggregate block separately with NumPy supplied. This is a diagnostic control, **not successful execution of the unmodified native candidate**.

Under that narrowly stated control, both holes in a sparse 2×2 fixture remain None across all thirteen means/sigmas, legitimate supported zero stays zero, and missing uncertainty/concentration stays None rather than the parent's concentration 1.0. Retain this intended fix while repairing the native bindings.

## SP-E85-02 — P2 integrated spatial-validity work remains incomplete

This is the same Batch B missingness/grid contract, not a set of new one-line PRs.

1. **Scalar support maps still fabricate zero for absent support.** `_microzone_scalar_to_grid` at `engine.py:1804–1835` remains unchanged: holes are initialized to 0.0 and explicit None becomes 0.0. It is used for retrovalidation/BMA and biophysical support maps. This omission was in the planned whole-grid acceptance matrix. Genuine zero and missing support still cannot be distinguished there.
2. **IDs and canonical shape remain unqualified.** The converter still infers shape from maximum parsed IDs and permits Python negative indexing. In an explicit scratch-binding control, `mz_-1_-1` overwrites the valid `(0,0)` cell with 0.9. This malformed authored input is not established as normal graph output; the standard graph is rectangular. It remains an unimplemented planned boundary validation.
3. **Bilinear handling does not preserve masked supported endpoints.** Native `_bilinear_resample` converts None to NaN, then weighted sums propagate `NaN * 0`. For `[[0,None],[None,0.8]] → 3×3`, the supported top-left physical zero becomes missing; only the bottom-right value stays finite. A fully supported control yields nine finite cells. This function is unchanged, but the new None output activates the intended missingness convention across its quick-visual resampling caller (`2255–2270`). Ordinary current candidate conversion aborts earlier; this is a demonstrated integration hazard after repairing the bindings, not a claim of a completed native run losing a field map.
4. **Frontend preflight remains the parent contract.** Exact pure TypeScript helper bodies still accept metric display bounds, 99×99 metadata beside 2×2 values, all-null support and a shifted affine mask. A valid control passes and ragged input rejects. `render-materialization.ts:109–183` is unchanged and these were explicitly included in the original Batch B plan. The probe does not show actual browser rendering or a backend authorization bypass.

## One completion gate for Batch B

Repair native bindings, then verify the entire same interface once:

- Call native converter and native assembly-prefix/scoped output builder without test-only globals. Ordinary fully supported numeric inputs must return.
- Run all thirteen means/sigmas through sparse holes and physical-zero controls; uncertainty/concentration remain unavailable at holes.
- Apply one validity/shape policy to scalar support maps, not only latent arrays. Use canonical graph dimensions and validated IDs.
- Make same-grid, resampling, reprojection and quick-visual paths preserve values and masks consistently; valid endpoint zero cannot disappear because a zero-weight neighbor is missing.
- Carry mask/shape contracts through L1/SIRE/cache/export and browser preflight; coordinate with the cache/export lane so the same receipt is checked rather than re-created.
- Retain the now-correct native identity-nodata/grounding controls.

This is a single integrated spatial correction within the existing A/B cohort. It does not require another planning stage or reopening the earlier covariance/checked-square findings. Package FA milestones remain open. R3 ownership is AB-L10-001 qualified grid/mask/resolution projection, AB-ARC-006 bounded degradation, and AB-ASM-016 local uncertainty/validity; implementation ownership F38/T11/T09 with F36 support parity.

## Reproduction

```bash
python review-ab-e85cfd2/spatial/probes.py
node review-ab-e85cfd2/spatial/frontend-probes.mjs
```

Python invokes exact candidate/parent subprocesses. Results and source SHA-256/Git blobs are recorded separately. Native engine import and converter calls do not initialize/run the engine. Prefix/aggregate extraction and explicit scratch NumPy controls are labelled in the result JSON; they must not be advertised as a full pipeline test. All scientific inputs are authored offline fixtures, with network disabled.


---

# Specialist appendix: Cache transactions and scientific policy

# Cache transaction, masks and scientific-policy compatibility

Candidate `e85cfd224f8a731e2959648ce28450e27782188f`; exact parent `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. **Partial closure: normal generation publication and explicit-mask persistence are repaired, with one coherent artifact-contract completion still required.** Native offline probes freshly reproduce sixteen grouped observations. Repository tests/audits are not used as correctness proof.

## Repairs verified

- Normal full-cache save/read works on candidate and parent.
- Candidate generation addressing preserves old JSON and old NPZ bytes when a replacement fails before JSON commit. The prior committed generation remains readable; the parent reproduces the previous unreadable-cache counterexample.
- An injected failure while building/hashing the new artifact manifest also preserves the prior candidate commit.
- Explicit two-dimensional MaskedArray masks roundtrip correctly: masked hidden payload77 becomes None, physical zero stays zero, and no mask member becomes a fake state feature. Parent exposes77, reproducing the old defect.
- Plain None/NaN array encodings normalize to None correctly; finite controls remain unchanged.
- A manually created genuine legacy fixed-path NPZ and original-layout member manifest remain readable. Tampered bytes reject on both snapshots.
- Two independent writer interpreter processes publish eight candidate generations each while a separate reader performs90 loads on the same cache identity. All observed hits are internally consistent. Initial clean misses and the number of distinct generations observed vary with scheduling; this is a bounded process stress control, not universal crash durability proof.

## Required completion within the same artifact delivery

### 1. New scalar-nomask MaskedArray regression — P2

At `layer05_asmae/cache.py:516–524`, the writer takes `np.asarray(grid.mask)` directly. An ordinary `np.ma.array([[0,.1],[.2,.3]])` has scalar nomask=False. `ascontiguousarray` stores that mask as a one-dimensional `(1,)` NPZ member; the manifest builder rejects it at566–567 as non-2D. The native candidate cache returns False for this valid unmasked array type, while the exact parent saves successfully. The previously committed candidate generation remains safe; this is a new accepted-input availability regression.

Use shape-normalized `np.ma.getmaskarray` (or deliberately omit an all-false mask) and preserve mask/data shape parity. Apply the same numeric dtype policy to masked and plain inputs.

### 2. Mask association validation is incomplete — P2 contract boundary

The validated reader checks each member against its own declared shape/hash, but never requires the mask's shape to equal its target data or verifies a complete typed pairing. Lines656–665 apply masks only over `min(data_shape, mask_shape)`. A manifest-consistent2×2 data member and1×1 mask are accepted, leaving the rest of the data, including77, visible. This fixture is deliberately authored; normal writer generation of an undersized2D mask or an external exploit was not established. The compatibility loader repeats the clipping policy.

Require bool dtype, exact data/mask shape equality, a unique existing target, recognized member roles/version and no orphan/reserved-prefix collision. Reject inconsistent whole artifacts rather than truncating masks. Preserve strict member/hash checks already repaired.

### 3. Storage backward compatibility replays pre-repair scientific policy — P1 scientific migration boundary

A fresh two-snapshot bridge proves this beyond source inspection:

1. The actual exact-parent ledger builder consumes an authored accepted real NDVI→vigor report in the format emitted by the old H_t branch. It creates direct count1, relationshipdirect and field-approval eligibilityTrue.
2. Native parent cache serialization writes the ordinary legacy JSON/NPZ transaction.
3. Candidate computes the **identical input cache key** (`0a3eec0b8f796cec2728c1341a208a095a0e2063bf70a82288b2e9a4d613d066`) and native deserialization accepts the old cache.
4. Candidate native feature export retains `status=real`, `source=layer05_enkf_direct`, confidence/weight0.90 and `usable_for_field_approval=True`. Candidate native SIRE classification returns Observed/directTrue; its management eligibility remainsFalse.

Thus scientific-label fixes can be bypassed by valid pre-policy caches. This is not a checksum bypass: every old artifact is legitimate under its prior contract. No full runner, production field execution or physical action occurred. `cache.py:68–71,318–327` retains unchanged scientific/cache versions, and the new legacy reader does not requalify the old support proof.

Separate storage-format compatibility from scientific-policy compatibility. Version the state-support/operator/descriptor policy in the execution cache identity, or explicitly migrate/requalify old support receipts with provenance. Legacy files may remain parsable for archive/research without being silently reused as current Observed/field-approved state evidence. Add the exact parent-write/current-read bridge as an integrated acceptance control.

## Additional hardening qualifications

- JSON diagnostics containing NaN still serialize to raw `NaN` (`cache.py:451,765`) and return successful publication. Raster NaN correctly becomes None; non-raster metadata has no equivalent strict normalization. Normalize exact JSON/hash representation and use strict finite JSON together. Do not add `allow_nan=False` without preparing the payload.
- Injecting an exception after the native JSON writer switches the manifest causes lines779–787 to delete the newly referenced NPZ, leaving an unreadable manifest. This is a post-commit ambiguity/recovery fixture; the current helper has no directory fsync, and normal incidence of an exception after its replace is unestablished. Do not label it a reproduced ordinary disk failure. Cleanup should inspect committed references/linearization before deleting candidates, especially when adding directory-fsync durability handling.
- UUID generations are unique and preserve prior artifacts. Content-stable retry reuse and unreferenced-generation garbage collection are not implemented/proved; distinguish those remaining design contracts from the normal transaction repair.

## One completion scope and acceptance gate

Keep these in the current artifact-contract cohort: (a) normalized mask writer plus exact reader pairing; (b) strict JSON/hash normalization; (c) scientific-policy cache invalidation/requalification; (d) commit-aware cleanup/durability semantics. Do not launch a separate residual review for every helper.

The acceptance matrix includes scalar nomask, explicit2D all-false/all-true/partial masks, finite zero, None/NaN, shape/role/member mismatch, immutable generation retries, original legacy layout, old-policy cache migration, injected before/after commit boundaries, byte/member tampering and real two-process writer/reader controls. Old valid scientific generations must remain readable under their declared role, without acquiring current policy authority by format compatibility alone.

## Reproduction and evidence

Run `python review-ab-e85cfd2/cache/probes.py` from the reconstructed workspace. The script invokes isolated candidate/parent subprocesses, temporary native cache directories, the legacy-policy bridge and three real concurrent processes. Sixteen observation assertions reproduce; successes include documenting defects. Exact cache module Git blobs/SHA256 and unchanged-byte checks are in candidate/parent results. JSON is strict in the review outputs; no production source or runtime store is changed. The scientific bridge uses actual builders/classifiers and authored report declarations, not acquired field observations.


---

# Specialist appendix: Scientific export and L10 publication

# Integrated A/B scientific export and L10 transaction verification

Candidate: `e85cfd224f8a731e2959648ce28450e27782188f`. Exact parent: `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. Scope: native raster compatibility export, canonical surface comparison, ordinary native ASMAE construction, and exact isolated L10 cache writer/sanitizer. No full runner, provider, API, browser, repository test, GIS file or hardware was executed. No production source or Git was changed.

Fresh replay: `python review-ab-e85cfd2/export/probes.py` and the same command with `--parent`. **18 candidate observations and nine exact-parent observations reproduce.** Counts include current residuals and positive controls; zero exits do not mean full export acceptance.

## Verified repair progress

All thirteen dedicated raw state products project through the native compatibility exporter. On rich controls with explicit dataclass metadata, the candidate now preserves grid specification, confidence grid, scalar uncertainty, observed/inferred masks, False action permissions and all three resolution fields. Physical zero and None values remain unchanged, and finite valid-pixel count is correct for those controls. The parent lacks the added scientific fields, so the field-presence expansion is independently verified.

The canonical serializer now denies the controlled raw True permissions beside diagnostic/revoked provenance; the parent canonically returned True in this particular fixture. This improvement is recorded separately from the remaining compatibility-export disagreement below.

## E85-EXPORT-01 — P2: field presence is repaired, canonical receipt parity is still incomplete

`layer10_sire/products/export.py:75–154` reconstructs its own metadata instead of using `serialize_surface_artifact`. The new `canonical_metadata` field is another manually assembled subset, not the result of the canonical serializer. Native probes expose consequential differences:

1. **Ordinary ASMAE construction loses confidence in compatibility export.** Native `generate_asmae_surfaces` puts confidence in provenance (`surfaces/asmae.py:1645`) and leaves the dataclass confidence attribute unset. The canonical serializer correctly resolves provenance confidence (`surface_contract.py:307`). The exporter reads only `s.confidence` (`products/export.py:143`). In the authored ordinary aligned thirteen-state fixture, all thirteen canonical surfaces have confidence **0.8**, while all thirteen compatibility entries contain **None**. This is a native builder→export path, not only a specially enriched SurfaceArtifact.
2. **Canonical fallback masks and grid uncertainty do not survive.** A SurfaceArtifact carrying confidence, observed/inferred masks and a sigma grid in provenance is preserved by the canonical serializer. The exporter ignores provenance masks/confidence and tries `float(provenance['uncertainty'])` (`export.py:103–108`), silently returning uncertainty None for a legitimate grid-valued canonical receipt. Scalar-uncertainty controls do pass. The sigma-grid case establishes an accepted canonical-boundary mismatch; this review does not claim every normal SIRE metadata producer emits grid uncertainty.
3. **Canonical restrictions and permission decisions are bypassed by the compatibility projection.** A raw surface with explicit True attributes and `authority_ceiling='DIAGNOSTIC'`/`support_revoked` provenance serializes canonically with both permissions False and a top-level block reason. The compatibility entry copies raw True attributes and an empty attribute block list (`export.py:119–121,149–151`). Provenance itself remains present, so the information is not entirely destroyed; its canonical top-level capability fields disagree. No consuming privilege escalation, state update or physical action is established.
4. **Validity is still merely `v is not None`.** An authored NaN input is counted as valid and its statistics contain non-finite values (`export.py:80–93`). Strict JSON serialization then fails. This is a native export-boundary counterexample; normal field incidence is unestablished. The runner actively invokes export at `runner.py:3646–3655` and suppresses exporter exceptions, but no full-runner failure was executed here.

**Disposition:** the original nine-field omission is substantially repaired at the schema/explicit-attribute level. Full scientific receipt parity is **partial**, with one connected export-projection correction still required. These are extensions of WB05's existing canonical-receipt work, not separate micro-patch tickets.

**Required correction:** derive compatibility scientific fields from the actual canonical serialized receipt and the shared qualified raster-validity contract. Preserve scalar or raster uncertainty under an explicit typed representation; resolve provenance fallbacks once; keep restrictions/permissions exactly equal across canonical and compatibility forms. Compute values, valid masks and statistics from finite, nonboolean, supported cells; preserve physical zero and explicit unknown. Do not depend on a later consumer to rediscover a denial from nested provenance.

## E85-EXPORT-02 — P2: equivalent L10 cache still destroys the previous committed generation on failure

The prior integrated plan explicitly included auditing and repairing the equivalent L10 JSON/NPZ transaction within Batch B. That path remains fixed-address and destructive in this candidate, independently of the ASMAE cache improvements reviewed by the cache lane.

Fresh controlled execution extracts the exact `save_layer10_to_cache` and `sanitize_surface_values` functions from the production runner AST. An admitted-publication validator stub accepts an authored in-memory fixture; this deliberately avoids full runner import/execution and does not claim publication-validator acceptance. Files are written only in a lane-local temporary directory.

The first cache write succeeds, creates both JSON and NPZ, and preserves the supported physical-zero control. The second write changes values. Injecting failure at the JSON rename makes the function return zero and **deletes both the previously committed JSON path and NPZ path**. The exact parent behaves identically. Relevant source:

- `runner.py:1457–1458`: fixed per-key JSON and NPZ paths.
- `runner.py:1518–1522`: replaces NPZ before publishing JSON.
- `runner.py:1539–1544`: failure cleanup removes final NPZ and final JSON, rather than only uncommitted candidate files.

**Disposition:** current inherited Batch-B coverage gap, not a regression introduced by the new generation-addressed ASMAE cache. It prevents the broader scientific publication durability claim from being marked complete.

**Required correction:** apply the same immutable generation/addressed-artifact plus atomic manifest-switch discipline to L10. Never overwrite or delete a referenced committed generation during candidate failure cleanup. Preserve live object restoration already implemented in the detachment finally block. Update the corresponding L10 reader and compatibility reconstruction with versioned references, checksums and explicit member roles. Garbage collection must only remove unreferenced generations.

## One connected acceptance extension for the existing A/B cohort

Do not open an independent follow-up cycle for each item. Complete the artifact-projection/durability work and run this matrix once:

- Native ASMAE generation of all thirteen states → canonical serializer → compatibility entry: confidence, scalar/grid sigma, masks, restrictions and capability fields agree exactly.
- Explicit dataclass metadata and provenance fallback carriers produce equivalent receipts. False/diagnostic/revoked canonical decisions remain identical in compatibility forms; qualified explicit positive grants remain intact.
- None, NaN, infinity, malformed/boolean scalars and physical zero obey the shared value/mask policy, with strict finite JSON statistics and no fake valid support.
- Both ASMAE and L10 cache writers: valid first commit, changed retry, injected artifact/hash/JSON/fsync failure, last-generation readability, idempotent retry, concurrent reader/writer and safe unreferenced cleanup.
- Preserve existing identifiers, source/display grid proof, legacy compatibility fields and live output object restoration.

Source receipts in results verify five production modules against pinned Git blobs and SHA-256 digests. All 1,087 selected source file bytes remain unchanged. The generic GeoTIFF/COG publisher and browser receipts remain later delivery scope; this review does not reopen the previously documented generic GIS helper qualification or perform a real GDAL roundtrip. All package FA milestones remain open.
