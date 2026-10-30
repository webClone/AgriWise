# AgriBrain consolidated session and work-in-progress audit

27 October 2026 · Review branch `feat/f36-t09-asmae-13-state-publication` · Candidate **`220953f4a8436e394a091d375b4fe6388648448b`**.

## Decision

**The recent sessions delivered broader, useful implementation work, but the new four-owner cohort does not yet pass its connected software exit gate.** Preserve the accepted ASMAE A+B closures at `563c6fa`. Repair the five current contract failures below as one parallel owner batch, then perform one integrated exit review. Do not restart the entire 52-package audit after each edit.

The review covers the published artifacts and code behind the sessions, not inaccessible chat transcripts. GitHub exposes 21 commits between main and the candidate; eight follow `570341c`. Six independent review lanes assessed the recent connected paths: execution, durable evidence, EO, temporal/hydraulic forcing, ASMAE numerical semantics, and plan reconciliation. The root replayed six authored probe scripts; all completed successfully **and reproduced the documented failing contracts**. Their exit code zero does not mean production acceptance passed.

No production source, Git branch/ref, acceptance checkbox or monograph was changed. No merge or field hardware operation occurred. These results are bounded software evidence, not a whole-repository or empirical scientific certification.

## 1. What the sessions actually delivered

| Published revision | Work delivered or claimed | Current disposition |
|---|---|---|
| `563c6fa` | Typed uncertainty consumer, canonical bare-soil support, v3 cache migration | Prior independent bounded closure retained. Do not reopen those three findings. |
| `570341c` | Additional covariance, V90 identity, rollback and missing-quality hardening | Superseded by later numerical and resolver fixes; count the current contract once. |
| `aaf3895`, `730b9fe` | Numerical scale refinements, HT/proxy rollback, V90 conflict denial | Current ordinary controls pass; extreme finite covariance remains a defensive follow-up. |
| `f041a8f` | Update walkthrough revision reference | Documentation-only; no separate implementation credit. |
| `6f60a57` | Broader four-owner cohort: admission, weather, hydrology, acquisition, execution, storage | Concrete expansion beyond the publication workstream. Not proof all 16 packages are complete. |
| `3687d65`, `df3ead6` | Physical STOP evidence, multi-worker durability, issuance eligibility, EO tensor/provenance qualification | Several positive controls pass; current counterexamples remain in the same connected contracts. |
| `87f33ff` | Advisory locks, corruption reporting, STOP evidence, lookback and EO fallback repairs | Retained where independently exercised. Earlier weaker mechanisms in walkthroughs are historical. |
| `220953f` | CUSTOM-vendor simulation exception removed, correlated receipt checks, EO restriction propagation | These specific improvements exist, but do not fully close STOP proof or EO qualification. |

The full 21-commit lineage and compare metadata are retained in the evidence bundle. Earlier review decisions are historical evidence with their own pins, not a claim that every old probe was rerun here. Repository tests and audit narratives were not used as correctness oracles. Author-reported test totals were not independently rerun or summed into progress.

## 2. Current branch versus merged delivery

| Ref observed during this audit | SHA | Meaning |
|---|---|---|
| `main` | `90ab701714554c7b786bba4ac6b19259e77279ce` | The current reviewed cohort is not merged here. |
| Publication / four-owner review branch | `220953f4a8436e394a091d375b4fe6388648448b` | 21 commits ahead of main, zero behind; 72 changed paths in aggregate. |
| Independent F02 branch | `075f19d318db6fa86d5988c2cabcb680dc17702e` | Diverged from review branch: one unique F02 commit is not an ancestor of this candidate. Similar fixes on another branch do not prove full branch integration. |
| Independent F01 downstream branch | `e0e5b1eabee73e8b17ce6849f4a23c05b302501a` | Separate branch identity; do not silently count all of its changes as merged into current main. |

Pushed, reviewed, integrated on a branch, and merged to main are four different delivery states. The current status ledger needs to record them separately. The review branch now contains substantial foundation/execution/acquisition work despite retaining its ASMAE name; that naming is not a defect, but its scope needs a current consolidated release note.

## 3. Five connected failures to repair together

### CS-01 — P1: Physical STOP evidence is still accepted inconsistently

There are three linked mechanisms under one execution owner. They share the same invariant: transport acceptance or a weak receipt must not certify cessation and release ownership.

**Contradictory HTTP evidence:** a response with `status='RUNNING'`, `is_running=False`, and zero flow is accepted as confirmed stopped. The same happens with `RUNNING` plus `confirmed_stopped=True`. An invalid NaN flow can also be bypassed by a stopped status. Native cancellation with the actual dispatcher, registry, SafetyMonitor and SharedQuotaStore publishes `CANCELLED`, creates a stopped receipt, and removes reservation, active tracking and watchdog. A consistent STOPPED/zero control is accepted; STOPPED/positive-flow is correctly rejected.

**Late START fencing:** an authored controller transport holds START in flight. The first transport-only STOP correctly enters `STOP_PENDING_CONFIRMATION`. START later finishes and the primitive sends a fence STOP. That branch checks `fence_res.success` rather than affirmative physical cessation, then sets ONLINE and clears the active command despite the controlled controller still running. This proves the actuator-level ownership loss. It is not presented as a separately proven whole-submit quota-release sequence.

**Receipt trust qualification:** `confirm_stop` rejects explicit `authenticated=False`, but missing authentication is accepted when the supplied source string is allowlisted. The native local boundary can clear ownership on this weaker receipt. This is a P2 trust-contract qualification within the same owner repair: an externally reachable exploit or independent network authentication bypass was not established. A caller-supplied source label or `authenticated=True` is not itself cryptographic authentication; the trusted transport boundary must supply the assurance.

Repair the decoder, primitive fence, dispatcher and confirmation boundary together. Use one qualified cessation decision, reject conflicting or malformed supplied telemetry, preserve operation/device correlation and timing, and retain STOP_PENDING/STOP_REQUESTED, watchdog and exposure whenever physical outcome is unresolved. Test normal cancel, emergency, watchdog, restart and late ACK/fence paths with both confirmed and unconfirmed controls. Do not reintroduce CUSTOM as a simulation category.

### CS-02 — P1: Future-issued weather enters through `weather_prior`

The direct-weather and historical-lookback guards work in the exercised controls. Their fallback path does not. For a run on 3 January at noon, a weather prior issued on 4 January with 8 mm rain reaches the **native water solver** and is published in a scoped checkpoint. The same future-issued record in `weather_daily`, without a prior, is correctly rejected and publishes no checkpoint.

A second path fills missing components of an earlier observation from that future prior. The committed receipt then attributes the 8 mm rainfall to the earlier observation's role and 2 January issuance, losing the supplying prior's future availability. This is prospective contamination of the numerical state and replay evidence, not merely a label problem.

Qualify priors against the step's issuance limit before any direct fallback, parser default or persistence/climatology fill. Preserve component-level supplier provenance when combining records. One shared fix should cover both paths. Keep past-issued positive controls and legitimate climatology/missingness behavior explicit.

### CS-03 — P1: Invalid EO geometry still becomes updateable evidence

Missing CRS/transform now correctly produces restricted evidence. However, a nonempty invalid CRS, a singular all-zero transform, or a transform containing infinity is labelled spatial-qualified. Native EO inference through Layer 1 conversion, truth normalization, evidence validation and the actual evidence ledger accepts the anomaly evidence as `observed`, `state_update_allowed=True`, `production_usable=True`.

Use one strict spatial qualifier at model and adapter boundaries: recognized CRS, finite non-boolean affine coefficients, explicit coefficient convention, invertibility and coherent dimensions. Do not let a non-None flag substitute for physical spatial support. Preserve the existing finite aligned positive and missing-geometry diagnostic controls.

### CS-04 — P1: Non-finite EO pixels are laundered into valid support

Six all-infinite reflectance bands return a finite embedding, 24 valid input values and confidence .56. In a sharper comparison, replacing only B2 by infinity versus missing values produces **the same tile hash but different embeddings and quality**: valid counts 24 versus 20, confidence .56 versus .55. Hashing treats infinity as missing while model normalization clips it into supported reflectance.

Qualify finite non-boolean numeric pixels before clipping; build normalization, valid masks, support counts and hashes from the same admission policy. Preserve genuine physical zeros. Repair CS-03 and CS-04 together under the EO owner, including the downstream permission receipt rather than only testing a helper flag.

### CS-05 — P2: Warm sensor workers miss committed foreign rows

Native two-process reproduction: A initializes an empty warm index; B commits row B; A commits row A. A reads `[A]` while a fresh process reads `[B,A]`. A's own append updates its cached file stat to the entire current disk generation, but adds only A to its stale RAM index. The getter then incorrectly considers that incomplete index synchronized until another external write occurs.

After append, invalidate the cached generation or rebuild/advance from a fully synchronized locked snapshot. Do not claim the whole file generation loaded after adding only the local row. Keep the passing append atomicity, corruption and disk-first contracts. This violates the cohort's explicit distributed rehydration outcome despite durable disk rows remaining intact.

## 4. What independently passed

| Boundary exercised | Retained result | Qualification |
|---|---|---|
| EO ONNX-failure fallback | Actual spectral backend and fallback-weight digest reported | ONNX failure injected at the runtime helper; no real provider/model calibration performed. |
| EO grid/mask shapes | Ragged and dimension-mismatched inputs reject | Missing geometry restrictions survive native admission; malformed nonmissing geometry is CS-03. |
| Sensor concurrent normalized writes | 24 parallel rows remain intact | POSIX process test, not Windows or power-loss certification. |
| Raw same-ID publication | Eight workers, exactly one winner | Adjacent atomicity control; not full ingestion exactly-once acceptance. |
| Nonce admission | Eight workers, one winner; release allows retry | Bounded shared-admission control. |
| Corrupt normalized log / failed append | Typed corruption failure; no RAM publication after failed append | Warm cross-worker consistency still fails CS-05. |
| Direct weather / historical lookback | Future-issued records excluded; qualified past records retained | Prior fallback remains CS-02. |
| Hydraulic parameter inputs | Supplied Ks, alpha and n precision retained | No independent field physical-accuracy/calibration conclusion. |
| HT and proxy negligible updates | Returned ensemble rolls back to prior in exercised cases | HT ndarray caller-alias side effect is separately documented; actual run_enkf consumes returned cube. |
| Canonical water/V90 identity | Root-zone/wetness/canopy distinctions and conflicting certification denial pass | No operational V90 field certification granted. |
| Ordinary covariance controls | PSD/singular positives accepted; tested small indefinite matrices reject | Numerical tolerance is not exact mathematical PSD at every scale. |

The original R706 typed-consumer, bare-soil binding and v3 migration findings remain closed within their accepted scope. This audit does not use fresh unrelated requirements to reverse that decision.

## 5. Numerical and inherited follow-ups: keep them bounded

**Finite extreme covariance:** `[[1e200,0],[0,1e200]]` raises OverflowError in a pre-try `scale ** 2`/Cauchy–Schwarz calculation. Native surface generation aborts, dropping a valid sibling, whereas an aligned ordinary control emits both states. Record this P2 numerical resilience follow-up under the existing ASMAE owner; normalize before squaring or safely reject locally. It is an extreme authored input, not a demonstrated normal field failure. Bundle it with the next numerical repair rather than opening another ASMAE-only review project.

The matrix validator also has an absolute numerical floor; do not claim every arbitrarily tiny indefinite matrix is rejected. Use a stated scale policy and stable algorithms rather than literal mathematical exactness claims.

**Raw replay:** the inherited `replay_raw_message` path attempts to iterate `DecoderResult` rather than its readings, causing TypeError for valid raw input. This is remaining F39 replay scope, not introduced by the eight new commits and not a reason to reopen ASMAE closure.

**EO package remainder:** the current model emits a fallback-weight digest, but full digest/version provenance is not preserved through every consumer. The generic ONNX statistics tensor is not evidence of correct per-model spatial adapters. Record remaining F25 criteria instead of equating fallback tests with full model acceptance.

Other inherited projection/display, real-plot/browser/GIS export, independent observability/calibration and scientific extensions remain under their own package criteria. A structural 13-state catalog is not 13 independently observed field maps.

## 6. Correct the progress record once

The task register has **225 numeric deliveries, 8 early slices and 52 FA milestones: 285 unique checkboxes, all open**. Only 52 are full acceptances. Treating all 285 as empirical/field milestones is incorrect and hides software delivery. Conversely, open checkboxes do not prove zero implementation.

The current walkthroughs claim 32% overall, 53% or 54% immediate-cohort maturity, and individual lane percentages without an accepted criterion rubric, numerator or weight calculation. These are **unverified planning estimates**, not independently audited achievement. The older walkthrough's current-head reference `730b9fe` is historical relative to `220953f`.

Also correct the blanket explanation that every FA must await growing-season data or hardware. Apply each package's own criteria. F21/F34 examples have software-verifiable full acceptance outcomes; F29/F36/T06/T12 and applicable operational commissioning require empirical work. This review preserves all 52 open statuses and does not grant any FA.

Maintain one evidence ledger with: package/ticket, exact criterion, implementing SHA, verifying SHA, downstream receipt, disposition, merge state, owner and remaining obligation. Track software verification separately from empirical validation and operational release. Do not sum successive repair counts or test totals as independent progress. Do not invent a global percentage before this reconciliation.

## 7. Faster delivery from here

| Owner | One bounded current repair batch | Exit evidence |
|---|---|---|
| Execution | CS-01 decoder/fence/receipt consistency | Unconfirmed or contradictory stop never releases ownership across cancel, emergency, watchdog, late ACK and recovery; confirmed positives still finish. |
| Temporal / trajectory | CS-02 prior and component provenance | Future prior cannot enter solver or durable history through any fallback; qualified past positives remain usable. |
| EO | CS-03 plus CS-04 shared input admission | Invalid geometry/pixels cannot acquire observed update authority; support hash and effective computation agree. |
| Durable evidence | CS-05 warm-generation synchronization | Warm and cold readers agree after interleaved own/foreign commits; append/nonce/corruption positives remain. |
| Integrator | Consolidate exact-SHA evidence and tracking corrections | One integrated candidate; named failures closed; no silently waived criterion. |

The numerical extreme and inherited replay/provenance work can be assigned as visible subitems where dependency-ready. Independent owners need not idle behind execution work. After actual prerequisite acceptance, existing next packages include F05, F12, F21, F27, F30, F32, F33 and F35; the plan appendix lists prerequisites. Larger T capability extensions remain substantial and cannot be inferred complete from this cohort.

**Implementation decision:** continue independent ready work now; do not accept the entire current four-owner cohort as complete or promote its unsafe execution slice while these reproductions persist. Preserve already accepted software slices. Fix the four owner batches in parallel, freeze one candidate, and conduct one integrated exit review. No serial whole-repository audit is needed after each individual fix.

## 8. Reproducibility and scope

The materialized corpus contains 904 Git-blob-verified files at the current tree, including all 20 production Python files changed since `570341c`, selected unchanged dependencies and current plan sources. Every materialized tracked Python file parses. This is source identity and syntax coverage, not exhaustive correctness of 904 files. The repository tree was complete/nontruncated. Compare data retains the 8-commit recent range and 21-commit main range.

Six parallel review lanes used independent authored inputs and production symbols rather than repository test expectations. The root reran six scripts: execution, durability, EO, temporal source selection, full native hydraulic solver/persistence and ASMAE. Successful script completion includes expected counterexamples. The evidence records substitutions precisely: controlled transports/provider boundaries, isolated artifact paths, source-selection sink versus real solver, and untested external paths.

No real controller, drone, weather/provider service, browser, HTTP deployment, ONNX model calibration, full repository regression suite, Windows lock acceptance, power-loss test or growing-season reference study was executed. Other chat transcripts could not be retrieved directly; all-sessions coverage here means the accessible published commit/artifact chain and connected current contracts. If a session produced unpushed work or no saved artifact, it is outside the observed evidence rather than presumed complete.

The existing R3 monograph remains the scientific target. Prospective availability, finite evidence/support identity, bounded authority and durable scientific provenance are the specific contracts exercised here. Its larger agronomic, data-science, AI, economic and operational requirements are neither removed nor certified by this software audit.

Detailed lane reports and exact receipt/probe results follow in the full report and evidence bundle.


---

# Appendix — safety independent review

# Integration S: consolidated physical STOP review at 220953f

Read-only independent review, 27 October 2026. Candidate `220953f4a8436e394a091d375b4fe6388648448b`, aggregate changes after `570341c`. Only authored software fixtures were used; no physical equipment, providers or public HTTP endpoint was operated. The source under `../source/` is the root's Git-blob-verified materialization. `probes.py` runs the native base actuator, HTTP driver, dispatcher cancellation, registry, SafetyMonitor and SharedQuotaStore. The transport response is the only stub in the concrete HTTP path. Fresh temporary quota directories isolate durable state. Repository tests and audit documents are not a correctness oracle.

## Recommendation

**Do not accept the four-owner cohort's physical STOP boundary yet.** One consolidated Integration S finding remains, with two reproduced execution defects and an authentication qualification gap. Repair these together under the physical execution owner and review the integrated candidate once. These findings do not reopen the accepted three-defect ASMAE 563c6fa closure. Parallel non-dependent work can continue.

## S-STOP-01: contradictory HTTP response becomes confirmed STOP and removes active obligations (P1)

`drivers/http_driver.py:385–398` and `496–512` derive contradiction only from boolean `is_running is True`, positive flow and explicit `is_stopped is False`. They do not treat the textual status `RUNNING` as a denial. Consequently these receipts both produce `confirmed_physical_stop=True`:

```python
{'status': 'RUNNING', 'is_running': False, 'flow_rate_lpm': 0.0}
{'status': 'RUNNING', 'confirmed_stopped': True}
```

Both native `_stop_zone` and `emergency_stop` certify the contradictory inputs. The native `CommandDispatcher._is_stop_confirmed` accepts the emergency result. This is a disagreement between explicit fields, not merely absent telemetry.

The full native cancellation control registers an HTTP actuator with vendor CUSTOM, model `real-field-controller`, a running own-operation command, an admitted durable 8 mm reservation and active duration monitor. Its HTTP transport returns the first contradictory receipt. `cancel_event` publishes:

```json
{"event_status":"CANCELLED","active_tracking_retained":false,"watchdog_retained":false,"stopped_receipt_exists":true,"active_reservation":false}
```

This establishes premature software finalization despite unqualified physical evidence. It does not establish any field hardware's actual flow. Positive `STOPPED/false/0` is accepted; `STOPPED/false/2` correctly remains unconfirmed. The same proof path also accepts NaN flow with STOPPED text, whereas numeric qualification elsewhere in the system rejects non-finite physical measurements. Fix the denial-first typed receipt parser for **both** HTTP STOP paths; reject contradictory or invalid supplied fields before considering positive evidence. Preserve operation correlation and known positive/negative controls.

## S-STOP-02: late START fence still equates transport success with physical cessation (P1 primitive boundary)

`actuator.py:587–598` calls `send_command(fence_stop)` directly, then uses `fence_res.success` alone. This bypasses the physical-proof semantics already implemented in `_execute_stop_direct`. An ACK-only result with `transport_acknowledged_only=True` and `confirmed_physical_stop=False` is enough to mark the actuator ONLINE and clear its active command.

The native controlled transport fixture pauses START until a STOP is issued; that STOP correctly puts the base actuator in STOP_PENDING_CONFIRMATION. START subsequently completes and the late fence also returns only transport acknowledgement. Result:

```json
{"after_first_stop":"STOP_PENDING_CONFIRMATION","after_late_fence":"ONLINE","controller_still_running":true,"active_command_retained":false,"error_code":"PREEMPTED_BY_STOP","stop_count":2}
```

`controller_still_running` here is the explicitly controlled software transport state, not an observation of hardware. The native public base `execute_with_safety` path is exercised. The dispatcher late outcome code at `dispatcher.py:679–688` retries the fence only for EXECUTING/ERROR; the erroneous ONLINE classification therefore bypasses that follow-up branch. We do **not** claim that this separate probe executed the entire dispatcher submit lifecycle or universally released its durable reservation; the full native cancellation demonstration belongs to S-STOP-01 above.

Use the same qualified physical STOP predicate in the late fence as in all other stop paths. If only queued/transport acknowledgement is available, keep the active operation context and pending cessation status. A late START may not erase that boundary because a second STOP send returned success.

## S-STOP-03: receipt authentication claim exceeds the implemented guarantee (P2 qualification / same repair owner)

`actuator.confirm_stop` requires a source from a static string allowlist but only rejects authentication when `receipt.get('authenticated') is False` (`actuator.py:916–922`). Omitting authentication passes. With a correctly matching operation ID, current timestamp, `source='controller'` and `status='STOPPED'`, the native method returns True, clears the active command and sets ONLINE. Explicit `authenticated=False` is correctly rejected. Explicit True also passes.

This proves caller-declared labels/absence are accepted; it does **not** prove a remotely reachable exploit, authentication bypass across an HTTP route, or that a trusted in-process caller is malicious. No cryptographic or authenticated transport verifier is exercised by the method. Describe the current boundary as a trusted-caller assertion unless a verified receipt carrier is supplied by an authenticated driver/controller layer. For the promised authenticated-receipt contract, validate actual trusted ingress identity and exact operation correlation, then pass a non-forgeable/internal qualified receipt or proof rather than inferring authentication from a source string. At minimum, missing/invalid explicit authentication must not be described as independently verified authentication.

The direct recovery fallback also does not reject when all active, pending and durable correlation anchors are absent (`actuator.py:858–860`); only a nonempty operation token remains. `confirm_stopped_event` supplies its expected ID set, which protects that dispatcher route. Treat no-anchor direct calls as an unverified contract case, not as proof that the dispatcher path lacks correlation.

## Retained improvements and test interpretation

- CUSTOM is no longer itself a simulation classification; the concrete HTTP controls use CUSTOM and a real-field model, and physical flags govern acceptance.
- A normal direct ACK-only STOP correctly yields STOP_PENDING_CONFIRMATION; its late-fence sibling is the remaining inconsistency.
- Positive stopped feedback is accepted; explicit positive flow is rejected by both HTTP STOP paths.
- Missing timestamps, explicit untrusted sources and explicitly false authentication have denial code in `confirm_stop`; only missing-auth positive/false controls were executed here.
- Modbus complete-register and MQTT correlated ACK branches were source-inspected but not independently exercised by this probe. Do not present them as field commissioning or exhaustive protocol verification.

## Single integrated repair exit

One owner should unify the physical STOP qualification predicate, typed contradictory-field parsing and verified-receipt ingress. Re-run ordinary cancel, emergency stop, late START fence, restart and event confirmation against the same receipt matrix. Preserve active reservation/watchdog and canonical command envelope until physical cessation is qualified. Include valid STOPPED controls, positive-flow/running denials, malformed scalar inputs, ACK-only transport and missing receipt authentication. The requested follow-up is one bounded Integration S cohort patch, not three serial residual review projects.


---

# Appendix — durable independent review

# Integration D — consolidated source verification

Candidate: `220953f4a8436e394a091d375b4fe6388648448b`, read-only review on 27 October 2026. Owning packages: F39, with sensor ingress/namespace contracts shared with F01/F37. Current production modules are drawn from the root's Git-blob-verified source corpus. This is bounded native software evidence, not field, provider, hardware, power-loss, or Windows acceptance.

## Decision

The recent storage changes make substantive progress: complete raw-file publication under an OS advisory lock, disk-first fsynced normalized appends, typed corrupt-normalized-log failure, and strict identifier qualification work in the exercised controls. They do **not** yet establish the advertised multi-worker reader consistency. One deterministic P2 counterexample remains in the changed storage implementation and directly contradicts the current walkthrough's distributed rehydration claim.

Keep the ASMAE A+B closures intact. Repair the F39 synchronization issue inside the existing durable-evidence lane; do not restart the broad ASMAE review loop. An additional inherited replay helper defect belongs to remaining F39 package criteria and is recorded separately below.

## D-CURRENT-01 — P2: an own append certifies a stale worker index as current

Production source: `services/agribrain/sensor_runtime/storage.py`, lines 312–354, especially 348–354; conditional reload at lines 357–406.

`store_normalized_reading` appends its row durably, reads the latest entire file's stat into `_LAST_NORM_FILE_STAT`, and appends only its own row to `_NORMALIZED_STORAGE`. It never brings a previously stale worker index up to the generation whose stat it just records. The next getter sees matching file stat and skips disk rehydration, omitting already committed foreign rows.

Independent native subprocess reproduction:

1. Worker A initializes an empty store/index.
2. Separate OS process B calls the unchanged native `store_normalized_reading` for row `B` and exits successfully.
3. A calls native `store_normalized_reading` for row `A`.
4. A's native getter returns `["A"]`.
5. A fresh independent process, reading the exact same durable log, returns `["B", "A"]`.
6. A third foreign append `C` changes the stat; A then sees `["B", "A", "C"]`.

The durable bytes survive; this is a stable missing-evidence/read-generation defect, not alleged physical disk loss. It persists until another file change or restart. No provider or scheduler assumptions are needed. The reproduction is deterministic and does not use sleep, clock manipulation, repository tests, monkeypatching of production storage, or fake lock implementations.

Expected criterion: once A's store returns, its public getter must expose all committed records in the associated durable generation, matching a cold reader. The walkthrough explicitly claims distributed multi-worker rehydration at lines 120–122.

Repair direction: never advance the index's generation token beyond the records actually loaded into that index. The simplest safe approach is to invalidate the cached token after a successful own append and load a complete consistent snapshot before the next read; alternatively maintain a qualified append offset/generation under the same OS lock and account for every intervening row. Preserve disk-first publication, detached copies, and fail-closed corruption behavior. Do not merely refresh before append while still allowing a competitor between refresh and publication.

Exit proof: repeat A-init → B-write → A-write → A-read and require exact `[B,A]` parity with cold control; include B writes between A's refresh/append if implementing an incremental protocol. Keep the parallel writer and corruption controls below.

## Controls independently passing

`durable/probes.py` imports and invokes production symbols from the pinned corpus. All controls run in fresh temporary directories, with subprocesses sharing only explicit isolated storage paths.

| Control | Native result |
|---|---|
| 24 normalized rows from independent OS worker processes | 24 unique complete rows retained; cold public getter reads all |
| Eight workers publish the same immutable raw message ID | Exactly one winner; seven `ValueError` refusals |
| Appended malformed JSON normalized line | Public getter raises `StorageCorruptedError` |
| Controlled append failure before disk publication | Exception propagates; RAM index remains empty; no invented successful row |
| Eight processes atomically reserve the same nonce | Exactly one admitted winner |
| Native nonce rollback/release | Removes seen/durable reservation and permits one qualified retry |
| Canonical/short sensor module imports | `NormalizedSensorReading` and storage module identities match in the tested full-name-first order |

The append-failure control injects an `OSError` at `_acquire_and_append`, to qualify the writer's disk-before-RAM behavior. It is a fault injection, not a real power interruption or filesystem stress test. Other listed controls run the native storage/locking/nonce implementations. POSIX `flock` was exercised; Windows `msvcrt` remains unverified here.

Source inspection also confirms that ingestion now calls `store_normalized_reading` and propagates failure as `RuntimeError` rather than returning a successful normalized list (ingestion.py lines 260–266). Registry/calibration readers remain explicit production-path lookups. This review does not establish every scientific calibration or device credential contract from those facts.

## D-INHERITED-02 — P2: raw replay helper consumes the wrong return type

Separate remaining F39 criterion, not introduced by the latest eight commits. `sensor_runtime/replay.py` lines 11–15 assigns the native `DecoderResult` object to `readings` and iterates it. Current `decode_raw_message` returns a `DecoderResult` with a `.readings` list, not an iterable of readings.

A valid raw HTTP JSON payload with soil_moisture_vwc=0.2 and unit=fraction raises `TypeError: 'DecoderResult' object is not iterable` in native `replay_raw_message`. The exact valid fixture and error are in `probes.py` / `results.json`. Qualify this on the existing F39 replay task when completing that package; do not describe the entire evidence replay capability as accepted while this supported helper fails. The likely implementation correction is consumption of `.readings` while deliberately preserving decoder diagnostic/strictness information and original timestamps.

## Documentation and verification boundaries

The current walkthrough still describes raw publication using final-path `O_EXCL`; the latest native implementation instead writes/fsyncs a unique temporary file and checks/replaces the final destination under an OS-backed advisory lock. The latter passed the same-ID control. Update the walkthrough mechanism description without treating this wording mismatch as another production blocker.

No repository test counts were accepted as independent correctness proof. No source file, Git ref, register checkbox, or monograph was modified. All FA obligations remain separate from these software controls. This review does not claim transaction-wide exactly-once recovery across a partially normalized multi-reading payload, physical calibration validity, Linux power-cut durability, or Windows behavior.

Reproduce from the shared workspace using `python sessions-20261027/durable/probes.py`. Results are written to `durable/results.json`; standard output copy is `durable/stdout.json`.


---

# Appendix — eo independent review

# Consolidated EO integration review — current branch 220953f

Candidate: `220953f4a8436e394a091d375b4fe6388648448b`. Read-only review of F25/F26 Integration E and connected Layer 1 admission. Production files were supplied from the pinned Git tree and hash verified by the root. No repository tests or implementation narratives were used as correctness oracles.

## Decision

The concrete earlier repair slices pass the bounded controls: ONNX execution failure reports `spectral_basis_v2` and the actual spectral-weight SHA-256; ragged or differently sized bands/cloud masks reject; absent geometry is explicitly flagged and the real admission/normalization path retains `state_update_allowed=False` and `production_usable=False`.

**Do not mark F26's scientific admission boundary complete yet.** Two directly reproducible cases still admit unsupported data. They can be repaired together by the EO owner as one input-qualification change, without reopening ASMAE's accepted A+B closure or unrelated packages.

## E27-01 — P1: Invalid spatial evidence earns update permission

Production path: `EOFoundationModel.infer` → `Layer1FusionEngine._try_eo_embedding` → `_admit_evidence_or_quarantine` → native `normalize_evidence_truth`/`validate_evidence` → actual `EvidenceLedger.add`.

Six aligned 2×2 bands with finite values were submitted with each of these metadata fixtures:

- Valid control: CRS `EPSG:32631`, transform `[100,10,0,200,0,-10]`.
- Missing control: no CRS or transform.
- Singular transform: CRS `EPSG:32631`, six zero transform coefficients.
- Non-finite transform: CRS `EPSG:32631`, origin `+Inf` and otherwise the valid transform.
- Invalid CRS: `not-a-coordinate-system`, otherwise valid transform.

The missing control is correctly blocked for state updates. The latter three fixtures are all labelled `is_spatial_qualified=True` and the anomaly-score evidence is actually admitted as `observed`, `state_update_allowed=True`, `production_usable=True` without `UNQUALIFIED_SPATIAL_IDENTITY`.

Cause: engine lines 735–755 accept any nonempty CRS and float-convert six transform values without checking finite values/invertibility. Model line 369 defines qualification solely as non-None CRS/transform. The EO normalizer (truth_bridge lines 457–465) trusts this qualification flag rather than independently establishing the physical support. Existing `_has_valid_geospatial_grid` is used elsewhere and does not gate this EO branch.

Required repair: one shared strict spatial qualifier used by both model and native engine; reject/mark unavailable non-finite, boolean, singular/noninvertible transforms and invalid CRS, retaining diagnostic-only behavior through admission. Freeze the affine convention explicitly; do not decide invertibility by accepting either of two unrelated coefficient conventions. Preserve valid same-grid controls and absent-geometry diagnostics.

This demonstrates a software admission/authority error; it does not establish a current live-plot incident, remote exploit, or field outcome.

## E27-02 — P1: Infinite reflectance is clipped into supported measurements and collides with missing-data identity

Production model normalization lines 414–421 skips None and NaN, but does not reject infinities or booleans before arithmetic and `[0,1]` clipping.

Native six-band 2×2 all-`+Inf` input returns a finite embedding, `valid_pixels=24`, confidence `0.56`. The values should be rejected or excluded as unsupported; they must not improve input quality.

More discriminating control: keep five finite bands unchanged, replace B2 with all `+Inf` versus all `None`. Both inputs have the **same tile hash** because `_compute_tile_hash` maps both to `NaN` (lines 729–733). Yet they produce different embeddings and quality: valid pixels `24` versus `20`, confidence `.56` versus `.55`. Thus a single support identity describes different effective model evidence, violating F26's complete-support identity/finite-pixel criteria.

Required repair: qualify finite, non-boolean native numeric pixels before normalization, build an explicit validity mask from that same qualification, and hash the exact admitted support/missingness policy. Apply equivalent mask/scalar qualification without laundering invalid values to reflectance endpoints. Keep legitimate physical zero reflectance distinct from missing values and preserve supported finite-band outputs.

## Retained evidence and package limits

- ONNX runtime failure was simulated only at `_infer_onnx` returning None; fallback computation, digest calculation, result construction, Layer 1 conversion, truth normalization, validation and ledger are native production functions. No real ONNX weights/provider execution was attempted.
- Native EO class emits the correct fallback-weight digest, but `_try_eo_embedding`'s audit dict (engine lines 853–863) and evidence provenance do not preserve `model_weights_digest` or preprocessing/model version. This is a remaining F25 provenance integration item, not proof the bounded digest computation repair failed.
- `_infer_onnx` still constructs a generic `(1,N_FEATURES)` statistics tensor and truncates/pads outputs (lines 488–506). No actual per-model spatial tensor adapter/calibration validation was established. Do not infer complete F25 acceptance from fallback/backend tests.
- F25/F26 remain open in the register. These findings concern named package criteria and currently changed EO admission, not all 52 packages or the already closed A+B defects.

## Reproduction

`python sessions-20261027/eo/probes.py`

Inputs are authored locally. `results.json` preserves exact backend/digest, spatial role/permission receipts, shape failures and hash-collision comparison. No network/provider/hardware interaction or production-source mutation occurs.


---

# Appendix — temporal independent review

# Temporal and hydraulic cohort verification — 220953f

Read-only source review of `220953f4a8436e394a091d375b4fe6388648448b`, across the cumulative changes following `570341c`. Scope: F02/F06 weather-at-issuance admission and persistence, plus F04/F08 hydraulic parameter precision and digest continuity. The root materialized and Git-blob-verified the production sources. Repository tests and implementation walkthroughs were not the correctness oracle.

## Disposition

**One demonstrated P1 residual remains in the agreed F02/F06 boundary: `weather_prior` bypasses issuance qualification and can also backfill future weather into an apparently earlier observation receipt.** Treat these as two entry paths of one repair, not separate serial review projects. Other exercised direct-weather and lookback controls pass.

### T-01: Unqualified weather-prior fallback and component backfill

Production targets:

- `services/agribrain/layer3_decision/runner.py:1104–1109`: after correctly rejecting ineligible daily weather, the fallback copies any `weather_prior` dictionary into the current record and sets `is_prior=True`; no issuance predicate is evaluated.
- Same file `1159–1165`: `_parse_weather` fills missing weather components from `weather_prior` without checking its issuance or merging its provenance. The parsed record retains the primary record's `issued_at` and role.
- Same file `1189–1207`: parser records only primary-record source role/issuance.

Reproduction, full native orchestration/solver/persistence:

1. Run timestamp `2026-01-03T12:00:00+00:00`.
2. Supply `weather_prior` with `issued_at=2026-01-04T00:00:00+00:00`, `source_role=forecast`, and complete finite meteorology including 8 mm precipitation.
3. Invoke the unmodified native `_execute_canonical_water_engine`, native `WaterIntelligenceEngine.execute_pipeline`, and native `CanonicalWorldlineService` with only artifact roots rebased to isolated temporary directories.
4. Actual: returns `WaterState` and hydrological feedback and commits a scoped checkpoint. Its Jan 3 `history_summary.weather` contains 8 mm precipitation with the future Jan 4 issuance, plus `is_prior=True`. Top-layer VWC is 0.2109. Expected: known-future evidence cannot supply Jan 3 weather-at-issuance; retain missingness or select a qualified prior.
5. Negative control: the identical future-issued dictionary placed in `weather_daily['2026-01-03']`, without a prior, correctly returns `(None, None)` and publishes no checkpoint.
6. Positive control: the otherwise identical Jan 2-issued record is admitted and commits normally.

Second path, same root cause:

- Primary daily record has only temperature maximum, `issued_at=2026-01-02T00:00:00+00:00`, `source_role=observation`.
- Future-issued Jan 4 `weather_prior` supplies missing components through recognized fallback aliases `temp_min`, `precipitation`, `wind_speed`, `rh_min`, `rh_max`, `net_radiation`.
- Actual native solver and checkpoint publication succeed; the 8 mm precipitation is persisted with **source_role=observation and issued_at=Jan 2**, losing the supplying future prior's availability/provenance. This is more than a cosmetic metadata issue: the known-future forcing reaches the numerical state.

Risk: causal/prospective contamination of hydraulic calculations and durable replay. This violates the cohort's claimed issuance boundary. This is a remaining connected contract path, not a claim that all of it was newly introduced in the last commit.

Bounded fix: qualify the prior once against the applicable step issuance limit before it can become the main record, supply parser defaults, or seed climatological/persistence fallbacks. Keep supplying component provenance and availability explicit when combining sources; an `is_prior` label must not override an explicit future issuance. Add both native fallback and mixed-component controls, plus valid climatology/no-issuance and past-issued controls. Do not reopen unrelated scientific packages.

## Passing controls

`probes.py` runs the native orchestration with a captured solver sink to isolate source-selection results; it is explicitly not an end-to-end hydrology test. `real_solver_probe.py` independently confirms the blocker through the actual solver and checkpoint writer.

- Future-issued direct daily weather is excluded.
- Past-issued direct daily weather is admitted.
- Future-issued historical lookback candidate with distinctive maximum temperature 99 C is excluded from Jan 1/Jan 2 forcing.
- A valid prior Jan 1 observation at 33 C supplies Jan 2 persistence with zero rain and `imputation_method=prior_weather_persistence_zero_rain`.
- Factory retains supplied Ks `0.00123456789`, alpha `0.003456789`, n `1.6789123` without the old parameter rounding. Derived m is `0.4043762738530178`.
- Native solver positive controls and scoped checkpoint publication complete.

The factory still rounds derived unsaturated-conductivity output to six decimals; this field was not found as a dynamic solver input in the inspected water modules, so it is a presentation/diagnostic follow-up rather than a separately established cohort blocker. No whole-system physical-accuracy or field-calibration acceptance is inferred.

## Evidence and limits

- `probes.py`, `results.json`: nine declared source-selection/precision checks; eight pass and future-prior exclusion fails.
- `real_solver_probe.py`, `real_solver_results.json`: five actual solver/persistence fixtures; both future-prior paths publish, past/qualified positives publish, future direct negative does not publish.
- All inputs authored independently; network denied. Artifact paths isolated. No production source, repository tests, Git references, hardware, or acceptance register changed.
- No provider/API/browser execution, multi-worker hydraulic race stress, or calibration campaign performed in this lane. The demonstrated blocker does not invalidate already-verified ASMAE A+B publication closures.


---

# Appendix — asmae independent review

# ASMAE numerical / certification lane — consolidated sessions review

Candidate: `220953f4a8436e394a091d375b4fe6388648448b`, read-only review, 27 October 2026. Source modules fetched by the root and checked against Git blob identities. `probes.py` exercises native production functions using independently authored fixtures; no repository tests or prior audit verdict is used as an oracle.

## Decision

The original named A+B closures remain intact in the paths exercised. Root-zone/canopy/wetness resolution and conflicting canonical-variable denial work. Returned HT and proxy ensembles roll back excluded negligible updates correctly. The current numerical validator rejects tested nonfinite and small indefinite matrices while preserving PSD and singular-zero controls.

One bounded P2 numerical hardening follow-up is reproducible: extreme finite covariance magnitudes overflow before the validator's exception boundary and abort the native surface generator, losing otherwise valid sibling surfaces. Track it in the existing F36/T09 numerical boundary work; do not turn it into a separate whole-repository review or reopen unrelated A+B closures. No field/calibration certification is claimed here.

## Reproduction and results

Command: `PYTHONDONTWRITEBYTECODE=1 python sessions-20261027/asmae/probes.py`.

| Case | Native result |
| --- | --- |
| PSD `[[1,.2],[.2,1]]` | valid |
| singular zero matrix | valid |
| indefinite `[[1e-5,2e-5],[2e-5,1e-5]]` | rejected |
| indefinite at `1e-10` scale | rejected |
| NaN covariance | rejected |
| root-zone surface, no/generic water metadata | `root_zone_water` |
| canopy surface | `canopy_water` |
| wetness surface | `surface_wetness_event` |
| root-zone surface plus canonical canopy metadata | `conflict_rejected` |
| direct V90 resolver with conflict sentinel | unapproved, `canonical_variable_conflict` and `variable_mismatch` |
| native HT negligible-influence update | excluded, returned cube exactly prior |
| native proxy negligible-influence update | excluded, returned dictionary and input exactly prior |
| finite covariance `[[1e200,0],[0,1e200]]` | unhandled `OverflowError` |
| aligned 2x2 generator with ordinary covariance | vigor and chlorophyll generated |
| same aligned generator with extreme vigor covariance | `OverflowError`; no returned surface collection |

## Numerical follow-up

In `services/agribrain/layer10_sire/surfaces/asmae.py`, lines 139–145, the new Cauchy–Schwarz check computes `scale ** 2` and `cov_ij ** 2` outside the `try` beginning at line 146. Finite magnitude alone does not guarantee finite squared arithmetic. The prior-distribution and support-classification callers do not isolate this exception, so `generate_asmae_surfaces` aborts its whole collection. This is a demonstrated producer-boundary robustness issue under extreme metadata, not a reproduced ordinary bounded-state scientific failure or measured field impact.

Recommended bounded repair: normalize covariance before pairwise/PSD checks or use non-overflowing scaled comparisons, and contain all arithmetic conversion/check exceptions locally so malformed or unrepresentable prior evidence fails closed for the affected state while valid siblings survive. Retain PSD, singular-zero, covariance-alias and existing small-indefinite controls.

The validator also intentionally has an absolute `1e-15` floor: `[[1e-16,2e-16],[2e-16,1e-16]]` is accepted despite a negative eigenvalue. Therefore documentation must not claim rejection of mathematically indefinite matrices at literally every scale. This probe is a tolerance-limit qualification, not a separate blocker; select tolerances explicitly against numerical/physical precision.

## Returned state versus caller-owned array

HT assigns `state_cube = ensemble` at line 1590 and the native batch ETKF updater mutates this array before influence qualification. Line 1781 restores the *returned* local cube via a copy, but an external alias to the originally supplied ndarray retains a `6.579929023864395e-08` difference in the authored negligible fixture. The production `run_enkf` path consumes `ensemble, scene_reports = update_step_ht(...)` (line 307), so the rollback returned to the actual caller is correct. Proxy restores its dictionary in place. Treat ndarray ownership parity as an API clarification/defensive follow-up, not proof that the committed normal EnKF posterior remains wrong.

## Scope limits

Native helper, native update, native generator and native V90 conflict-denial functions ran. A full filtering campaign, provider execution, actual stored valid certification roundtrip, browser map rendering, GIS export or independent agronomic calibration did not run. No production source or milestone was modified. Existing FA obligations remain separate.


---

# Appendix — plan independent review

# Cross-session plan and delivery reconciliation — 27 October 2026

Reviewed tree: `220953f4a8436e394a091d375b4fe6388648448b` on `feat/f36-t09-asmae-13-state-publication`. Comparison base: `570341c0fd769c8aceb0babab65bdf5e443faf74`. This lane reconciles current Git-pinned documents and branch claims; it does not independently certify the production code or reproduce other chat transcripts. Other review lanes own runtime verification.

The recent work has expanded beyond ASMAE into the four-owner cohort. Eight commits follow the comparison base, seven with production changes and one documentation-only revision. This is concrete implementation activity, but neither the new walkthroughs nor the unchanged task register establishes an overall completion percentage or proves that all 16 cohort packages are complete.

## 1. Commit and session reconciliation

| Revision | Claimed delivery focus | Evidence disposition in this lane |
|---|---|---|
| `563c6fa` | Three named A+B integration counterexamples closed | Existing bounded independent closure remains the acceptance scope; do not reopen unrelated stages from this plan review. |
| `570341c` | Covariance, V90 identity, negligible-influence rollback, missing/NaN quality | Comparison baseline. Subsequent exact changes need current production verification, not repetition of this narrative. |
| `aaf3895` | Scale tolerance, HT/proxy rollback receipt parity, V90 conflict | New production repair; ASMAE lane verifies. |
| `730b9fe` | Cauchy–Schwarz, unconditional V90 rejection, ASMAE rollout cache test | New production repair; ASMAE lane verifies. |
| `f041a8f` | Walkthrough revision pin changed | Documentation-only; no extra implementation credit. |
| `6f60a57` | Track A blockers across F25/F26, F39, F17/F18, F01, F04/F08, F02/F06 | Actual broader cohort start. A package reference is not proof of its full criteria. |
| `3687d65` | Physical STOP, multi-worker storage, temporal cutoff, EO alignment | Connected integration repairs; current S/D/E/temporal lanes verify. |
| `df3ead6` | Receipt authority, durable evidence, temporal replay, EO qualification | Further integration repairs; current consumers must be exercised. |
| `87f33ff` | STOP evidence, advisory locking, corruption, EO fallback, lookback cutoff | Later corrective revision supersedes earlier weaker mechanisms in the walkthrough. |
| `220953f` | Remove CUSTOM simulation bypass, authenticate correlated STOP receipts, wire EO qualification | Current candidate. Earlier self-reported passes do not certify these new paths. |

Do not add successive test counts or repair counts as independent progress: many revisions cover the same contract. Preserve one disposition per acceptance criterion with its current validating SHA and the prerequisite it enables.

## 2. Exact register counts and the reporting correction

The exact current register contains **285 unique ticket checkboxes**:

| Ticket class | Open | In progress | Completed |
|---|---:|---:|---:|
| Numeric delivery tickets | 225 | 0 | 0 |
| Early slices | 8 | 0 | 0 |
| Full-package acceptance milestones | 52 | 0 | 0 |
| Total | 285 | 0 | 0 |

The dashboard's 17 stage cells and the lifecycle legend are excluded. The register itself defines these three separate classes near its beginning. Therefore the user-facing assertion that the 285 checkboxes all correspond to full-package acceptance milestones is incorrect. Only 52 do. The other 233 should be reconciled with software evidence; leaving them all unpopulated conceals delivered work.

Also avoid saying that all 52 FAs are inherently blocked by growing-season data or hardware commissioning. Apply each package's own criterion. For example F21 FA asks for immutable content identity, caller-mutation resistance and tenant/namespace isolation; F34 FA asks for applied-versus-planned classification, dimensional correctness and idempotent stock/cost/mass. These are reviewable software outcomes. F29/F36/T06/T12 and relevant operational commissioning criteria retain independent empirical obligations. Preserving all 52 open rows for this review is appropriate; inventing one universal empirical prerequisite is not.

The register has not become a progress meter simply because its open status is preserved. **285 open tickets do not prove zero implementation.** They prove an unreconciled tracking baseline. Likewise test totals, Git commit counts and the number of packages mentioned cannot supply a valid completion numerator.

## 3. Unsupported percentages and stale document scope

Current `AgriBrain_Implementation_Walkthrough_570341c_2026-10-26.md` lines 14–18 state 32% overall, 53% cohort, 0% rounded change, and current head `730b9fe`. Its lane table gives 52%, 56%, 52% and 42%. Current `AgriBrain_Four_Owner_Cohort_Delivery_Walkthrough_2026-10-26.md` lines 13–14 states 32% overall and 54% immediate cohort.

No evidence-weighted criterion register, maturity rubric, accepted numerator or declared weighting is provided for these percentages. A package-count-weighted average of the four lane percentages happens to be 52.5%, which could round to 53%, but that does not validate the lane numbers or the later 54%. These figures must be labelled unverified planning estimates or replaced with evidence-backed quantities. The prior independent delivery annex explicitly declined to verify an overall percentage; its conclusion cannot be cited as validation of 32%.

The old walkthrough can remain a historical record, but `730b9fe` is not the current review-branch head. A new consolidated status should pin `220953f`, show which earlier claims were superseded, and distinguish the branch from `main@90ab701`. The branch's production work is not published on main merely because it is pushed to origin. Separate F01 (`e0e5b1e`) and F02 (`075f19d`) review-branch identities must likewise not be silently treated as merged deliverables.

These are status/reporting findings, not a reason to reopen the accepted A+B code closure. Fix them together in the next tracking reconciliation; do not create another isolated defensive-code cycle for them.

## 4. Package scope that can and cannot be inferred

The declared immediate cohort consists of 16 existing packages: F37, F01, F02, F03, F04, F06, F07, F08, F09, F39, F16, F17, F18, F19, F25, F26. Its original full-package budgets total 388–660 hours, including already completed scope. This is neither a remaining-hours estimate nor a sprint duration.

The changed production files demonstrate wider implementation than the prior publication-only revision, but current walkthrough claims concentrate on selected blockers and integrations S/D/E. They do not enumerate accepted outcomes for every numeric ticket in all 16 packages. In particular, absent a package-level criterion-by-criterion reconciliation, full F03/F07/F09 trajectory acceptance and F37 all-entrypoint cold-start acceptance cannot be inferred from a water initializer repair, one namespace bridge, or a passing consolidated suite. The same applies to F16–F19: software simulation evidence is distinct from any required supported-controller commissioning.

Nor is there current evidence here for completing the other 36 packages. Earlier ASMAE work contributes bounded slices to F36/T09/F38/T11; it is not completion of those packages or of subsequent representation, economics, experiment, national-dashboard or learning capability extensions.

## 5. Faster next action consistent with the existing plan

1. Finish one consolidated exit gate on `220953f`, using actual connected production paths. Preserve accepted A+B software closures. Block only a named failed criterion or demonstrated unsafe/corrupt/incompatible current path; keep unrelated lower-priority work in its existing package backlog.
2. Reconcile the 233 non-FA tickets against accepted exact-SHA evidence. Each row needs package/ticket, criterion, current validation SHA, observed downstream result, reviewer disposition and the remaining obligation. Mark only what that evidence demonstrates. Maintain the 52 FA statuses until each package's own complete criteria are met.
3. Merge the accepted software cohort through normal governance when its agreed gate passes, without waiting for unrelated empirical programs. If a current blocker remains, give it one owner and the exact reproduction while independent ready owners continue.
4. Move owners onto the next dependency-ready packages. The following are **conditionally ready if their listed prerequisite software contracts have actually been accepted**, not automatically ready from the current status narrative:

| Package | Declared prerequisites | Next boundary |
|---|---|---|
| F05 | F01, F04 | Depth-aware soil observations and covariance |
| F12 | F02 | Separate exposure verification from causal attribution |
| F21 | F02, F09 | Immutable training-window payloads and partition identity |
| F27 | F01, F26 | MESIA link-time axes and graph topology |
| F30 | F02, F09 | Scoped conversational memory and cache identity |
| F32 | F09 | Calendar/error states with genuine scoped records |
| F33 | F01, F02, F09 | Photo-zone ownership and durable insert success |
| F35 | F09 | Driver capability and complete mission-process cleanup |

Within the existing next-cohort grouping, subsequent F10/F11/F13/F14/F15, learning F22/F23/F24/F28/F29, action exposure F20/F34 and application reliability work follow their own prerequisites. These need not be forced into one serial stage queue. T08/T09 can advance once their actual prerequisites are accepted, rather than waiting for unrelated model research. Reference recruitment and instrument studies can begin early without granting their capability claims.

One integrator should own shared admission/schema contracts; independent owners consume a frozen interface. Review one integrated candidate per coherent cohort. This preserves the monograph's scientific target while preventing every audit from expanding into an unbounded new project.

## 6. Source and method

All five documents read here are Git-blob verified against the `220953f` recursive tree: the current task register, both walkthroughs, master repair plan and execution addendum. The latter two were reused only after exact local bytes matched the current tree. `results.json` records source blob/SHA-256 identities, every ticket and package dependency, the eight-commit comparison chain and conditional next-ready list.

No repository source, tracked plan, monograph, Git ref, merge or acceptance checkbox was modified. This is cross-session artifact/Git reconciliation; inaccessible other chat transcripts are not claimed to have been read. Runtime, prospective scientific, provider, browser and field conclusions remain with their own evidence gates.
