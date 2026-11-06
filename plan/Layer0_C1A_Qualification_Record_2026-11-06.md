# Layer 0 C1A — Exact-Head Qualification Record

**Implementation branch:** `fix/layer0-c1-scientific-integrity-20261106`  
**Locally qualified implementation HEAD:** `be02d1ef5422118c4308339562040ab643f7786d`  
**Parent correction:** `fd298cc850cd2484020a4d20375d0d3989657676`  
**Baseline:** post-freeze `6b6767c655a3093d1bea9e40b8df792dd5a65267`  
**Disposition:** **L0-C1A qualified for defined source-export and grid-rejection scope**, not formal closure of entire C1 or L0. 
**Execution source:** operator-supplied local Windows/Python test receipts. GitHub check-runs for the candidate are empty; connector review independently verified exact commit and source-only test changes, **not execution**.

## Qualification results reported by operator

| Gate | Result |
|---|---|
| New `test_l0_c1_scientific_integrity_exit_gate.py` | **13/13 PASS** |
| Full Layer 0 Python tests | **813/813 PASS** |
| Layer 1 fusion regression | **21/21 PASS** |
| ASMAE fast regression | **84/84 PASS** |
| Connected Mongo `manual_b2b08_transactional_revocation_connected_gate.py` | **PASS** |
| Connected Mongo `manual_b2b08_postfreeze_observation_only_connected_gate.py` | **PASS** |

Local environment reported: Windows, Python 3.13.13, pytest 9.0.3,
isolated Mongo `127.0.0.1:27018/?replicaSet=rs0` and
`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`.

## Review of the 17 initial failures

The corrective follow-up commit `be02d1e` changes only three files:
- `test_packet_scene_qa_influence.py`
- `test_packet_scope_negative_admission.py`
- `test_plot_zone_observation_support.py`

All three previously supplied `{"test_adapter": True}` as a mocked
self-audit result. The follow-up supplies a minimally structured
`structural_audit={"status":"PASS","checks_run":1,"checks_failed":0}`
test stub. Production audit code, numerical integrity gate, and
spatial 500-pixel rejection were **unchanged** by the follow-up.

The mocked `PASS` is a **fixture assertion**, not empirical evidence
that each fixture's physical state passed a real production auditor.
The local 813/813 suite is evidence for implemented test behavior; it is
not a full independent agronomic calibration.

## Claimed vs actually exercised C1 contracts

**Source-confirmed implemented:** deterministic terminal rejection of
nonfinite exported state/sigma; negative sigma; malformed/mismatched
exported day index; native `enforce_all_invariants(auto_fix=False)`;
cross-source validation exceptions; missing/failed structural audit;
rejected grid extent >500 pixels instead of silent truncation.

**Important correction to the operator summary:** the 13 selected
pytest cases include one parametrized pair, and **do not contain**
a direct complete covariance positive-semidefiniteness test, asymmetric
full-matrix covariance test, or a specific subthreshold-grid-cell-count
test. `scientific_integrity_gate.py` itself documents that it checks
**exported numerical/sigma integrity, not full covariance PSD**.
Any non-PSD/asymmetric covariance guarantees come from other pre-existing
numerical suites and must be cited by exact test name and SHA before
they can be included in C1A's focused acceptance list.

## Outstanding C1/C5 acceptance

1. **Complete covariance and full state-uncertainty consistency**:
   prove any output path cannot convert an invalid full covariance to
   apparently valid exported sigmas.
2. **Cross-layer Layer 0 → Layer 1 gate**:
   a state package marked `scientific_state_admissible=False`,
   missing the marker or bearing mismatched scope/root must not become
   a trusted Layer 1 source; valid qualified input remains model-derived
   and diagnostic-only where appropriate.
3. **Grid coverage beyond safe rejection**:
   optional tiled large-plot support, exact CRS/area/buffer and numerical
   geodetic tests remain unimplemented and cannot be claimed complete.
4. **Persistent failure receipt and runtime route reachability**:
   prove invalid Layer 0 scientific output cannot be consumed by alternate
   legacy/ASGI/worker code paths and preserve failure identity.
5. **Independent source-backed observation**:
   qualify L0 → L1 → ASMAE pilot continuity without any signed irrigation
   receipt; do not conflate locally built unit fixtures with field truth.

**Decision:** accept this **C1A candidate for the tested scope** and
continue C1B/C5 independent cross-layer acceptance in parallel with the
pinned Layer 1 source audit. L0-C2 signed-delivery recovery retains its
separate, disabled-by-policy workstream.

**Protected:** `main`, Scientific Pilot PR #9 and Phase 1F/1G,
signed-delivery post-freeze branch, B2B-08 freeze, historical `findings/`
and intended master architecture monograph unchanged.
